"""Strict event envelopes and configurable finite-state transition rules."""

from dataclasses import dataclass
from enum import Enum

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    regex_fullmatch,
)


class Code(Enum):
    INVALID_RECORD = "invalid_record"
    OVERSIZED_RECORD = "oversized_record"
    DUPLICATE_ID = "duplicate_id"
    CONFLICTING_ID = "conflicting_id"
    DUPLICATE_SEQUENCE = "duplicate_sequence"
    BEFORE_START = "sequence_before_start"
    GAP = "sequence_gap"
    OUT_OF_ORDER = "sequence_out_of_order"
    STREAM_TIME = "stream_time_regression"
    GLOBAL_TIME = "global_time_regression"
    STATE_MISMATCH = "state_mismatch"
    TRANSITION = "invalid_transition"


@dataclass
class Parsed:
    value: Json
    errors: list[str]


@dataclass
class Stream:
    high: int
    high_line: int
    clock: str
    clock_line: int
    state: str
    state_line: int
    first_line: int
    events: int


def issue(code: Code, details: Json) -> Json:
    return {"code": code.value, "details": details}


def fields(value: Json, expected: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(expected), "unexpected configuration fields"
    return  # noqa: PLR1711


def validate_config(config: Json) -> set[tuple[str, str]]:
    fields(
        config,
        [
            "input",
            "output",
            "states",
            "initial_state",
            "transitions",
            "first_sequence",
            "global_time_order",
            "max_streams",
            "max_records",
            "max_line_bytes",
            "max_input_bytes",
        ],
    )
    states: set[str] = set()
    for value in json_array(config["states"]):
        name: str = json_string(value)
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name) and name not in states, "invalid or duplicate state"
        states.add(name)
    assert 1 <= len(states) <= 32 and json_string(config["initial_state"]) in states, "invalid state configuration"
    transitions: set[tuple[str, str]] = set()
    for item in json_array(config["transitions"]):
        fields(item, ["from", "to"])
        pair: tuple[str, str] = (json_string(item["from"]), json_string(item["to"]))
        assert pair[0] in states and pair[1] in states and pair not in transitions, "invalid or duplicate transition"
        transitions.add(pair)
    assert json_int(config["first_sequence"]) >= 1, "first sequence must be positive"
    json_bool(config["global_time_order"])
    assert 1 <= json_int(config["max_streams"]) <= 1000, "stream limit must be 1..1000"
    assert 1 <= json_int(config["max_records"]) <= 10000, "record limit must be 1..10000"
    assert 1 <= json_int(config["max_line_bytes"]) <= 65536, "line limit must be 1..65536"
    assert 1 <= json_int(config["max_input_bytes"]) <= 8388608, "input limit must be 1..8 MiB"
    return transitions


def payload_nodes(value: Json, depth: int) -> int:
    assert depth <= 16, "payload nesting exceeds 16"
    count: int = 1
    if json_kind(value) == "object":
        for name in json_keys(value):
            count = count + payload_nodes(value[name], depth + 1)
            assert count <= 1000, "payload exceeds 1000 nodes"
    elif json_kind(value) == "array":
        for child in json_array(value):
            count = count + payload_nodes(child, depth + 1)
            assert count <= 1000, "payload exceeds 1000 nodes"
    return count


def parse(raw: bytes, states: list[Json]) -> Parsed:
    event: Json = None
    try:
        event = json_loads(raw.decode())
    except Exception:  # noqa: BLE001 - retain stable field diagnostics across runtimes
        return Parsed(None, ["json_or_utf8"])
    if json_kind(event) != "object":
        return Parsed(None, ["object"])
    required: list[str] = ["id", "stream", "sequence", "time", "from", "to"]
    errors: list[str] = []
    for name in required:
        if name not in event:
            errors.append("missing:" + name)
    for name in json_keys(event):
        if name not in required and name != "data":
            errors.append("unknown:" + name)
    if len(errors) > 0:
        return Parsed(None, errors)
    normalized: Json = {}
    required.append("data")
    for name in required:
        try:
            value: Json = json_get(event, name, None)
            if name in ["id", "stream"]:
                text: str = json_string(value)
                assert 1 <= len(text.encode()) <= 128 and text.strip() == text
                assert regex_fullmatch("[^\x00-\x1f\x7f]+", text)
            elif name == "sequence":
                assert json_int(value) >= 1
            elif name == "time":
                value = datetime_iso(datetime_parse(json_string(value)))
            elif name in ["from", "to"]:
                assert json_string(value) in states
            else:
                payload_nodes(value, 0)
            normalized[name] = value
        except Exception:  # noqa: BLE001 - retain stable field diagnostics across runtimes
            errors.append(name)
    return Parsed(normalized if len(errors) == 0 else None, errors)
