"""Validate the entire bounded batch and protect report destinations before I/O."""

from names import query_name

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    read_text,
    regex_fullmatch,
)


def configuration() -> Json:
    paths: list[str] = [
        env_get("DNS_CONFIG", "dns.json"),
        env_get("DNS_REPORT", "dns-report.json"),
        env_get("DNS_TEXT", "dns-report.txt"),
    ]
    seen: set[str] = set()
    for index in range(len(paths)):
        assert index == 0 or not path_is_symlink(paths[index]), "report must not be a symlink"
        path: str = path_join(path_resolve(path_parent(paths[index])), path_name(paths[index]))
        assert path not in seen, "DNS paths overlap"
        seen.add(path)
        for other in range(index):
            if path_exists(paths[index]) and path_exists(paths[other]):
                assert not path_same(paths[index], paths[other]), "DNS paths alias"
    text: str = read_text(paths[0])
    assert len(text.encode()) <= 65536, "DNS configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    for key in json_keys(raw):
        assert key in ["host", "port", "timeout_ms", "attempts", "queries"], "unknown DNS setting"
    host: str = json_string(json_get(raw, "host", "127.0.0.1"))
    parts: list[str] = host.split(".")
    assert len(parts) == 4, "DNS server must be numeric IPv4"
    for part in parts:
        assert regex_fullmatch("[0-9]{1,3}", part), "invalid IPv4 component"
        assert str(int(part)) == part and int(part) <= 255, "noncanonical IPv4 component"
    policy: Json = {"host": host}
    bounds: dict[str, tuple[int, int, int]] = {
        "port": (53, 1, 65535),
        "timeout_ms": (500, 20, 5000),
        "attempts": (3, 1, 5),
    }
    for key in bounds:  # noqa: PLC0206 - supported dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        number: int = json_int(json_get(raw, key, limits[0]))
        assert number >= limits[1] and number <= limits[2], "invalid setting: " + key
        policy[key] = number
    queries: list[Json] = []
    unique: set[str] = set()
    for item in json_array(raw["queries"]):
        assert json_keys(item) == ["name", "type"], "invalid query fields"
        name: str = query_name(json_string(item["name"]))
        kind: str = json_string(item["type"]).upper()
        assert kind in ["A", "AAAA"] and name + kind not in unique, "invalid or repeated query"
        unique.add(name + kind)
        queries.append({"name": name, "type": kind})
    assert len(queries) >= 1 and len(queries) <= 100, "batch needs 1..100 queries"
    policy["queries"] = queries
    return policy
