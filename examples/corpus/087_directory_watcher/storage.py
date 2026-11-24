"""Checksummed state, strict validation and atomic checkpoint publication under the caller's lock."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLR1711 - explicit subset returns
from configuration import binding, exact, integer, relative
from files import checkpoint, hashed, identity, present, read, regular, stamp
from py2rust.stdlib import (
    Json, directory_names, file_open, file_sync, file_write, json_array, json_canonical, json_equal, json_int,
    json_is_null, json_keys, json_loads, json_string, mkdir_new, path_join, path_parent, regex_fullmatch,
    replace_file, sync_directory,
)


def entry(value: Json) -> None:
    exact(value, ["kind", "device", "inode", "links", "mode", "size", "mtime_ns", "digest", "target"])
    kind: str = json_string(value["kind"])
    assert kind in ["file", "directory", "symlink"], "invalid entry kind"
    for name in ["device", "inode", "links"]:
        integer(value[name], 0, 9223372036854775807)
    integer(value["mode"], 0, 4095)
    integer(value["size"], 0, 1048576)
    json_int(value["mtime_ns"])
    digest: str = json_string(value["digest"])
    target: str = json_string(value["target"])
    assert len(target.encode()) <= 1024 and "\x00" not in target, "invalid link target"
    if kind == "file":
        assert (
            regex_fullmatch("[0-9a-f]{64}", digest) and target == "" and json_int(value["links"]) >= 1
        ), "invalid file"
    else:
        assert digest == "" and json_int(value["size"]) == 0 and json_int(value["links"]) == 0, "invalid nonfile"
        if kind == "directory":
            assert target == "" and json_int(value["mtime_ns"]) == 0, "invalid directory"
    return


def validate(config: Json, state: Json) -> None:
    exact(state, ["version", "binding", "clock_ms", "next_id", "snapshot", "pending", "journal"])
    assert json_int(state["version"]) == 1 and json_equal(
        state["binding"], binding(config)
    ), "state configuration mismatch"
    now: int = integer(state["clock_ms"], 0, 9000000000000000)
    next_id: int = integer(state["next_id"], 1, 1000000000000)
    snapshot: Json = state["snapshot"]
    pending: Json = state["pending"]
    journal: list[Json] = json_array(state["journal"])
    assert len(json_keys(snapshot)) <= 256 and len(json_keys(pending)) <= 256, "state entry limit"
    assert len(journal) == min(next_id - 1, json_int(config["retain"])), "journal retention mismatch"
    total: int = 0
    for path in json_keys(snapshot):
        relative(path)
        entry(snapshot[path])
        parts: list[str] = path.split("/")
        for depth in range(1, len(parts)):
            parent: str = "/".join(parts[:depth])
            assert (
                parent in json_keys(snapshot) and json_string(snapshot[parent]["kind"]) == "directory"
            ), "missing parent directory"
        total = total + json_int(snapshot[path]["size"])
    assert total <= 4194304, "state scan byte limit"
    items: list[Json] = journal.copy()
    for path in sorted(json_keys(pending)):
        item: Json = pending[path]
        assert json_string(item["path"]) == path and path in json_keys(snapshot), "pending path mismatch"
        assert (
            json_string(item["kind"]) in ["created", "modified"] and json_int(item["emitted_ms"]) == 0
        ), "invalid pending event"
        assert json_equal(item["after"], snapshot[path]), "pending snapshot mismatch"
        items.append(item)
    emitted: int = 0
    for index in range(len(items)):
        item: Json = items[index]
        exact(item, ["id", "kind", "path", "previous_path", "before", "after", "first_ms", "last_ms", "emitted_ms"])
        expected_id: int = next_id - len(journal) + index if index < len(journal) else 0
        assert json_int(item["id"]) == expected_id, "noncontiguous event ID"
        first: int = integer(item["first_ms"], 0, now)
        last: int = integer(item["last_ms"], first, now)
        integer(item["emitted_ms"], last if index < len(journal) else 0, now)
        if index < len(journal):
            emitted = integer(item["emitted_ms"], emitted, now)
        kind: str = json_string(item["kind"])
        assert kind in ["created", "modified", "renamed", "deleted"], "invalid event kind"
        relative(json_string(item["path"]))
        if kind == "renamed":
            relative(json_string(item["previous_path"]))
            assert not json_equal(item["path"], item["previous_path"]), "rename must change path"
        else:
            assert json_string(item["previous_path"]) == "", "unexpected previous path"
        assert json_is_null(item["before"]) == (kind == "created"), "invalid before image"
        assert json_is_null(item["after"]) == (kind == "deleted"), "invalid after image"
        for name in ["before", "after"]:
            if not json_is_null(item[name]):
                entry(item[name])
        if kind == "renamed":
            assert identity(item["before"]) == identity(item["after"]), "rename identity mismatch"
    return


def load(config: Json) -> Json:
    root: str = json_string(config["output"])
    if not present(root):
        mkdir_new(root)
        sync_directory(path_parent(root))
    assert json_string(stamp(root)["kind"]) == "directory", "output must be a directory"
    for name in directory_names(root, 3):
        assert name in ["state.json", "control.tmp"], "unknown output file"
        regular(path_join(root, name))
    state: Json = {
        "version": 1,
        "binding": binding(config),
        "clock_ms": 0,
        "next_id": 1,
        "snapshot": {},
        "pending": {},
        "journal": [],
    }
    if present(path_join(root, "state.json")):
        envelope: Json = json_loads(read(path_join(root, "state.json"), 2097152).decode())
        exact(envelope, ["value", "sha256"])
        state = envelope["value"]
        assert json_string(envelope["sha256"]) == hashed(json_canonical(state).encode()), "state checksum mismatch"
    validate(config, state)
    return state


def save(config: Json, state: Json) -> None:
    validate(config, state)
    root: str = json_string(config["output"])
    data: bytes = (json_canonical({"value": state, "sha256": hashed(json_canonical(state).encode())}) + "\n").encode()
    assert len(data) <= 2097152, "state exceeds 2 MiB"
    temporary: str = path_join(root, "control.tmp")
    if present(temporary):
        regular(temporary)
    with file_open(temporary, "w+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    checkpoint("staged")
    replace_file(temporary, path_join(root, "state.json"))
    sync_directory(root)
    checkpoint("committed")
    return
