"""Validate webhook envelopes and configuration before modifying receipt storage."""

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_parse,
    json_string,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("INBOX_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def valid_id(value: str) -> bool:
    return regex_fullmatch("[A-Za-z0-9_-]{1,100}", value)


def normalize(value: Json) -> Json:
    assert json_keys(value) == ["data", "id", "occurred_at", "source", "type"], "unexpected envelope fields"
    identifier: str = json_string(value["id"])
    kind: str = json_string(value["type"])
    source: str = json_string(value["source"])
    assert valid_id(identifier), "invalid event ID"
    assert regex_fullmatch("[A-Za-z0-9_.-]{1,80}", kind), "invalid event type"
    assert regex_fullmatch("[A-Za-z0-9_.-]{1,80}", source), "invalid event source"
    assert json_kind(value["data"]) == "object", "event data must be an object"
    stamp: DateTime = datetime_parse(json_string(value["occurred_at"]))
    return {"id": identifier, "type": kind, "source": source, "occurred_at": datetime_iso(stamp), "data": value["data"]}


def validate_configuration() -> None:
    assert setting("INBOX_LIMIT", 1000) > 0 and setting("INBOX_LIMIT", 1000) <= 10000, "invalid event limit"
    assert setting("INBOX_MAX_BODY", 65536) > 0 and setting("INBOX_MAX_BODY", 65536) <= 1048576, "invalid body limit"
    assert (
        setting("INBOX_MAX_STATE", 8388608) > 0 and setting("INBOX_MAX_STATE", 8388608) <= 33554432
    ), "invalid snapshot limit"
    assert setting("INBOX_PORT", 8768) >= 0 and setting("INBOX_PORT", 8768) <= 65535, "invalid port"
    assert clock() >= 0.0, "clock must be nonnegative"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
