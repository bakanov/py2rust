"""Persistent scenario state and a bounded chronological request transcript."""

from routes import text

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("MOCK_STATE", "mock-state.json")


def fresh(config: Json) -> Json:
    return {"scenario": text(config, "initial", ""), "sequence": 0, "transcript": []}


def save(state: Json) -> None:
    write_text_atomic(state_path(), pretty(state))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load() -> Json:
    return json_loads(read_text(state_path()))


def initialize(config: Json) -> None:
    if not path_exists(state_path()):
        save(fresh(config))
    state: Json = load()
    declared: list[str] = []
    for item in json_array(config["states"]):
        declared.append(json_string(item))
    assert text(state, "scenario", "") in declared, "stored scenario no longer exists"
    sequence: int = json_int(state["sequence"])
    assert sequence >= 0, "negative transcript sequence"
    events: list[Json] = json_array(state["transcript"])
    assert len(events) == sequence, "transcript sequence mismatch"
    assert sequence <= 1000, "transcript exceeds the configured bound"
    expected: int = 1
    for event in events:
        assert json_int(event["sequence"]) == expected, "transcript is out of order"
        expected = expected + 1
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def record(state: Json, event: Json, following: str) -> Json:
    events: list[Json] = json_array(state["transcript"])
    sequence: int = json_int(state["sequence"]) + 1
    assert sequence <= 1000, "transcript full; reset before continuing"
    event["sequence"] = sequence
    event["before"] = text(state, "scenario", "")
    event["after"] = following
    events.append(event)
    result: Json = {"scenario": following, "sequence": sequence, "transcript": events}
    save(result)
    return result
