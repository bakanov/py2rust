"""Bounds for a local capture service with one active SMTP session."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_get,
    json_int,
    json_keys,
    json_loads,
    path_exists,
    read_text,
)


def configuration() -> Json:
    text: str = read_text(env_get("SMTP_CONFIG", "smtp.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_bytes": (1048576, 64, 1048576),
        "max_messages": (100, 1, 1000),
        "max_recipients": (100, 1, 100),
        "command_ms": (5000, 50, 30000),
        "data_ms": (15000, 50, 60000),
        "max_commands": (100, 5, 1000),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: Json = {}
    for key in bounds:  # noqa: PLC0206 - exercise the supported dictionary-key iterator
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    return policy


def stopping() -> bool:
    marker: str = env_get("SMTP_SHUTDOWN", "")
    return marker != "" and path_exists(marker)
