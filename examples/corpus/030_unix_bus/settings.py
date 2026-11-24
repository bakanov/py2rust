"""Explicit bounds and paths for a local command bus."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_get,
    json_int,
    json_keys,
    json_loads,
    path_exists,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
)


def configuration() -> dict[str, int]:
    text: str = read_text(env_get("BUS_CONFIG", "bus.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_peers": (32, 1, 128),
        "frame_bytes": (16384, 1024, 65536),
        "queue_bytes": (65536, 1028, 262144),
        "keys": (128, 1, 1024),
        "receipts": (256, 1, 1024),
        "value_bytes": (4096, 1, 8192),
        "session_ms": (60000, 100, 300000),
        "partial_ms": (3000, 50, 30000),
        "drain_ms": (1000, 50, 10000),
        "write_bytes": (65536, 1, 65536),
        "allow_stop": (0, 0, 1),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: dict[str, int] = {}
    for key in bounds:  # noqa: PLC0206 - supported dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    assert policy["queue_bytes"] >= policy["frame_bytes"] + 4, "queue cannot hold a frame"
    assert policy["frame_bytes"] >= policy["value_bytes"] * 2 + 512, "frame cannot hold an escaped value"
    return policy


def validate_paths() -> None:
    paths: list[str] = []
    for value in [
        env_get("BUS_SOCKET", "command.sock"),
        env_get("BUS_CONFIG", "bus.json"),
        env_get("BUS_REQUESTS", "requests.json"),
        env_get("BUS_REPORT", "report.json"),
        env_get("BUS_STOP", ""),
    ]:
        if value == "":
            continue
        current: str = path_join(path_resolve(path_parent(value)), path_name(value))
        for previous in paths:
            assert current != previous, "bus and control paths must be distinct"
            if path_exists(current) and path_exists(previous):
                assert not path_same(current, previous), "bus and control paths must not alias"
        paths.append(current)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
