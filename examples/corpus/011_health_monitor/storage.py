"""Validate durable health history and protect configuration from report writes."""

from model import clock, fresh

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_float,
    json_int,
    json_is_null,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_resolve,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("HEALTH_STATE", "health-state.json")


def validate_paths() -> None:
    paths: list[str] = [
        env_get("HEALTH_CONFIG", "health-endpoints.json"),
        state_path(),
        state_path() + ".report.json",
        state_path() + ".report.txt",
    ]
    for first in range(len(paths)):
        for second in range(first + 1, len(paths)):
            assert paths[first] != paths[second], "configuration, state and reports must be separate files"
            if path_exists(paths[first]) and path_exists(paths[second]):
                assert path_resolve(paths[first]) != path_resolve(paths[second]), "file paths alias one another"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    write_text_atomic(state_path(), text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_record(record: Json, endpoint: Json, policy: Json, now: float) -> None:
    assert json_keys(record) == json_keys(fresh()), "invalid health record fields"
    phase: str = json_string(record["phase"])
    assert phase in ["unknown", "up", "down"], "invalid phase"
    checks: int = json_int(record["checks"])
    failures: int = json_int(record["failures"])
    good: int = json_int(record["good_run"])
    bad: int = json_int(record["bad_run"])
    assert checks >= 0 and failures >= 0 and failures <= checks, "invalid counters"
    assert good >= 0 and good <= json_int(policy["recovery_threshold"]), "invalid recovery run"
    assert bad >= 0 and bad <= json_int(policy["failure_threshold"]) and (bad == 0 or good == 0), "invalid failure run"
    assert good <= checks - failures and bad <= failures, "run exceeds observation counts"
    first_bad: float = json_float(record["first_bad"])
    assert first_bad >= 0.0 and first_bad <= now and (bad > 0 or first_bad == 0.0), "invalid failure start"
    if phase == "down":
        assert not json_is_null(record["opened"]) and json_float(record["opened"]) >= 0.0, "missing outage start"
        assert json_float(record["opened"]) <= now and good < json_int(
            policy["recovery_threshold"]
        ), "invalid open outage"
    else:
        assert json_is_null(record["opened"]), "healthy state has an open outage"
        assert bad < json_int(policy["failure_threshold"]), "unapplied failure threshold"
    if phase == "unknown":
        assert checks == failures and good == 0, "unknown state has a successful check"
    if phase == "up":
        assert checks > failures, "healthy state has no successful check"
    down: float = json_float(record["down_seconds"])
    assert down >= 0.0 and down <= now, "invalid downtime"
    previous: float = 0.0
    retained_down: float = 0.0
    outages: list[Json] = json_array(record["outages"])
    assert len(outages) <= json_int(policy["retain"]), "too many outages"
    for outage in outages:
        assert json_keys(outage) == ["end", "seconds", "start"], "invalid outage fields"
        start: float = json_float(outage["start"])
        end: float = json_float(outage["end"])
        assert start >= previous and end >= start and end <= now, "invalid outage interval"
        assert json_float(outage["seconds"]) == end - start, "invalid outage duration"
        retained_down = retained_down + (end - start)
        previous = end
    assert down >= retained_down, "downtime omits retained outages"
    if phase == "down":
        assert json_float(record["opened"]) >= previous, "open outage overlaps closed history"
    samples: list[Json] = json_array(record["samples"])
    assert len(samples) == min(checks, json_int(policy["retain"])), "invalid sample history length"
    previous = 0.0
    for sample in samples:
        assert json_keys(sample) == ["at", "kind", "latency_ms", "ok", "status"], "invalid sample fields"
        at: float = json_float(sample["at"])
        code: int = json_int(sample["status"])
        kind: str = json_string(sample["kind"])
        assert at >= previous and at <= now and json_float(sample["latency_ms"]) >= 0.0, "invalid sample measurements"
        expected: bool = False
        for accepted in json_array(endpoint["statuses"]):
            if code == json_int(accepted):
                expected = True
        assert json_bool(sample["ok"]) == expected, "sample disagrees with policy"
        assert (code == 0 and kind == "transport") or (
            code >= 200 and code <= 599 and kind == "http"
        ), "invalid sample status"
        previous = at
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    if not path_exists(state_path()):
        records: list[Json] = []
        for endpoint in json_array(policy["endpoints"]):
            records.append(fresh())
        return {"version": 1, "policy": policy, "clock": clock(), "records": records}
    text: str = read_text(state_path())
    assert len(text.encode()) <= 8388608, "snapshot exceeds 8 MiB"
    state: Json = json_loads(text)
    assert json_keys(state) == ["clock", "policy", "records", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "snapshot policy mismatch"
    now: float = json_float(state["clock"])
    assert now >= 0.0 and now <= 253402214400.0, "invalid stored clock"
    records: list[Json] = json_array(state["records"])
    endpoints: list[Json] = json_array(policy["endpoints"])
    assert len(records) == len(endpoints), "endpoint count mismatch"
    for index in range(len(records)):
        validate_record(records[index], endpoints[index], policy, now)
    return state
