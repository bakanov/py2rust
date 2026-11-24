"""Snapshot policy and normalized UTC observation times."""

from changes import pointer

from py2rust.stdlib import (
    Json,
    datetime_iso,
    datetime_parse,
    env_get,
    json_array,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    read_text,
    url_resolve,
    utc_now,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def clock() -> str:
    value: str = env_get("WATCH_NOW", "")
    if value == "":
        return datetime_iso(utc_now())
    return datetime_iso(datetime_parse(value))


def configuration() -> Json:
    text: str = read_text(env_get("WATCH_CONFIG", "watch.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in [
            "url",
            "ignore",
            "retain",
            "max_changes",
            "max_body",
            "timeout_ms",
            "interval_ms",
        ], "unknown setting"
    ignored: list[str] = []
    for item in json_array(json_get(value, "ignore", [])):
        path: str = pointer(json_string(item))
        assert path not in ignored, "duplicate ignored path"
        ignored.append(path)
    assert len(ignored) <= 100, "too many ignored paths"
    ignored.sort()
    retain: int = json_int(json_get(value, "retain", 20))
    changes: int = json_int(json_get(value, "max_changes", 100))
    body: int = json_int(json_get(value, "max_body", 65536))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    interval: int = json_int(json_get(value, "interval_ms", 1000))
    assert retain >= 1 and retain <= 100 and changes >= 1 and changes <= 1000, "invalid history bounds"
    assert body >= 1 and body <= 262144 and timeout >= 1 and timeout <= 30000, "invalid HTTP bounds"
    assert interval >= 1 and interval <= 60000, "invalid poll interval"
    return {
        "url": url_resolve(json_string(value["url"]), ""),
        "ignore": ignored,
        "retain": retain,
        "max_changes": changes,
        "max_body": body,
        "timeout_ms": timeout,
        "interval_ms": interval,
    }


def ignored_paths(policy: Json) -> list[str]:
    paths: list[str] = []
    for value in json_array(policy["ignore"]):
        paths.append(json_string(value))
    return paths
