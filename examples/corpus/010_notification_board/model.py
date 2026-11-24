"""Validate publications and encode the board's documented SSE event format."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_dumps,
    json_float,
    json_int,
    json_keys,
    json_loads,
    json_string,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def clock() -> float:
    configured: str = env_get("BOARD_NOW", "")
    if configured != "":
        return json_float(json_loads(configured))
    return unix_time()


def configure() -> None:
    assert setting("BOARD_PORT", 8775) >= 0 and setting("BOARD_PORT", 8775) <= 65535, "invalid port"
    assert setting("BOARD_RETAIN", 128) >= 1 and setting("BOARD_RETAIN", 128) <= 1000, "invalid retention"
    assert setting("BOARD_POLL", 50) >= 1 and setting("BOARD_POLL", 50) <= 1000, "invalid poll interval"
    assert clock() >= 0.0 and clock() <= 253402214400.0, "invalid clock"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def valid_name(value: str) -> bool:
    return regex_fullmatch("[A-Za-z0-9_-]{1,64}", value)


def publication(value: Json) -> Json:
    assert json_keys(value) == ["data", "key", "topic"], "expected key, topic and data"
    key: str = json_string(value["key"])
    topic: str = json_string(value["topic"])
    assert valid_name(key) and valid_name(topic), "invalid key or topic"
    assert len(json_dumps(value["data"]).encode()) <= 8192, "event data exceeds 8 KiB"
    return {"key": key, "topic": topic, "data": value["data"]}


def decimal(value: str) -> int:
    assert regex_fullmatch("0|[1-9][0-9]{0,17}", value), "expected a nonnegative decimal integer"
    return json_int(json_loads(value))


def event_frame(record: Json) -> bytes:
    # Compact JSON escapes embedded newlines, preventing injected SSE fields.
    text: str = "id: " + str(json_int(record["id"])) + "\nevent: notification\ndata: " + json_dumps(record) + "\n\n"
    return text.encode()


def gap_frame(bounds: Json) -> bytes:
    return ("event: gap\ndata: " + json_dumps(bounds) + "\n\n").encode()
