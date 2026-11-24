# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
"""Checksummed, bounded snapshots commit the clock before any live/expired response."""

from config import read, setting, stamp, state_path, timestamp
from model import exact, key, lifetime, value_check

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_float,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    write_text_atomic,
)


def digest(state: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(state).encode()))


def document(state: Json) -> str:
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def load() -> Json:
    envelope: Json = json_loads(read(state_path(), setting("TTL_STATE_BYTES", 8388608)).decode())
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "snapshot checksum mismatch"
    exact(state, ["version", "clock", "entries"])
    assert json_int(state["version"]) == 1, "unsupported snapshot version"
    observed: float = timestamp(state["clock"])
    entries: Json = state["entries"]
    assert len(json_keys(entries)) <= setting("TTL_KEYS", 256), "stored key count exceeds limit"
    for name in json_keys(entries):
        key(name)
        record: Json = entries[name]
        exact(record, ["value", "written", "ttl", "expires"])
        written: float = timestamp(record["written"])
        assert written <= observed, "entry written after stored clock"
        ttl: float = lifetime(record["ttl"])
        assert json_float(record["expires"]) == written + ttl, "inconsistent expiration"
        value_check(record["value"])
    return state


def checkpoint(label: str) -> None:
    assert env_get("TTL_FAULT", "") != label, "injected failure: " + label
    if env_get("TTL_PAUSE", "") == label:
        print("PAUSED " + label)
        for attempt in range(3000):
            sleep(0.01)
        assert False, "pause timed out"
    return


def save(state: Json) -> None:
    text: str = document(state)
    assert len(text.encode()) <= setting("TTL_STATE_BYTES", 8388608), "snapshot exceeds byte limit"
    if path_exists(state_path()) or path_is_symlink(state_path()):
        stamp(state_path())
    checkpoint("before_commit")
    write_text_atomic(state_path(), text)
    checkpoint("after_commit")
    return


def initialize() -> None:
    if not path_exists(state_path()) and not path_is_symlink(state_path()):
        save({"version": 1, "clock": 0.0, "entries": {}})
    load()
    return
