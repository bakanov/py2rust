"""Atomic JSON snapshots keep binary data as hex and retain a wall-clock high-water mark."""

import sys

from config import clock_ms, snapshot

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_size,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    pretty,
    read_text,
    regex_fullmatch,
    write_text_atomic,
)


def fault(boundary: str) -> None:
    if env_get("KV_FAULT", "") == boundary:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def total(entries: Json) -> int:
    size: int = 0
    for key in json_keys(entries):
        size = size + len(bytes.fromhex(key)) + len(bytes.fromhex(json_string(entries[key]["value"])))
    return size


def load(policy: Json) -> Json:
    assert not path_is_symlink(snapshot()), "snapshot must not be a symlink"
    if not path_exists(snapshot()):
        return {"version": 1, "clock_ms": 0, "entries": {}}
    with file_open(snapshot(), "rb") as handle:
        assert file_size(handle) <= 8388608, "snapshot exceeds 8 MiB"
    state: Json = json_loads(read_text(snapshot()))
    assert (
        json_keys(state) == ["clock_ms", "entries", "version"] and json_int(state["version"]) == 1
    ), "invalid snapshot"
    clock: int = json_int(state["clock_ms"])
    assert clock >= 0 and clock <= 253402214400000, "invalid retained clock"
    entries: Json = state["entries"]
    assert len(json_keys(entries)) <= json_int(policy["max_keys"]), "retained key limit"
    for key in json_keys(entries):
        record: Json = entries[key]
        assert regex_fullmatch("([0-9a-f]{2})*", key), "noncanonical binary key"
        assert len(bytes.fromhex(key)) <= json_int(policy["max_key"]), "retained key size"
        assert json_keys(record) == ["expires", "value"], "invalid entry fields"
        encoded: str = json_string(record["value"])
        assert regex_fullmatch("([0-9a-f]{2})*", encoded), "noncanonical binary value"
        assert len(bytes.fromhex(encoded)) <= json_int(policy["max_value"]), "retained value size"
        expires: int = json_int(record["expires"])
        assert expires == 0 or (expires > clock and expires <= 253402214400000), "invalid expiration"
    assert total(entries) <= json_int(policy["max_total"]), "retained byte capacity"
    return state


def refresh(state: Json) -> Json:
    now: int = max(clock_ms(), json_int(state["clock_ms"]))
    entries: Json = state["entries"]
    for key in json_keys(entries):
        expires: int = json_int(entries[key]["expires"])
        if expires > 0 and expires <= now:
            del entries[key]
    state["entries"] = entries
    state["clock_ms"] = now
    return state


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    assert not path_is_symlink(snapshot()), "snapshot must not be a symlink"
    fault("before_checkpoint")
    write_text_atomic(snapshot(), text)
    fault("after_checkpoint")
    return  # noqa: PLR1711 - explicit return required by repository guidelines
