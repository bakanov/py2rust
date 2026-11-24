"""Three explicit versions of a small network-service configuration schema."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


def exact_keys(value: Json, expected: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert len(json_keys(value)) == len(expected), "unexpected or missing fields"
    for key in expected:
        assert key in value, "missing field: " + key
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_address(host: str, port: int) -> None:
    assert len(host) > 0 and len(host) <= 253, "invalid host length"
    assert regex_fullmatch("[A-Za-z0-9.:-]+", host), "invalid host characters"
    assert port > 0 and port <= 65535, "port out of range"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_tags(value: Json) -> None:
    tags: list[Json] = json_array(value)
    assert len(tags) <= 100, "too many tags"
    seen: set[str] = set()
    for item in tags:
        tag: str = json_string(item)
        assert regex_fullmatch("[A-Za-z0-9_-]{1,64}", tag), "invalid tag"
        assert tag not in seen, "duplicate tag"
        seen.add(tag)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_log(value: Json) -> None:
    exact_keys(value, ["level"])
    assert json_string(value["level"]) in ["DEBUG", "INFO", "WARNING", "ERROR"], "invalid logging level"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate(value: Json) -> int:
    version: int = json_int(value["version"])
    if version == 1:
        exact_keys(value, ["version", "host", "port", "debug", "timeout", "tags"])
        validate_address(json_string(value["host"]), json_int(value["port"]))
        json_bool(value["debug"])
        seconds: int = json_int(value["timeout"])
        assert seconds >= 1 and seconds <= 3600, "timeout out of range"
        validate_tags(value["tags"])
        return version
    if version == 2:
        exact_keys(value, ["version", "listen", "logging", "timeout_ms", "tags"])
        exact_keys(value["listen"], ["host", "port"])
        validate_address(json_string(value["listen"]["host"]), json_int(value["listen"]["port"]))
        validate_log(value["logging"])
        milliseconds: int = json_int(value["timeout_ms"])
        assert milliseconds >= 1 and milliseconds <= 3600000, "timeout out of range"
        validate_tags(value["tags"])
        return version
    assert version == 3, "unsupported schema version"
    exact_keys(value, ["version", "server", "logging", "labels"])
    exact_keys(value["server"], ["bind", "port", "timeout_ms"])
    validate_address(json_string(value["server"]["bind"]), json_int(value["server"]["port"]))
    validate_log(value["logging"])
    milliseconds: int = json_int(value["server"]["timeout_ms"])
    assert milliseconds >= 1 and milliseconds <= 3600000, "timeout out of range"
    labels: list[str] = json_keys(value["labels"])
    assert len(labels) <= 100, "too many labels"
    for label in labels:
        assert regex_fullmatch("[A-Za-z0-9_-]{1,64}", label), "invalid label"
        assert json_bool(value["labels"][label]), "labels must be enabled"
    return version


def migrate_one(value: Json) -> Json:
    version: int = validate(value)
    if version == 1:
        level: str = "INFO"
        if json_bool(value["debug"]):
            level = "DEBUG"
        return {
            "version": 2,
            "listen": {"host": value["host"], "port": value["port"]},
            "logging": {"level": level},
            "timeout_ms": json_int(value["timeout"]) * 1000,
            "tags": value["tags"],
        }
    assert version == 2, "no migration available for current schema"
    labels: Json = {}
    for tag in json_array(value["tags"]):
        labels[json_string(tag)] = True
    return {
        "version": 3,
        "server": {"bind": value["listen"]["host"], "port": value["listen"]["port"], "timeout_ms": value["timeout_ms"]},
        "logging": value["logging"],
        "labels": labels,
    }


def upgrade(value: Json) -> Json:
    current: Json = value
    version: int = validate(current)
    while version < 3:
        current = migrate_one(current)
        following: int = validate(current)
        assert following == version + 1, "migration did not advance exactly one version"
        version = following
    return current
