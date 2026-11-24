"""Validate endpoint policy and apply consecutive-failure/recovery rules."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def clock() -> float:
    configured: str = env_get("HEALTH_NOW", "")
    if configured != "":
        return json_float(json_loads(configured))
    return unix_time()


def normalize_url(value: str) -> str:
    assert len(value) <= 2048, "URL exceeds 2048 characters"
    assert regex_fullmatch(
        "https?://[A-Za-z0-9.-]+(:[1-9][0-9]{0,4})?/[A-Za-z0-9._~!$&'()*+,;=:@/?%-]*", value
    ), "invalid URL"
    scheme: str = value.split(":")[0]
    authority: str = value.split("/")[2].lower()
    host: str = authority.split(":")[0]
    assert len(host) <= 253, "hostname too long"
    for label in host.split("."):
        assert len(label) <= 63 and regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?", label), "invalid hostname"
    if regex_fullmatch("[0-9.]+", host):
        assert len(host.split(".")) == 4, "IPv4 needs four octets"
        for octet in host.split("."):
            assert regex_fullmatch("0|[1-9][0-9]{0,2}", octet), "invalid IPv4 octet"
            assert json_int(json_loads(octet)) <= 255, "invalid IPv4 octet"
    if ":" in authority:
        port: int = json_int(json_loads(authority.split(":")[1]))
        assert port <= 65535, "invalid port"
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            authority = host
    pieces: list[str] = value.split("%")
    for index in range(1, len(pieces)):
        assert len(pieces[index]) >= 2 and regex_fullmatch(
            "[0-9A-Fa-f]{2}", pieces[index][:2]
        ), "invalid percent escape"
    return scheme + "://" + authority + value[len(scheme) + 3 + len(value.split("/")[2]) :]


def configuration() -> Json:
    text: str = read_text(env_get("HEALTH_CONFIG", "health-endpoints.json"))
    assert len(text.encode()) <= 262144, "configuration exceeds 256 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in [
            "endpoints",
            "failure_threshold",
            "recovery_threshold",
            "retain",
            "timeout_ms",
            "max_body",
        ], "unknown setting"
    failures: int = json_int(json_get(value, "failure_threshold", 2))
    recoveries: int = json_int(json_get(value, "recovery_threshold", 2))
    retain: int = json_int(json_get(value, "retain", 20))
    timeout: int = json_int(json_get(value, "timeout_ms", 1000))
    maximum: int = json_int(json_get(value, "max_body", 65536))
    assert failures >= 1 and failures <= 20 and recoveries >= 1 and recoveries <= 20, "invalid threshold"
    assert retain >= 1 and retain <= 100, "invalid history limit"
    assert timeout >= 1 and timeout <= 30000 and maximum >= 1 and maximum <= 1048576, "invalid HTTP bounds"
    endpoints: list[Json] = []
    identifiers: set[str] = set()
    for endpoint in json_array(value["endpoints"]):
        for key in json_keys(endpoint):
            assert key in ["id", "url", "statuses"], "unknown endpoint field"
        identifier: str = json_string(endpoint["id"])
        assert (
            regex_fullmatch("[A-Za-z0-9_-]{1,64}", identifier) and identifier not in identifiers
        ), "invalid or duplicate endpoint ID"
        identifiers.add(identifier)
        statuses: list[int] = []
        for item in json_array(json_get(endpoint, "statuses", [200])):
            code: int = json_int(item)
            assert code >= 200 and code <= 599 and code not in statuses, "invalid or duplicate success status"
            statuses.append(code)
        assert len(statuses) > 0 and len(statuses) <= 20, "invalid success statuses"
        statuses.sort()
        endpoints.append({"id": identifier, "url": normalize_url(json_string(endpoint["url"])), "statuses": statuses})
    assert len(endpoints) > 0 and len(endpoints) <= 100, "invalid endpoint count"
    return {
        "endpoints": endpoints,
        "failure_threshold": failures,
        "recovery_threshold": recoveries,
        "retain": retain,
        "timeout_ms": timeout,
        "max_body": maximum,
    }


def fresh() -> Json:
    return {
        "phase": "unknown",
        "good_run": 0,
        "bad_run": 0,
        "first_bad": 0.0,
        "opened": None,
        "checks": 0,
        "failures": 0,
        "down_seconds": 0.0,
        "samples": [],
        "outages": [],
    }


def tail(values: list[Json], limit: int) -> list[Json]:
    result: list[Json] = []
    for index in range(max(0, len(values) - limit), len(values)):
        result.append(values[index])
    return result


def observe(record: Json, sample: Json, policy: Json) -> Json:
    now: float = json_float(sample["at"])
    record["checks"] = json_int(record["checks"]) + 1
    if json_bool(sample["ok"]):
        record["bad_run"] = 0
        record["first_bad"] = 0.0
        record["good_run"] = min(json_int(record["good_run"]) + 1, json_int(policy["recovery_threshold"]))
        if json_string(record["phase"]) != "down" or json_int(record["good_run"]) >= json_int(
            policy["recovery_threshold"]
        ):
            if json_string(record["phase"]) == "down":
                started: float = json_float(record["opened"])
                outages: list[Json] = json_array(record["outages"])
                outages.append({"start": started, "end": now, "seconds": now - started})
                record["outages"] = tail(outages, json_int(policy["retain"]))
                record["down_seconds"] = json_float(record["down_seconds"]) + (now - started)
            record["phase"] = "up"
            record["opened"] = None
    else:
        record["failures"] = json_int(record["failures"]) + 1
        record["good_run"] = 0
        if json_int(record["bad_run"]) == 0:
            record["first_bad"] = now
        record["bad_run"] = min(json_int(record["bad_run"]) + 1, json_int(policy["failure_threshold"]))
        if json_string(record["phase"]) != "down" and json_int(record["bad_run"]) >= json_int(
            policy["failure_threshold"]
        ):
            record["phase"] = "down"
            record["opened"] = record["first_bad"]
    samples: list[Json] = json_array(record["samples"])
    samples.append(sample)
    record["samples"] = tail(samples, json_int(policy["retain"]))
    return record


def status(record: Json) -> str:
    phase: str = json_string(record["phase"])
    if phase == "down" and json_int(record["good_run"]) > 0:
        return "recovering"
    if phase == "up" and json_int(record["bad_run"]) > 0:
        return "degraded"
    return phase
