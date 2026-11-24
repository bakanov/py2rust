"""Explicit limits for peers, lines, queues and event-loop work."""

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
    text: str = read_text(env_get("ROOM_CONFIG", "rooms.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    defaults: Json = {
        "max_peers": 32,
        "max_rooms": 16,
        "line_bytes": 2048,
        "queue_bytes": 16384,
        "queue_lines": 128,
        "commands_per_tick": 8,
        "write_bytes": 16384,
        "send_buffer": 8192,
        "partial_ms": 3000,
        "idle_ms": 60000,
        "close_ms": 200,
    }
    for key in json_keys(raw):
        assert key in defaults, "unknown setting"
    bounds: Json = {
        "max_peers": [1, 64],
        "max_rooms": [1, 32],
        "line_bytes": [64, 4096],
        "queue_bytes": [4096, 262144],
        "queue_lines": [4, 1024],
        "commands_per_tick": [1, 32],
        "write_bytes": [1, 65536],
        "send_buffer": [1024, 65536],
        "partial_ms": [50, 30000],
        "idle_ms": [100, 300000],
        "close_ms": [50, 5000],
    }
    for key in json_keys(defaults):
        value: int = json_int(json_get(raw, key, defaults[key]))
        assert value >= json_int(bounds[key][0]) and value <= json_int(bounds[key][1]), "setting outside bounds"
        defaults[key] = value
    assert json_int(defaults["queue_bytes"]) >= json_int(defaults["line_bytes"]) + 128, "queue cannot hold a message"
    return defaults


def stopping() -> bool:
    marker: str = env_get("ROOM_STOP", "")
    return marker != "" and path_exists(marker)
