"""Retained revision snapshots with a replay-checked audit trail."""

from enum import Enum

from schema import clock, defaults, differences, setting, validate_values

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


class ChangeKind(Enum):
    INITIAL = "initial"
    UPDATE = "update"
    ROLLBACK = "rollback"


def state_path() -> str:
    return env_get("SETTINGS_STATE", "settings-state.json")


def serialize(fields: list[Json], history: list[Json]) -> str:
    return pretty({"version": 1, "schema": fields, "history": history})


def save(fields: list[Json], history: list[Json]) -> None:
    content: str = serialize(fields, history)
    assert len(history) <= setting("SETTINGS_HISTORY", 100), "history count exceeds limit"
    assert len(content.encode()) <= 8388608, "history snapshot exceeds byte limit"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(fields: list[Json]) -> list[Json]:
    content: str = read_text(state_path())
    assert len(content.encode()) <= 8388608, "history snapshot exceeds byte limit"
    value: Json = json_loads(content)
    assert json_int(value["version"]) == 1, "unsupported history version"
    assert json_equal(value["schema"], fields), "configured schema differs from stored schema"
    history: list[Json] = json_array(value["history"])
    assert len(history) >= 1 and len(history) <= setting("SETTINGS_HISTORY", 100), "invalid history length"
    return history


def initialize(fields: list[Json]) -> None:
    if not path_exists(state_path()):
        values: Json = defaults(fields)
        entry: Json = {
            "revision": 0,
            "kind": ChangeKind.INITIAL.value,
            "source": 0,
            "timestamp": clock(),
            "values": values,
            "changed": json_keys(values),
        }
        save(fields, [entry])
    history: list[Json] = load(fields)
    before: Json = {}
    previous_time: float = 0.0
    for revision in range(len(history)):
        entry: Json = history[revision]
        assert json_keys(entry) == [
            "changed",
            "kind",
            "revision",
            "source",
            "timestamp",
            "values",
        ], "invalid history entry fields"
        assert json_int(entry["revision"]) == revision, "non-contiguous revision sequence"
        validate_values(fields, entry["values"])
        assert json_equal(entry["changed"], differences(before, entry["values"])), "incorrect changed-field audit"
        timestamp: float = json_float(entry["timestamp"])
        assert timestamp >= previous_time, "history clock moved backwards"
        kind: str = json_string(entry["kind"])
        source: int = json_int(entry["source"])
        if revision == 0:
            assert kind == ChangeKind.INITIAL.value and source == 0, "invalid initial revision"
            assert json_equal(entry["values"], defaults(fields)), "initial values differ from defaults"
        elif kind == ChangeKind.UPDATE.value:
            assert source == revision - 1 and len(differences(before, entry["values"])) > 0, "invalid update audit"
        else:
            assert kind == ChangeKind.ROLLBACK.value and source >= 0 and source < revision, "invalid rollback source"
            assert json_equal(entry["values"], history[source]["values"]), "rollback does not reconstruct source"
        before = entry["values"]
        previous_time = timestamp
    return  # noqa: PLR1711 - explicit return required by repository guidelines
