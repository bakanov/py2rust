"""Finite limits and non-overlapping configuration, clock, stop and snapshot files."""

from py2rust.stdlib import (
    Json,
    ceil,
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
    unix_time,
)


def snapshot() -> str:
    return env_get("KV_STATE", "kv-state.json")


def stopping() -> bool:
    marker: str = env_get("KV_STOP", "")
    return marker != "" and path_exists(marker)


def clock_ms() -> int:
    path: str = env_get("KV_CLOCK", "")
    now: int = ceil(unix_time() * 1000.0)
    if path != "":
        now = json_int(json_loads(read_text(path)))
    assert now >= 0 and now <= 253402214400000, "invalid millisecond clock"
    return now


def configuration() -> Json:
    paths: list[str] = [snapshot(), env_get("KV_CONFIG", "kv.json")]
    for option in ["KV_STOP", "KV_CLOCK"]:
        if env_get(option, "") != "":
            paths.append(env_get(option, ""))
    seen: set[str] = set()
    for index in range(len(paths)):
        name: str = path_join(path_resolve(path_parent(paths[index])), path_name(paths[index]))
        assert name not in seen, "configuration paths overlap"
        seen.add(name)
        for prior in range(index):
            if path_exists(paths[index]) and path_exists(paths[prior]):
                assert not path_same(paths[index], paths[prior]), "configuration paths alias"
    assert not path_is_symlink(snapshot()), "snapshot must not be a symlink"
    text: str = read_text(paths[1])
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_keys": (1000, 1, 1000),
        "max_key": (256, 1, 256),
        "max_value": (65536, 32, 65536),
        "max_total": (1048576, 64, 2097152),
        "max_peers": (16, 1, 32),
        "frame_ms": (3000, 50, 30000),
        "idle_ms": (30000, 100, 300000),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: Json = {}
    for key in bounds:  # noqa: PLC0206 - dictionary-key iteration is part of the source subset
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    clock_ms()
    return policy
