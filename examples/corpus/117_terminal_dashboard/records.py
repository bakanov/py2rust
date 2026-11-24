"""Observe monotonic snapshots and independently recompute archived frame contents."""

from layout import frame
from model import exact, settings, snapshot, text

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_is_null,
    json_loads_unique,
)


def observe(previous: Json, source: bytes, readable: bool) -> tuple[Json, str]:
    if not readable:
        return (previous, "unreadable")
    try:
        current: Json = snapshot(json_loads_unique(source.decode()))
        if not json_is_null(previous):
            sequence: int = json_int(current["sequence"])
            if sequence < json_int(previous["sequence"]):
                return (previous, "older sequence")
            if sequence == json_int(previous["sequence"]):
                if json_canonical(current) != json_canonical(previous):
                    return (previous, "conflicting sequence")
                return (previous, "unchanged")
        return (current, "updated")
    except Exception:  # noqa: BLE001 - recover an invalid snapshot and retain the last valid state
        return (previous, "invalid snapshot")


def event(
    source: bytes, readable: bool, state: Json, status: str, width: int, height: int, index: int, count: int
) -> Json:
    return {
        "source_hex": source.hex(),
        "readable": readable,
        "status": status,
        "columns": width,
        "rows": height,
        "lines": frame(state, width, height, index, count, status),
    }


def replay(archive: Json) -> tuple[Json, list[Json], Json, int]:
    exact(archive, ["version", "settings", "events", "signal"])
    assert json_int(archive["version"]) == 1, "archive version"
    config: Json = settings(archive["settings"])
    interrupted: int = json_int(archive["signal"])
    assert interrupted in [0, 2, 15], "archive signal"
    count: int = json_int(config["refreshes"])
    events: list[Json] = json_array(archive["events"])
    assert len(events) <= count and (len(events) == count or interrupted != 0), "archive frame count"
    state: Json = None
    for index in range(len(events)):
        stored: Json = events[index]
        exact(stored, ["source_hex", "readable", "status", "columns", "rows", "lines"])
        spelling: str = text(stored["source_hex"])
        assert len(spelling) <= 131072, "snapshot byte limit"
        raw: bytes = bytes.fromhex(spelling)
        readable: bool = json_bool(stored["readable"])
        assert raw.hex() == spelling and (readable or len(raw) == 0), "archive source encoding"
        width: int = json_int(stored["columns"])
        height: int = json_int(stored["rows"])
        assert 1 <= width <= json_int(config["columns"]) and 1 <= height <= 132, "archive dimensions"
        observed: tuple[Json, str] = observe(state, raw, readable)
        state = observed[0]
        computed: Json = event(raw, readable, state, observed[1], width, height, index + 1, count)
        assert json_canonical(computed) == json_canonical(stored), "archive differs from recomputed frame"
    return (config, events, state, interrupted)
