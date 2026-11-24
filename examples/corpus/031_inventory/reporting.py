"""Logical pathname totals, distinct-inode totals and deterministic extension groups."""

from py2rust.stdlib import Json, json_array, json_int, json_string, pretty


def extension(relative: str) -> str:
    names: list[str] = relative.split("/")
    parts: list[str] = names[-1].split(".")
    if len(parts) == 1 or parts[-1] == "" or (len(parts) == 2 and parts[0] == ""):
        return "(none)"
    return "." + parts[-1].lower()


def add(left: int, right: int) -> int:
    assert right >= 0 and left <= 9223372036854775807 - right, "inventory total exceeds signed 64-bit range"
    return left + right


def summarize(walk: Json, config: Json) -> Json:
    counts: dict[str, int] = {
        "file": 0,
        "directory": 0,
        "symlink": 0,
        "fifo": 0,
        "socket": 0,
        "block": 0,
        "char": 0,
        "other": 0,
    }
    extensions: dict[str, Json] = {}
    seen: dict[str, int] = {}
    logical_bytes: int = 0
    unique_bytes: int = 0
    empty_directories: int = 0
    oldest: int = 0
    newest: int = 0
    inconsistent: list[Json] = []
    parents: set[str] = set()
    for row in json_array(walk["entries"]):
        relative: str = json_string(row["path"])
        components: list[str] = relative.split("/")
        if relative != ".":
            parents.add("/".join(components[:-1]) if len(components) > 1 else ".")
        if json_string(row["status"]) != "ok":
            continue
        kind: str = json_string(row["kind"])
        counts[kind] = counts[kind] + 1
        if kind == "file":
            size: int = json_int(row["size"])
            logical_bytes = add(logical_bytes, size)
            identity: str = str(json_int(row["device"])) + ":" + str(json_int(row["inode"]))
            if identity not in seen:
                seen[identity] = size
                unique_bytes = add(unique_bytes, size)
            elif seen[identity] != size:
                inconsistent.append({"path": relative, "operation": "changed_inode_size"})
            group: str = extension(relative)
            summary: Json = extensions.get(group, {"files": 0, "bytes": 0})
            summary["files"] = json_int(summary["files"]) + 1
            summary["bytes"] = add(json_int(summary["bytes"]), size)
            extensions[group] = summary
            modified: int = json_int(row["mtime_ns"])
            oldest = modified if counts["file"] == 1 else min(oldest, modified)
            newest = modified if counts["file"] == 1 else max(newest, modified)
    # An excluded child still makes its parent nonempty. A pruned/error directory
    # never makes a claim about whether it is empty.
    for value in json_array(walk["excluded"]):
        components: list[str] = json_string(value).split("/")
        parents.add("/".join(components[:-1]) if len(components) > 1 else ".")
    for row in json_array(walk["entries"]):
        if (
            json_string(row["status"]) == "ok"
            and json_string(row["kind"]) == "directory"
            and json_string(row["scan"]) == "complete"
            and json_string(row["path"]) not in parents
        ):
            empty_directories = empty_directories + 1
    errors: list[Json] = json_array(walk["errors"])
    errors.extend(inconsistent)
    return {
        "version": 1,
        "root": config["root"],
        "complete": len(errors) == 0 and len(json_array(walk["omissions"])) == 0,
        "policy": {
            "follow_symlinks": False,
            "exclude": config["exclude"],
            "max_depth": config["max_depth"],
            "max_entries": config["max_entries"],
            "max_children": config["max_children"],
        },
        "counts": counts,
        "logical_bytes": logical_bytes,
        "unique_files": len(seen),
        "unique_bytes": unique_bytes,
        "empty_directories": empty_directories,
        "file_mtime_ns": {"oldest": oldest, "newest": newest},
        "extensions": extensions,
        "entries": walk["entries"],
        "excluded": walk["excluded"],
        "errors": errors,
        "omissions": walk["omissions"],
    }


def text_summary(report: Json) -> str:
    compact: Json = {
        "root": report["root"],
        "complete": report["complete"],
        "counts": report["counts"],
        "logical_bytes": report["logical_bytes"],
        "unique_bytes": report["unique_bytes"],
        "errors": report["errors"],
        "omissions": report["omissions"],
    }
    return pretty(compact)
