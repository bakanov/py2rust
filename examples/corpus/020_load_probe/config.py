"""Validate a finite load schedule and give every request a stable, ordered identity."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    url_resolve,
)


def target(raw: Json) -> Json:
    for key in json_keys(raw):
        assert key in ["id", "url", "method", "headers", "body_hex"], "unknown target field"
    identifier: str = json_string(raw["id"])
    assert regex_fullmatch("[A-Za-z0-9_-]{1,40}", identifier), "invalid target ID"
    method: str = json_string(json_get(raw, "method", "GET"))
    assert method in ["GET", "POST", "PUT", "DELETE"], "unsupported method"
    body: bytes = bytes.fromhex(json_string(json_get(raw, "body_hex", "")))
    assert len(body) <= 4096, "request body exceeds 4 KiB"
    incoming: Json = json_get(raw, "headers", {})
    headers: dict[str, str] = {}
    assert len(json_keys(incoming)) <= 16, "too many request headers"
    for name in json_keys(incoming):
        normalized: str = name.lower()
        value: str = json_string(incoming[name])
        assert regex_fullmatch("[!#$%&'*+.^_`|~0-9a-zA-Z-]+", name), "invalid header name"
        assert normalized not in headers, "duplicate header name"
        assert normalized not in ["host", "content-length", "transfer-encoding", "connection"], "managed header"
        assert len(value) <= 1024 and regex_fullmatch("[\t -~]*", value), "invalid header value"
        headers[normalized] = value
    return {
        "id": identifier,
        "url": url_resolve(json_string(raw["url"]), ""),
        "method": method,
        "headers": headers,
        "body_hex": body.hex(),
    }


def configuration() -> Json:
    text: str = read_text(env_get("LOAD_CONFIG", "load.json"))
    assert len(text.encode()) <= 1048576, "configuration exceeds 1 MiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in [
            "targets",
            "schedule",
            "concurrency",
            "timeout_ms",
            "max_body",
            "duration_ms",
            "max_lag_ms",
            "buckets_ms",
        ], "unknown setting"
    workers: int = json_int(json_get(value, "concurrency", 4))
    timeout: int = json_int(json_get(value, "timeout_ms", 2000))
    body: int = json_int(json_get(value, "max_body", 65536))
    duration: int = json_int(json_get(value, "duration_ms", 10000))
    lag: int = json_int(json_get(value, "max_lag_ms", 2000))
    assert workers >= 1 and workers <= 32 and timeout >= 1 and timeout <= 30000, "invalid worker or timeout limit"
    assert body >= 1 and body <= 1048576 and duration >= 1 and duration <= 120000, "invalid run or body limit"
    assert lag >= 0 and lag <= 60000, "invalid lateness limit"
    buckets: list[int] = []
    previous: int = 0
    for item in json_array(json_get(value, "buckets_ms", [10, 50, 100, 500, 1000])):
        bound: int = json_int(item)
        assert bound > previous and bound <= 120000, "latency bounds must be increasing positive milliseconds"
        buckets.append(bound)
        previous = bound
    assert len(buckets) >= 1 and len(buckets) <= 30, "expected 1–30 latency bounds"
    targets: list[Json] = []
    seen: set[str] = set()
    for item in json_array(value["targets"]):
        normalized: Json = target(item)
        identifier: str = json_string(normalized["id"])
        assert identifier not in seen, "duplicate target ID"
        seen.add(identifier)
        targets.append(normalized)
    assert len(targets) >= 1 and len(targets) <= 16, "expected 1–16 targets"
    schedule: list[Json] = json_array(value["schedule"])
    assert len(schedule) >= 1 and len(schedule) <= 100, "expected 1–100 schedule entries"
    jobs: list[Json] = []
    order: list[tuple[int, int]] = []
    for slot in range(len(schedule)):
        item: Json = schedule[slot]
        assert json_keys(item) == ["at_ms", "count", "interval_ms", "target"], "invalid schedule fields"
        name: str = json_string(item["target"])
        count: int = json_int(item["count"])
        at: int = json_int(item["at_ms"])
        interval: int = json_int(item["interval_ms"])
        assert name in seen and count >= 1 and count <= 1000, "invalid scheduled target or count"
        assert at >= 0 and interval >= 0 and interval <= 60000, "invalid schedule times"
        assert at + (count - 1) * interval < duration, "schedule extends beyond run duration"
        assert len(jobs) + count <= 1000, "schedule exceeds 1000 requests"
        for repeat in range(count):
            planned: int = at + repeat * interval
            order.append((planned, len(jobs)))
            jobs.append({"id": name + "-" + str(slot) + "-" + str(repeat), "target": name, "at_ms": planned})
    order.sort()
    ordered: list[Json] = []
    for pair in order:
        ordered.append(jobs[pair[1]])
    return {
        "targets": targets,
        "jobs": ordered,
        "concurrency": workers,
        "timeout_ms": timeout,
        "max_body": body,
        "duration_ms": duration,
        "max_lag_ms": lag,
        "buckets_ms": buckets,
    }


def lookup(policy: Json, identifier: str) -> Json:
    for item in json_array(policy["targets"]):
        if json_string(item["id"]) == identifier:
            return item
    assert False, "scheduled target does not exist"
    return None
