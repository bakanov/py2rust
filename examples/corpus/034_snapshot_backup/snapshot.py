"""Build an immutable version, publish it last, then retain the newest versions."""

from common import (
    checkpoint,
    checksum,
    present,
    relative,
    stamp,
    unchanged,
    write_document,
)
from content import copy, digest

from py2rust.stdlib import (
    Json,
    directory_names,
    json_array,
    json_int,
    json_string,
    path_join,
    path_resolve,
    read_link,
    remove_file,
    rename_no_replace,
    sync_directory,
)


def scan(source: str, config: Json) -> list[Json]:
    pending: list[str] = [""]
    rows: list[Json] = []
    index: int = 0
    total: int = 0
    while index < len(pending):
        name: str = pending[index]
        index = index + 1
        relative(name)
        path: str = path_join(source, name)
        before: Json = stamp(path)
        kind: str = json_string(before["kind"])
        row: Json = {"path": name, "stamp": before, "target": ""}
        if kind == "directory":
            for child in directory_names(path, 10000):
                assert len(pending) < json_int(config["max_entries"]), "entry budget exceeded"
                pending.append(child if name == "" else name + "/" + child)
        elif kind == "file":
            total = total + json_int(before["size"])
            assert total <= json_int(config["max_bytes"]), "source byte budget exceeded"
        else:
            assert kind == "symlink", "unsupported special file"
            row["target"] = read_link(path)
        rows.append(row)
    return rows


def retain(repo: str, versions: dict[int, Json], keep: int) -> None:
    ordered: list[int] = sorted(list(versions))  # noqa: C414 - explicit typed key snapshot
    referenced: set[str] = set()
    for sequence in ordered[-keep:]:
        for row in json_array(versions[sequence]["entries"]):
            if json_string(row["kind"]) == "file":
                referenced.add(json_string(row["sha256"]))
    for sequence in ordered[:-keep]:
        remove_file(path_join(repo, "versions/" + json_string(versions[sequence]["name"]) + ".json"))
    sync_directory(path_join(repo, "versions"))
    checkpoint("retained")
    for name in directory_names(path_join(repo, "objects"), 100000):
        if name not in referenced:
            remove_file(path_join(repo, "objects/" + name))
    sync_directory(path_join(repo, "objects"))
    checkpoint("collected")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def create(config: Json, versions: dict[int, Json], name: str) -> Json:
    repo: str = json_string(config["repository"])
    source: str = path_resolve(json_string(config["source"]))
    assert source != "/" and source != repo, "source and repository overlap"
    assert not repo.startswith(source + "/") and not source.startswith(repo + "/"), "source and repository overlap"
    assert json_string(stamp(source)["kind"]) == "directory", "source must be a directory"
    target: str = path_join(repo, "versions/" + name + ".json")
    assert not present(target), "version already exists"
    assert len(versions) < 1000, "version capacity reached"
    sequence: int = 1
    for key in versions:
        sequence = max(sequence, key + 1)
    rows: list[Json] = scan(source, config)
    checkpoint("scanned")
    entries: list[Json] = []
    first_links: dict[str, str] = {}
    copied: int = 0
    for row in rows:
        path: str = path_join(source, json_string(row["path"]))
        before: Json = row["stamp"]
        kind: str = json_string(before["kind"])
        entry: Json = {
            "path": row["path"],
            "kind": kind,
            "mode": json_int(before["mode"]) & 511,
            "mtime_ns": before["mtime_ns"],
        }
        unchanged(path, before)
        if kind == "file":
            size: int = json_int(before["size"])
            hashed: str = digest(path, size)
            object_path: str = path_join(repo, "objects/" + hashed)
            if present(object_path):
                assert digest(object_path, size) == hashed, "stored object is corrupt"
            else:
                temporary: str = path_join(repo, "staging/object.part")
                assert copy(path, temporary, size) == hashed, "source changed during copy"
                checkpoint("copied")
                rename_no_replace(temporary, object_path)
                sync_directory(path_join(repo, "objects"))
                sync_directory(path_join(repo, "staging"))
                copied = copied + 1
                checkpoint("object")
            entry["size"] = size
            entry["sha256"] = hashed
            identity: str = str(json_int(before["device"])) + ":" + str(json_int(before["inode"]))
            entry["link_to"] = first_links.get(identity, "")
            if identity not in first_links:
                first_links[identity] = json_string(row["path"])
        elif kind == "symlink":
            entry["target"] = row["target"]
        entries.append(entry)
    for row in rows:
        unchanged(path_join(source, json_string(row["path"])), row["stamp"])
    body: Json = {"format": 1, "name": name, "sequence": sequence, "entries": entries}
    temporary_manifest: str = path_join(repo, "staging/manifest.json")
    write_document(temporary_manifest, {"id": checksum(body), "snapshot": body})
    checkpoint("manifest")
    rename_no_replace(temporary_manifest, target)
    sync_directory(path_join(repo, "versions"))
    sync_directory(path_join(repo, "staging"))
    checkpoint("published")
    versions[sequence] = body
    retain(repo, versions, json_int(config["keep"]))
    return {"name": name, "sequence": sequence, "entries": len(entries), "objects_copied": copied}
