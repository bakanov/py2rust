"""A bounded replay log with durable IDs and publication deduplication."""

from model import clock, publication, setting

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("BOARD_STATE", "notification-board.json")


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 16777216, "snapshot exceeds 16 MiB"
    write_text_atomic(state_path(), text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load() -> Json:
    text: str = read_text(state_path())
    assert len(text.encode()) <= 16777216, "snapshot exceeds 16 MiB"
    return json_loads(text)


def initialize() -> None:
    if not path_exists(state_path()):
        save({"version": 1, "last": 0, "clock": clock(), "events": []})
    state: Json = load()
    assert json_keys(state) == ["clock", "events", "last", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1, "unsupported snapshot version"
    last: int = json_int(state["last"])
    assert last >= 0 and last <= 999999999999999999, "invalid sequence"
    observed: float = json_float(state["clock"])
    assert observed >= 0.0 and observed <= 253402214400.0, "invalid stored clock"
    events: list[Json] = json_array(state["events"])
    assert len(events) <= setting("BOARD_RETAIN", 128) and len(events) <= last, "invalid retained count"
    assert last == 0 or len(events) > 0, "missing retained tail"
    expected: int = last - len(events) + 1
    keys: set[str] = set()
    previous_time: float = 0.0
    for record in events:
        assert json_keys(record) == ["created", "data", "id", "key", "topic"], "invalid event fields"
        assert json_int(record["id"]) == expected, "noncontiguous event IDs"
        value: Json = {"key": record["key"], "topic": record["topic"], "data": record["data"]}
        assert json_equal(publication(value), value), "invalid stored publication"
        key: str = json_string(record["key"])
        assert key not in keys, "duplicate publication key"
        keys.add(key)
        created: float = json_float(record["created"])
        assert created >= previous_time and created <= observed, "invalid event time"
        previous_time = created
        expected = expected + 1
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def bounds(state: Json) -> Json:
    events: list[Json] = json_array(state["events"])
    last: int = json_int(state["last"])
    return {"oldest": last - len(events) + 1, "last": last, "retained": len(events)}


def cursor_valid(state: Json, after: int) -> bool:
    limits: Json = bounds(state)
    return after >= json_int(limits["oldest"]) - 1 and after <= json_int(limits["last"])


def find_key(state: Json, key: str) -> Json:
    for record in json_array(state["events"]):
        if json_string(record["key"]) == key:
            return record
    return None


def append(state: Json, value: Json) -> Json:
    last: int = json_int(state["last"])
    assert last < 999999999999999999, "event IDs exhausted"
    now: float = max(clock(), json_float(state["clock"]))
    record: Json = {
        "id": last + 1,
        "key": value["key"],
        "topic": value["topic"],
        "data": value["data"],
        "created": now,
    }
    events: list[Json] = json_array(state["events"])
    events.append(record)
    retained: list[Json] = []
    for index in range(max(0, len(events) - setting("BOARD_RETAIN", 128)), len(events)):
        retained.append(events[index])
    save({"version": 1, "last": last + 1, "clock": now, "events": retained})
    return record
