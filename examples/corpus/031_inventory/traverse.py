"""Iterative deterministic traversal; symlinks are recorded, never descended into."""

from dataclasses import dataclass

from configuration import excluded

from py2rust.stdlib import (
    Json,
    directory_names,
    json_int,
    json_string,
    path_join,
    path_stat,
    read_link,
)


@dataclass
class Pending:
    path: str
    relative: str
    depth: int


def describe(item: Pending) -> Json:
    metadata: Json = path_stat(item.path, False)
    return {
        "path": item.relative,
        "depth": item.depth,
        "status": "ok",
        "kind": metadata["kind"],
        "size": metadata["size"],
        "mode": metadata["mode"],
        "mtime_ns": metadata["mtime_ns"],
        "ctime_ns": metadata["ctime_ns"],
        "device": metadata["device"],
        "inode": metadata["inode"],
        "links": metadata["links"],
    }


def walk(config: Json) -> Json:
    pending: list[Pending] = [Pending(json_string(config["root"]), ".", 0)]
    rows: dict[str, Json] = {}
    failures: list[Json] = []
    omissions: list[Json] = []
    exclusions: list[str] = []
    cursor: int = 0
    while cursor < len(pending):
        item: Pending = pending[cursor]
        cursor = cursor + 1
        row: Json = {}
        try:
            row = describe(item)
        except Exception:  # noqa: BLE001 - one missing/inaccessible entry must not stop the inventory
            rows[item.relative] = {"path": item.relative, "depth": item.depth, "status": "error", "operation": "stat"}
            failures.append({"path": item.relative, "operation": "stat"})
            continue
        kind: str = json_string(row["kind"])
        if kind == "symlink":
            try:
                row["target"] = read_link(item.path)
            except Exception:  # noqa: BLE001 - preserve metadata when a target is unreadable or unrepresentable
                row["target"] = None
                failures.append({"path": item.relative, "operation": "read_link"})
        if kind == "directory":
            row["scan"] = "complete"
            if item.depth >= json_int(config["max_depth"]):
                row["scan"] = "depth_limit"
                omissions.append({"path": item.relative, "reason": "depth_limit"})
            else:
                names: list[str] = []
                try:
                    names = directory_names(item.path, json_int(config["max_children"]))
                except Exception:  # noqa: BLE001 - bounded-directory errors belong in the report
                    row["scan"] = "error"
                    failures.append({"path": item.relative, "operation": "list"})
                entry_limit: bool = False
                for name in names:
                    if len(pending) + len(exclusions) >= json_int(config["max_entries"]):
                        entry_limit = True
                        break
                    relative: str = name if item.relative == "." else item.relative + "/" + name
                    if excluded(relative, config):
                        exclusions.append(relative)
                    else:
                        pending.append(Pending(path_join(item.path, name), relative, item.depth + 1))
                if entry_limit:
                    row["scan"] = "entry_limit"
                    omissions.append({"path": item.relative, "reason": "entry_limit"})
        rows[item.relative] = row
    ordered: list[Json] = []
    for key in sorted(list(rows)):  # noqa: C414 - explicit dictionary-key snapshot in this subset
        ordered.append(rows[key])
    exclusions.sort()
    return {"entries": ordered, "errors": failures, "omissions": omissions, "excluded": exclusions}
