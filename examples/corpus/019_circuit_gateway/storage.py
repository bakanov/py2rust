"""One atomic snapshot retains circuit state, counters and the last twenty transitions."""

from circuit import Phase, finish, fresh
from model import clock

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_float,
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
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("GATEWAY_STATE", "gateway-state.json")


def validate_paths() -> None:
    paths: list[str] = [state_path(), env_get("GATEWAY_CONFIG", "gateway.json")]
    for name in ["GATEWAY_CLOCK", "GATEWAY_CA"]:
        path: str = env_get(name, "")
        if path != "":
            paths.append(path)
    assert not path_is_symlink(state_path()), "state must not be a symlink"
    canonical: list[str] = []
    for index in range(len(paths)):
        value: str = paths[index]
        normalized: str = path_join(path_resolve(path_parent(value)), path_name(value))
        assert normalized not in canonical, "configuration, state or clock overlap"
        canonical.append(normalized)
        for previous in range(index):
            if path_exists(value) and path_exists(paths[previous]):
                assert not path_same(value, paths[previous]), "configuration, state or clock alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    text: str = pretty(state)
    assert len(text.encode()) <= 1048576, "state exceeds 1 MiB"
    validate_paths()
    write_text_atomic(state_path(), text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_record(record: Json, policy: Json, now: float) -> None:
    assert json_keys(record) == json_keys(fresh(json_string(record["id"]))), "invalid circuit fields"
    phase: str = json_string(record["phase"])
    assert phase in [Phase.CLOSED.value, Phase.OPEN.value, Phase.HALF_OPEN.value], "invalid circuit phase"
    for field in ["calls", "failed_calls", "rejected", "sequence"]:
        assert json_int(record[field]) >= 0 and json_int(record[field]) <= 1000000000, "invalid circuit counter"
    calls: int = json_int(record["calls"])
    failed: int = json_int(record["failed_calls"])
    inflight: bool = json_bool(record["inflight"])
    assert failed <= calls and (not inflight or failed < calls), "more failures than calls"
    last: float = json_float(record["last_at"])
    retry: float = json_float(record["retry_at"])
    assert last >= 0.0 and last <= now and retry >= 0.0 and retry <= 253402300799.0, "invalid circuit times"
    failures: int = json_int(record["failures"])
    successes: int = json_int(record["successes"])
    assert failures >= 0 and failures <= json_int(policy["threshold"]) and failures <= failed, "invalid failures"
    assert successes >= 0 and successes < json_int(policy["probes"]), "invalid successful probe count"
    assert phase == Phase.HALF_OPEN.value or successes == 0, "probes outside half-open circuit"
    if phase == Phase.OPEN.value:
        assert not inflight and failures > 0 and retry > last, "invalid open circuit"
    else:
        assert retry == 0.0, "cooldown outside open circuit"
    if phase == Phase.CLOSED.value:
        assert failures < json_int(policy["threshold"]), "closed circuit exceeds failure threshold"
    status: int = json_int(record["last_status"])
    error: str = json_string(record["last_error"])
    assert status == 0 or (status >= 200 and status <= 599), "invalid upstream status"
    assert error in ["", "http", "transport", "interrupted"], "invalid error category"
    if error == "http":
        assert status == 408 or status == 429 or status >= 500, "invalid HTTP failure"
    if error in ["transport", "interrupted"]:
        assert status == 0, "transport failure has a response"
    if calls == 0:
        assert json_equal(record, fresh(json_string(record["id"]))), "unattempted circuit has observations"
    history: list[Json] = json_array(record["history"])
    sequence: int = json_int(record["sequence"])
    assert len(history) == min(sequence, 20) and sequence <= calls * 2, "invalid transition count"
    previous: str = ""
    at: float = 0.0
    expected: int = sequence - len(history) + 1
    for event in history:
        assert json_keys(event) == ["after", "at", "before", "reason", "sequence"], "invalid transition fields"
        assert json_int(event["sequence"]) == expected, "transition sequence gap"
        before: str = json_string(event["before"])
        after: str = json_string(event["after"])
        assert before + ":" + after in [
            "closed:open",
            "open:half_open",
            "half_open:open",
            "half_open:closed",
        ], "invalid transition"
        assert previous == "" or previous == before, "broken transition chain"
        assert expected != 1 or before == Phase.CLOSED.value, "initial transition did not start closed"
        assert json_float(event["at"]) >= at and json_float(event["at"]) <= last, "invalid transition time"
        assert json_string(event["reason"]) in [
            "http",
            "transport",
            "interrupted",
            "probe",
            "recovered",
        ], "invalid reason"
        if after == Phase.HALF_OPEN.value:
            assert json_string(event["reason"]) == "probe", "half-open transition is not a probe"
        elif after == Phase.CLOSED.value:
            assert json_string(event["reason"]) == "recovered", "closed transition is not recovery"
        else:
            assert json_string(event["reason"]) in ["http", "transport", "interrupted"], "open transition lacks failure"
        previous = after
        at = json_float(event["at"])
        expected = expected + 1
    assert (sequence == 0 and phase == Phase.CLOSED.value) or previous == phase, "phase disagrees with history"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    routes: list[Json] = json_array(policy["routes"])
    records: list[Json] = []
    if not path_exists(state_path()):
        for route in routes:
            records.append(fresh(json_string(route["id"])))
        return {"version": 1, "policy": policy, "clock": 0.0, "circuits": records}
    text: str = read_text(state_path())
    assert len(text.encode()) <= 1048576, "state exceeds 1 MiB"
    state: Json = json_loads(text)
    assert json_keys(state) == ["circuits", "clock", "policy", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "state policy mismatch"
    now: float = json_float(state["clock"])
    assert now >= 0.0 and now <= 253402200000.0, "invalid snapshot clock"
    records = json_array(state["circuits"])
    assert len(records) == len(routes), "circuit count differs from route count"
    busy: int = 0
    for index in range(len(records)):
        assert json_string(records[index]["id"]) == json_string(routes[index]["id"]), "circuit route mismatch"
        validate_record(records[index], policy, now)
        if json_bool(records[index]["inflight"]):
            busy = busy + 1
    assert busy <= 1, "multiple inflight callbacks"
    return state


def initialize(policy: Json) -> None:
    state: Json = load(policy)
    now: float = clock()
    assert now >= json_float(state["clock"]), "clock moved backwards"
    records: list[Json] = json_array(state["circuits"])
    for index in range(len(records)):
        if json_bool(records[index]["inflight"]):
            records[index] = finish(records[index], 0, "interrupted", now, policy)
    state["circuits"] = records
    state["clock"] = now
    save(state)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
