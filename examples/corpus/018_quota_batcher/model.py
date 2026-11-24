"""One origin, stable request identities, bounded JSON results and explicit policy."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    unix_time,
    url_origin,
    url_resolve,
)


def clock() -> float:
    value: str = env_get("BATCH_NOW", "")
    now: float = unix_time()
    if value != "":
        now = json_float(json_loads(value))
    assert now >= 0.0 and now <= 253402200000.0, "clock outside supported range"
    return now


def configuration() -> Json:
    text: str = read_text(env_get("BATCH_CONFIG", "batch.json"))
    assert len(text.encode()) <= 16384, "configuration exceeds 16 KiB"
    value: Json = json_loads(text)
    for name in json_keys(value):
        assert name in ["base_url", "attempts", "backoff", "timeout_ms", "max_body"], "unknown setting"
    attempts: int = json_int(json_get(value, "attempts", 4))
    backoff: int = json_int(json_get(value, "backoff", 2))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    body: int = json_int(json_get(value, "max_body", 65536))
    assert attempts >= 1 and attempts <= 8 and backoff >= 1 and backoff <= 3600, "invalid retry policy"
    assert timeout >= 1 and timeout <= 30000 and body >= 1 and body <= 65536, "invalid HTTP bounds"
    return {
        "base_url": url_resolve(json_string(value["base_url"]), ""),
        "attempts": attempts,
        "backoff": backoff,
        "timeout_ms": timeout,
        "max_body": body,
    }


def normalize_job(raw: Json, policy: Json) -> Json:
    assert json_keys(raw) == ["id", "url"], "requests require exactly id and url"
    identifier: str = json_string(raw["id"])
    assert regex_fullmatch("[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", identifier), "invalid request ID"
    base: str = json_string(policy["base_url"])
    url: str = url_resolve(base, json_string(raw["url"]))
    assert url_origin(url) == url_origin(base), "request must remain on the configured origin"
    return {"id": identifier, "url": url}


def new_entry(job: Json) -> Json:
    return {
        "job": job,
        "state": "pending",
        "attempts": 0,
        "next_at": 0.0,
        "last_at": 0.0,
        "status": 0,
        "error": "",
        "result": None,
    }


def delay(policy: Json, attempts: int) -> float:
    seconds: int = json_int(policy["backoff"])
    for index in range(1, attempts):
        seconds = min(seconds * 2, 3600)
    return json_float(seconds)


def result_nodes(value: Json, depth: int) -> int:
    assert depth <= 24, "JSON result exceeds 24 levels"
    count: int = 1
    if json_kind(value) == "object":
        for name in json_keys(value):
            count = count + result_nodes(value[name], depth + 1)
    elif json_kind(value) == "array":
        for item in json_array(value):
            count = count + result_nodes(item, depth + 1)
    assert count <= 4096, "JSON result exceeds 4096 nodes"
    return count
