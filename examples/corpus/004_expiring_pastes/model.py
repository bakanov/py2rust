"""Paste validation, public metadata and separate read/delete capabilities."""

import hmac

from py2rust.stdlib import (
    Json,
    env_get,
    json_float,
    json_int,
    json_keys,
    json_parse,
    json_string,
    regex_fullmatch,
    regex_search,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("PASTE_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def valid_token(value: str) -> bool:
    return regex_fullmatch("[a-f0-9]{64}", value)


def matches(provided: str, expected: str) -> bool:
    if not valid_token(provided) or not valid_token(expected):
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def normalize(value: Json) -> Json:
    assert json_keys(value) == ["text", "title", "ttl", "visibility"], "unexpected paste fields"
    text: str = json_string(value["text"])
    title: str = json_string(value["title"]).strip()
    visibility: str = json_string(value["visibility"])
    ttl: int = json_int(value["ttl"])
    assert len(text.encode()) <= setting("PASTE_MAX_BYTES", 65536), "paste text exceeds byte limit"
    assert "\x00" not in text, "text cannot contain NUL"
    assert len(title) > 0 and len(title) <= 120, "invalid title length"
    assert not regex_search("[\\x00-\\x1f\\x7f]", title), "invalid title characters"
    assert visibility == "public" or visibility == "private", "invalid visibility"
    assert ttl >= 1 and ttl <= 86400, "TTL must be between one second and one day"
    return {"text": text, "title": title, "visibility": visibility, "ttl": ttl}


def metadata(record: Json) -> Json:
    return {
        "id": record["id"],
        "title": record["title"],
        "visibility": record["visibility"],
        "size": record["size"],
        "created": record["created"],
        "expires": record["expires"],
    }


def can_read(record: Json, key: str) -> bool:
    return (
        json_string(record["visibility"]) == "public"
        or matches(key, json_string(record["read_key"]))
        or matches(key, json_string(record["delete_key"]))
    )


def validate_record(record: Json) -> None:
    assert json_keys(record) == [
        "created",
        "delete_key",
        "expires",
        "id",
        "read_key",
        "size",
        "text",
        "title",
        "visibility",
    ], "invalid stored fields"
    assert valid_token(json_string(record["id"])), "invalid stored ID"
    assert valid_token(json_string(record["delete_key"])), "invalid delete key"
    visibility: str = json_string(record["visibility"])
    read_key: str = json_string(record["read_key"])
    if visibility == "private":
        assert valid_token(read_key), "invalid read key"
        assert read_key != json_string(record["delete_key"]), "read and delete keys must differ"
    else:
        assert visibility == "public" and read_key == "", "invalid visibility or public read key"
    normalize({"text": record["text"], "title": record["title"], "visibility": visibility, "ttl": 1})
    assert json_int(record["size"]) == len(json_string(record["text"]).encode()), "incorrect stored byte size"
    created: float = json_float(record["created"])
    expires: float = json_float(record["expires"])
    assert created >= 0.0 and expires > created and expires <= created + 86400.0, "invalid stored deadline"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def configure() -> None:
    assert setting("PASTE_LIMIT", 1000) >= 1 and setting("PASTE_LIMIT", 1000) <= 1000, "invalid count limit"
    assert setting("PASTE_MAX_BYTES", 65536) >= 1 and setting("PASTE_MAX_BYTES", 65536) <= 1048576, "invalid byte limit"
    assert (
        setting("PASTE_MAX_STATE", 8388608) >= 1024 and setting("PASTE_MAX_STATE", 8388608) <= 33554432
    ), "invalid snapshot limit"
    assert setting("PASTE_PORT", 8770) >= 0 and setting("PASTE_PORT", 8770) <= 65535, "invalid port"
    assert clock() >= 0.0 and clock() <= 253402214400.0, "clock outside supported range"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
