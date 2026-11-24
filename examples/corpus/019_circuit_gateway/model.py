"""Fixed upstream routes and bounded circuit policy; the clock can be supplied by a fixture."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    unix_time,
    url_resolve,
)


def clock() -> float:
    source: str = env_get("GATEWAY_CLOCK", "")
    now: float = unix_time()
    if source != "":
        now = json_float(json_loads(read_text(source)))
    assert now >= 0.0 and now <= 253402200000.0, "invalid clock"
    return now


def configuration() -> Json:
    text: str = read_text(env_get("GATEWAY_CONFIG", "gateway.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in ["routes", "threshold", "cooldown", "probes", "timeout_ms", "max_body"], "unknown setting"
    threshold: int = json_int(json_get(value, "threshold", 3))
    cooldown: float = json_float(json_get(value, "cooldown", 5.0))
    probes: int = json_int(json_get(value, "probes", 2))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    body: int = json_int(json_get(value, "max_body", 65536))
    assert threshold >= 1 and threshold <= 20 and probes >= 1 and probes <= 10, "invalid circuit thresholds"
    assert cooldown >= 0.01 and cooldown <= 3600.0, "invalid cooldown"
    assert timeout >= 1 and timeout <= 10000 and body >= 1 and body <= 1048576, "invalid HTTP limits"
    routes: list[Json] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for raw in json_array(value["routes"]):
        assert json_keys(raw) == ["id", "methods", "path", "url"], "invalid route fields"
        identifier: str = json_string(raw["id"])
        path: str = json_string(raw["path"])
        url: str = json_string(raw["url"])
        assert regex_fullmatch("[A-Za-z0-9_-]{1,40}", identifier) and identifier not in ids, "invalid or duplicate ID"
        assert regex_fullmatch("/[A-Za-z0-9/_-]{0,127}", path) and path not in paths, "invalid or duplicate route path"
        assert "//" not in path and not path.startswith("/_gateway"), "reserved or ambiguous route"
        assert "?" not in url and "#" not in url, "upstream URL must not include query or fragment"
        methods: list[str] = []
        for item in json_array(raw["methods"]):
            method: str = json_string(item)
            assert method in ["GET", "POST", "PUT", "DELETE"] and method not in methods, "invalid route method"
            methods.append(method)
        assert len(methods) > 0, "route requires a method"
        ids.add(identifier)
        paths.add(path)
        routes.append({"id": identifier, "path": path, "url": url_resolve(url, ""), "methods": methods})
    assert len(routes) >= 1 and len(routes) <= 16, "expected 1–16 routes"
    return {
        "routes": routes,
        "threshold": threshold,
        "cooldown": cooldown,
        "probes": probes,
        "timeout_ms": timeout,
        "max_body": body,
    }


def forwarded_headers(source: dict[str, str], names: list[str]) -> dict[str, str]:
    blocked: list[str] = []
    for token in source.get("connection", "").split(","):
        blocked.append(token.strip().lower())
    result: dict[str, str] = {}
    for name in names:
        if name in source and name not in blocked:
            result[name] = source[name]
    return result
