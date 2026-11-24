"""Explicit budgets and separate input, snapshot and shutdown paths."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_get,
    json_int,
    json_keys,
    json_loads,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
)


def snapshot() -> str:
    return env_get("MQTT_STATE", "telemetry.json")


def configuration() -> dict[str, int]:
    paths: list[str] = [snapshot(), env_get("MQTT_CONFIG", "sink.json")]
    if env_get("MQTT_STOP", "") != "":
        paths.append(env_get("MQTT_STOP", ""))
    seen: set[str] = set()
    for index in range(len(paths)):
        name: str = path_join(path_resolve(path_parent(paths[index])), path_name(paths[index]))
        assert name not in seen, "configuration paths overlap"
        seen.add(name)
        for prior in range(index):
            if path_exists(paths[index]) and path_exists(paths[prior]):
                assert not path_same(paths[index], paths[prior]), "configuration paths alias"
    assert not path_is_symlink(snapshot()), "snapshot must not be a symlink"
    source: str = read_text(paths[1])
    assert len(source.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(source)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_peers": (16, 1, 64),
        "max_topics": (64, 1, 256),
        "history": (16, 1, 128),
        "topic_bytes": (256, 1, 1024),
        "payload_bytes": (16384, 0, 65536),
        "total_bytes": (1048576, 64, 1048576),
        "packet_bytes": (66562, 13, 131072),
        "queue_bytes": (4096, 64, 65536),
        "packets_per_tick": (4, 1, 32),
        "write_bytes": (4096, 1, 65536),
        "handshake_ms": (3000, 50, 30000),
        "partial_ms": (3000, 50, 30000),
        "close_ms": (300, 50, 5000),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: dict[str, int] = {}
    for key in bounds:  # noqa: PLC0206 - supported dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    assert policy["packet_bytes"] >= policy["topic_bytes"] + policy["payload_bytes"] + 2, "packet budget too small"
    policy["port"] = json_int(json_loads(env_get("MQTT_PORT", "8792")))
    assert policy["port"] >= 0 and policy["port"] <= 65535, "invalid port"
    return policy
