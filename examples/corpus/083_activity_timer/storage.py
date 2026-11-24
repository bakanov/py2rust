"""Validate complete interval histories and atomically commit journal snapshots."""

# ruff: noqa: PLR1711 - explicit subset returns
from config import MAX_MONO, MAX_TIME, clocks, integer, setting, state_path
from documents import present, read, stamp
from model import exact, identifier, title

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_is_null,
    json_keys,
    json_loads,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    write_text_atomic,
)


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def document(state: Json) -> str:
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def validate(state: Json) -> None:
    exact(state, ["version", "clock_ms", "mono_ms", "sessions"])
    assert json_int(state["version"]) == 1, "unsupported state version"
    clock: int = integer(state["clock_ms"], 0, MAX_TIME)
    integer(state["mono_ms"], 0, MAX_MONO)
    sessions: Json = state["sessions"]
    assert len(json_keys(sessions)) <= setting("TIMER_SESSIONS", 128), "session limit exceeded"
    for key in json_keys(sessions):
        identifier(key)
        row: Json = sessions[key]
        exact(row, ["name", "status", "created_ms", "updated_ms", "open_ms", "stopped_ms", "intervals", "total_ms"])
        title(row["name"])
        created: int = integer(row["created_ms"], 0, clock)
        updated: int = integer(row["updated_ms"], created, clock)
        status: str = json_string(row["status"])
        assert status in ["running", "paused", "stopped"], "invalid stored status"
        intervals: list[Json] = json_array(row["intervals"])
        assert len(intervals) <= setting("TIMER_INTERVALS", 256), "interval limit exceeded"
        previous: int = created
        total: int = 0
        for index in range(len(intervals)):
            interval: Json = intervals[index]
            exact(interval, ["start_ms", "end_ms"])
            began: int = integer(interval["start_ms"], previous, updated)
            ended: int = integer(interval["end_ms"], began, updated)
            assert index != 0 or began == created, "first interval must start at creation"
            total = total + ended - began
            previous = ended
        assert json_int(row["total_ms"]) == total, "inconsistent completed duration"
        if status == "running":
            assert len(intervals) < setting("TIMER_INTERVALS", 256), "no room to close active interval"
            assert integer(row["open_ms"], previous, updated) == updated, "invalid open interval"
            assert len(intervals) != 0 or updated == created, "first open interval changed start"
        else:
            assert json_is_null(row["open_ms"]) and len(intervals) > 0, "inactive session lacks completed interval"
            if status == "paused":
                assert previous == updated, "paused time differs from final interval"
        if status == "stopped":
            assert json_int(row["stopped_ms"]) == updated, "inconsistent stop timestamp"
        else:
            assert json_is_null(row["stopped_ms"]), "non-stopped session has stop time"
    return


def load() -> Json:
    envelope: Json = json_loads(read(state_path(), 8388608).data.decode())
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "state checksum mismatch"
    validate(state)
    return state


def checkpoint(label: str) -> None:
    assert env_get("TIMER_FAULT", "") != label, "injected failure: " + label
    if env_get("TIMER_PAUSE", "") == label:
        print("PAUSED " + label)
        for attempt in range(3000):
            sleep(0.01)
        assert False, "pause timed out"
    return


def save(state: Json, inject: bool) -> None:
    text: str = document(state)
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    if present(state_path()):
        metadata: Json = stamp(state_path())
        assert json_int(metadata["links"]) == 1, "state acquired a hard-link alias"
    if inject:
        checkpoint("before_commit")
    write_text_atomic(state_path(), text)
    if inject:
        checkpoint("after_commit")
    return


def initialize() -> None:
    sample: tuple[int, int] = clocks()
    state: Json = {"version": 1, "clock_ms": sample[0], "mono_ms": sample[1], "sessions": {}}
    if present(state_path()):
        state = load()
        state["clock_ms"] = max(sample[0], json_int(state["clock_ms"]))
        state["mono_ms"] = sample[1]
    save(state, False)
    return
