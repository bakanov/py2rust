"""Configuration and deterministic clock seam for the file-drop service."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_float,
    json_int,
    json_kind,
    json_parse,
    unix_time,
)


def setting_integer(name: str, fallback: int) -> int:
    value: Json = json_parse(env_get(name, str(fallback)), None)
    assert json_kind(value) == "number", "setting must be a JSON integer"
    return json_int(value)


def data_directory() -> str:
    return env_get("DROP_DATA", "data")


def maximum_size() -> int:
    return setting_integer("DROP_MAX_BYTES", 1048576)


def default_lifetime() -> int:
    return setting_integer("DROP_TTL", 3600)


def now() -> float:
    supplied: str = env_get("DROP_NOW", "")
    if supplied != "":
        return json_float(json_parse(supplied, None))
    return unix_time()


def validate_configuration() -> None:
    assert maximum_size() > 0, "DROP_MAX_BYTES must be positive"
    assert maximum_size() <= 33554432, "DROP_MAX_BYTES exceeds the HTTP body limit"
    assert default_lifetime() > 0, "DROP_TTL must be positive"
    assert default_lifetime() <= 86400, "DROP_TTL exceeds one day"
    assert len(data_directory()) > 0, "DROP_DATA cannot be empty"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
