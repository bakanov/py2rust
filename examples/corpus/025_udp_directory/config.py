"""Finite datagrams, retained sequence records, retries and protected report paths."""

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


def clock_ms() -> int:
    path: str = env_get("DIR_CLOCK", "")
    value: int = ceil(unix_time() * 1000.0)
    if path != "":
        value = json_int(json_loads(read_text(path)))
    assert value >= 0 and value <= 253402214400000, "invalid directory clock"
    return value


def stopping() -> bool:
    path: str = env_get("DIR_STOP", "")
    return path != "" and path_exists(path)


def configuration(mode: str) -> Json:
    assert mode in ["serve", "client"], "invalid directory mode"
    paths: list[str] = [env_get("DIR_CONFIG", "directory.json")]
    output: str = env_get("DIR_REGISTRY", "registry.json")
    if mode == "client":
        paths.append(env_get("DIR_REQUESTS", "requests.json"))
        output = env_get("DIR_REPORT", "client-report.json")
    else:
        for option in ["DIR_CLOCK", "DIR_STOP"]:
            if env_get(option, "") != "":
                paths.append(env_get(option, ""))
    paths.append(output)
    assert not path_is_symlink(output), "report must not be a symlink"
    seen: set[str] = set()
    for index in range(len(paths)):
        name: str = path_join(path_resolve(path_parent(paths[index])), path_name(paths[index]))
        assert name not in seen, "directory paths overlap"
        seen.add(name)
        for previous in range(index):
            if path_exists(paths[index]) and path_exists(paths[previous]):
                assert not path_same(paths[index], paths[previous]), "directory paths alias"
    text: str = read_text(paths[0])
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_services": (100, 1, 100),
        "remember_ms": (60000, 100, 3600000),
        "max_datagram": (4096, 1024, 4096),
        "reply_ms": (200, 20, 5000),
        "attempts": (3, 1, 5),
    }
    policy: Json = {}
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    for key in bounds:  # noqa: PLC0206 - use the supported dictionary-key iterator
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    return policy
