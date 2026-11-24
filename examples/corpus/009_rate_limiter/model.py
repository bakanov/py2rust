"""A weighted sliding window with explicit retry times and immutable request IDs."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_parse,
    json_string,
    regex_fullmatch,
    regex_search,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("RATE_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def policy() -> Json:
    return {"quota": setting("RATE_QUOTA", 5), "window": json_float(json_parse(env_get("RATE_WINDOW", "60"), None))}


def valid_key(key: str) -> bool:
    return len(key) >= 1 and len(key) <= 100 and not regex_search("[\\x00-\\x1f\\x7f]", key)


def valid_id(identifier: str) -> bool:
    return regex_fullmatch("[A-Za-z0-9_-]{1,80}", identifier)


def request_value(value: Json) -> Json:
    keys: list[str] = json_keys(value)
    assert keys == ["id", "key"] or keys == ["cost", "id", "key"], "invalid admission fields"
    key: str = json_string(value["key"])
    identifier: str = json_string(value["id"])
    cost: int = json_int(json_get(value, "cost", 1))
    assert valid_key(key) and valid_id(identifier), "invalid key or request ID"
    assert cost >= 1 and cost <= json_int(policy()["quota"]), "invalid request cost"
    return {"key": key, "id": identifier, "cost": cost}


def quota(key: str, events: list[Json], now: float, cost: int) -> Json:
    configuration: Json = policy()
    limit: int = json_int(configuration["quota"])
    window: float = json_float(configuration["window"])
    used: int = 0
    for event in events:
        used = used + json_int(event["cost"])
    remaining: int = limit - used
    retry_at: float = now
    reset_at: float = now
    if len(events) > 0:
        reset_at = json_float(events[-1]["at"]) + window
    if cost > remaining:
        released: int = 0
        for event in events:
            released = released + json_int(event["cost"])
            if released >= cost - remaining:
                retry_at = json_float(event["at"]) + window
                break
    return {
        "key": key,
        "limit": limit,
        "window": window,
        "used": used,
        "remaining": remaining,
        "now": now,
        "retry_at": retry_at,
        "reset_at": reset_at,
    }


def configure() -> None:
    configuration: Json = policy()
    assert json_int(configuration["quota"]) >= 1 and json_int(configuration["quota"]) <= 10000, "invalid quota"
    assert (
        json_float(configuration["window"]) >= 0.001 and json_float(configuration["window"]) <= 86400.0
    ), "invalid window"
    assert setting("RATE_KEYS", 1000) >= 1 and setting("RATE_KEYS", 1000) <= 1000, "invalid key limit"
    assert (
        setting("RATE_MAX_STATE", 8388608) >= 1024 and setting("RATE_MAX_STATE", 8388608) <= 33554432
    ), "invalid snapshot limit"
    assert setting("RATE_PORT", 8774) >= 0 and setting("RATE_PORT", 8774) <= 65535, "invalid port"
    assert clock() >= 0.0 and clock() <= 253402214400.0, "invalid clock"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
