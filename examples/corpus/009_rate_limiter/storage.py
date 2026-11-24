"""Durable admission records; clock rollback cannot resurrect expired quota."""

from model import clock, policy, setting, valid_id, valid_key

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_float,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("RATE_STATE", "rate-state.json")


def load() -> Json:
    content: str = read_text(state_path())
    assert len(content.encode()) <= setting("RATE_MAX_STATE", 8388608), "snapshot exceeds byte limit"
    state: Json = json_loads(content)
    assert json_keys(state) == ["clock", "keys", "policy", "version"], "invalid snapshot fields"
    assert json_int(state["version"]) == 1, "unsupported snapshot version"
    assert json_equal(state["policy"], policy()), "configured policy differs from stored policy"
    return state


def fits(state: Json) -> bool:
    return len(pretty(state).encode()) <= setting("RATE_MAX_STATE", 8388608)


def save(state: Json) -> None:
    assert fits(state), "snapshot exceeds byte limit"
    assert len(json_keys(state["keys"])) <= setting("RATE_KEYS", 1000), "key limit exceeded"
    write_text_atomic(state_path(), pretty(state))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def initialize() -> None:
    if not path_exists(state_path()):
        save({"version": 1, "policy": policy(), "clock": clock(), "keys": {}})
    state: Json = load()
    observed: float = json_float(state["clock"])
    assert observed >= 0.0 and observed <= 253402214400.0, "invalid stored clock"
    window: float = json_float(policy()["window"])
    assert len(json_keys(state["keys"])) <= setting("RATE_KEYS", 1000), "stored key limit exceeded"
    for key in json_keys(state["keys"]):
        assert valid_key(key), "invalid stored key"
        events: list[Json] = json_array(state["keys"][key])
        assert len(events) >= 1 and len(events) <= json_int(policy()["quota"]), "invalid admission count"
        seen: set[str] = set()
        previous_time: float = 0.0
        total: int = 0
        for event in events:
            assert json_keys(event) == ["at", "cost", "id"], "invalid admission fields"
            identifier: str = json_string(event["id"])
            assert valid_id(identifier) and identifier not in seen, "invalid or duplicate admission ID"
            seen.add(identifier)
            timestamp: float = json_float(event["at"])
            assert (
                timestamp >= previous_time and timestamp <= observed and timestamp > observed - window
            ), "invalid admission time"
            previous_time = timestamp
            cost: int = json_int(event["cost"])
            assert cost >= 1, "invalid stored cost"
            total = total + cost
        assert total <= json_int(policy()["quota"]), "stored admissions exceed quota"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def refresh() -> Json:
    state: Json = load()
    now: float = max(clock(), json_float(state["clock"]))
    window: float = json_float(policy()["window"])
    active: Json = {}
    for key in json_keys(state["keys"]):
        kept: list[Json] = []
        for event in json_array(state["keys"][key]):
            if json_float(event["at"]) > now - window:
                kept.append(event)
        if len(kept) > 0:
            active[key] = kept
    updated: Json = {"version": 1, "policy": policy(), "clock": now, "keys": active}
    if not json_equal(state, updated):
        save(updated)
    return updated
