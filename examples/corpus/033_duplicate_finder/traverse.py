"""Deterministic bounded traversal; retain hard-link aliases without following symlinks."""

from configuration import excluded
from content import stamp

from py2rust.stdlib import (
    Json,
    directory_names,
    json_array,
    json_equal,
    json_int,
    json_string,
    path_join,
)


def scan(config: Json) -> Json:
    root: str = json_string(config["root"])
    pending: list[tuple[str, int]] = [(".", 0)]
    observed: dict[str, Json] = {}
    directories: list[Json] = []
    errors: list[Json] = []
    omissions: list[Json] = []
    ignored: list[Json] = []
    exclusions: list[str] = []
    cursor: int = 0
    while cursor < len(pending):
        item: tuple[str, int] = pending[cursor]
        cursor = cursor + 1
        relative: str = item[0]
        path: str = path_join(root, relative)
        info: Json = {}
        try:
            info = stamp(path)
        except Exception:  # noqa: BLE001 - report each inaccessible entry
            errors.append({"path": relative, "operation": "stat"})
            continue
        kind: str = json_string(info["kind"])
        if kind == "directory":
            directories.append({"paths": [relative], "stamp": info})
            if item[1] >= json_int(config["max_depth"]):
                omissions.append({"path": relative, "reason": "depth_limit"})
                continue
            names: list[str] = []
            try:
                names = directory_names(path, json_int(config["max_children"]))
            except Exception:  # noqa: BLE001 - listing is bounded and all-or-error
                errors.append({"path": relative, "operation": "list"})
            for name in names:
                if len(pending) + len(exclusions) >= json_int(config["max_entries"]):
                    omissions.append({"path": relative, "reason": "entry_limit"})
                    break
                child: str = name if relative == "." else relative + "/" + name
                if excluded(child, config):
                    exclusions.append(child)
                else:
                    pending.append((child, item[1] + 1))
        elif (
            kind == "file"
            and json_int(info["size"]) >= json_int(config["min_size"])
            and json_int(info["size"]) <= json_int(config["max_size"])
        ):
            observed[relative] = info
        else:
            ignored.append({"path": relative, "reason": "size_policy" if kind == "file" else kind})
    files: list[Json] = []
    identities: dict[str, int] = {}
    for name in sorted(list(observed)):  # noqa: C414 - typed key snapshot
        info: Json = observed[name]
        key: str = str(json_int(info["device"])) + ":" + str(json_int(info["inode"]))
        if key in identities:
            index: int = identities[key]
            row: Json = files[index]
            if not json_equal(row["stamp"], info):
                errors.append({"path": name, "operation": "changed_alias"})
            aliases: list[Json] = json_array(row["paths"])
            aliases.append(name)
            row["paths"] = aliases
            files[index] = row
        else:
            identities[key] = len(files)
            files.append({"paths": [name], "stamp": info})
    exclusions.sort()
    return {
        "files": files,
        "directories": directories,
        "errors": errors,
        "omissions": omissions,
        "ignored": ignored,
        "excluded": exclusions,
        "visited": len(pending),
    }
