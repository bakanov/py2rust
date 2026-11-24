"""Durable append plans recover partial files before advancing source cursors."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLR1711 - explicit subset returns
from config import exact
from files import hashed, present, read, regular
from state import initial, validate

from py2rust.stdlib import (
    Json, directory_names, env_get, file_open, file_seek, file_sync, file_truncate, file_write, json_canonical,
    json_equal, json_int, json_keys, json_loads, json_string, mkdir_new, path_join, path_parent, remove_file,
    replace_file, sleep, sync_directory
)


def checkpoint(label: str) -> None:
    assert env_get("ROUTER_FAULT", "") != label, "injected failure: " + label
    if env_get("ROUTER_PAUSE", "") == label:
        print("PAUSED " + label)
        for attempt in range(3000):
            sleep(0.01)
        assert False, "pause timed out"
    return


def load(path: str) -> Json:
    envelope: Json = json_loads(read(path, 2097152).decode())
    exact(envelope, ["value", "sha256"])
    value: Json = envelope["value"]
    assert json_string(envelope["sha256"]) == hashed(json_canonical(value).encode()), "control checksum mismatch"
    return value


def save(root: str, name: str, value: Json) -> None:
    data: bytes = (json_canonical({"value": value, "sha256": hashed(json_canonical(value).encode())}) + "\n").encode()
    assert len(data) <= 2097152, "control document exceeds 2 MiB"
    temporary: str = path_join(root, "control.tmp")
    for path in [temporary, path_join(root, name)]:
        if present(path):
            regular(path)
    with file_open(temporary, "w+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    replace_file(temporary, path_join(root, name))
    sync_directory(root)
    return


def inventory(root: str, names: list[str]) -> None:
    allowed: list[str] = names + ["state.json", "pending.json", "control.tmp"]
    for name in directory_names(root, 35):
        assert name in allowed, "unknown file in owned output directory"
        regular(path_join(root, name))
    return


def contents(root: str, before: Json, after: Json, additions: Json) -> dict[str, bytes]:
    old: Json = before["files"]
    new: Json = after["files"]
    names: list[str] = json_keys(new)
    inventory(root, names)
    for name in json_keys(old) + json_keys(additions):
        assert name in names, "recovery plan added an unknown segment or removed a committed segment"
    result: dict[str, bytes] = {}
    for name in names:
        data: bytes = read(path_join(root, name), 16384) if present(path_join(root, name)) else b""
        size: int = json_int(old[name]["bytes"]) if name in json_keys(old) else 0
        prefix: bytes = data[:size]
        assert len(prefix) == size, "committed output was truncated"
        if size > 0:
            assert hashed(prefix) == json_string(old[name]["sha256"]), "committed output was edited"
        extra: bytes = json_string(additions[name]).encode() if name in json_keys(additions) else b""
        assert extra.startswith(data[size:]), "unexpected output suffix"
        complete: bytes = prefix + extra
        assert len(complete) == json_int(new[name]["bytes"]) and hashed(complete) == json_string(
            new[name]["sha256"]
        ), "invalid planned content"
        assert complete.endswith(b"\n") and len(complete.decode().split("\n")) - 1 == json_int(
            new[name]["records"]
        ), "invalid record count"
        result[name] = complete
    return result


def recover(config: Json, current: Json) -> Json:
    root: str = json_string(config["output"])
    pending: str = path_join(root, "pending.json")
    if not present(pending):
        contents(root, current, current, {})
        return current
    plan: Json = load(pending)
    exact(plan, ["before", "after", "append"])
    before: Json = plan["before"]
    after: Json = plan["after"]
    validate(config, before)
    validate(config, after)
    assert json_equal(current, before) or json_equal(current, after), "plan does not match saved state"
    complete: dict[str, bytes] = contents(root, before, after, plan["append"])
    for index in range(len(json_keys(plan["append"]))):
        name: str = sorted(json_keys(plan["append"]))[index]
        path: str = path_join(root, name)
        size: int = json_int(before["files"][name]["bytes"]) if name in json_keys(before["files"]) else 0
        with file_open(path, "r+b" if present(path) else "x+b") as handle:
            file_truncate(handle, size)
            file_seek(handle, size, 0)
            extra: bytes = complete[name][size:]
            halfway: int = len(extra) // 2
            file_write(handle, extra[:halfway])
            file_sync(handle)
            checkpoint("partial-" + str(index))
            file_write(handle, extra[halfway:])
            file_sync(handle)
        checkpoint("file-" + str(index))
    sync_directory(root)
    save(root, "state.json", after)
    checkpoint("state")
    remove_file(pending)
    sync_directory(root)
    checkpoint("cleared")
    return after


def open_store(config: Json) -> Json:
    root: str = json_string(config["output"])
    if not present(root):
        mkdir_new(root)
        sync_directory(path_parent(root))
    if not present(path_join(root, "state.json")):
        inventory(root, [])
        assert not present(path_join(root, "pending.json")), "pending plan lacks initial state"
        save(root, "state.json", initial(config))
    state: Json = load(path_join(root, "state.json"))
    validate(config, state)
    return recover(config, state)


def commit(config: Json, before: Json, after: Json, additions: Json) -> Json:
    validate(config, after)
    if not json_equal(before, after):
        save(json_string(config["output"]), "pending.json", {"before": before, "after": after, "append": additions})
        checkpoint("planned")
        return recover(config, before)
    return before
