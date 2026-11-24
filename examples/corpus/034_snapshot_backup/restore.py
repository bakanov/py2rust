"""Reconstruct in a private sibling directory and publish with no overwrite."""

from common import checkpoint, outside, present
from content import copy

from py2rust.stdlib import (
    Json,
    create_symlink,
    json_array,
    json_int,
    json_string,
    link_file,
    mkdir_new,
    path_join,
    path_name,
    path_parent,
    path_set_metadata,
    rename_no_replace,
    sync_directory,
)


def restore(config: Json, body: Json, destination: str) -> Json:
    repo: str = json_string(config["repository"])
    target: str = outside(destination, repo)
    assert not present(target), "restore destination already exists"
    stage: str = path_join(path_parent(target), "." + path_name(target) + ".backup-incomplete")
    assert not present(stage), "incomplete restore exists; inspect and remove it before retrying"
    rows: list[Json] = json_array(body["entries"])
    assert len(rows) <= json_int(config["max_entries"]), "restore entry budget exceeded"
    total: int = 0
    for row in rows:
        if json_string(row["kind"]) == "file":
            total = total + json_int(row["size"])
            assert total <= json_int(config["max_bytes"]), "restore byte budget exceeded"
    mkdir_new(stage)
    for row in rows:
        name: str = json_string(row["path"])
        path: str = path_join(stage, name)
        kind: str = json_string(row["kind"])
        if kind == "directory":
            if name != "":
                mkdir_new(path)
        elif kind == "symlink":
            create_symlink(json_string(row["target"]), path)
        else:
            hashed: str = json_string(row["sha256"])
            original: str = json_string(row["link_to"])
            if original != "":
                link_file(path_join(stage, original), path)
            else:
                assert (
                    copy(path_join(repo, "objects/" + hashed), path, json_int(row["size"])) == hashed
                ), "corrupt object"
        checkpoint("restore-entry")
    # Children are finished before read-only parent permissions and timestamps.
    for index in range(len(rows) - 1, -1, -1):
        row: Json = rows[index]
        if json_string(row["kind"]) == "file" and json_string(row["link_to"]) != "":
            continue
        path: str = path_join(stage, json_string(row["path"]))
        path_set_metadata(path, json_int(row["mode"]), json_int(row["mtime_ns"]))
    checkpoint("restore-ready")
    rename_no_replace(stage, target)
    sync_directory(path_parent(target))
    return {"restored": body["name"], "entries": len(rows)}
