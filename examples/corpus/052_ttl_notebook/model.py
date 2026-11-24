# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
"""JSON values are opaque; liveness uses a half-open written-to-expiration interval."""

from config import setting

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_string,
)


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def key(value: Json) -> str:
    name: str = json_string(value)
    assert 1 <= len(name.encode()) <= 128, "key must contain 1..128 UTF-8 bytes"
    return name


def depth(value: Json, level: int) -> None:
    assert level <= 16, "value nesting exceeds 16"
    if json_kind(value) == "array":
        for item in json_array(value):
            depth(item, level + 1)
    elif json_kind(value) == "object":
        for name in json_keys(value):
            depth(value[name], level + 1)
    return


def value_check(value: Json) -> None:
    depth(value, 0)
    assert len(json_canonical(value).encode()) <= setting("TTL_VALUE_BYTES", 16384), "value exceeds byte limit"
    return


def lifetime(value: Json) -> int:
    result: int = json_int(value)
    assert 1 <= result <= 86400, "TTL must be an integer from 1 to 86400 seconds"
    return result


def live(entries: Json, now: float) -> Json:
    result: Json = {}
    for name in json_keys(entries):
        if json_float(entries[name]["expires"]) > now:
            result[name] = entries[name]
    return result


def entry(name: str, record: Json) -> Json:
    return {
        "key": name,
        "value": record["value"],
        "written": record["written"],
        "expires": record["expires"],
        "ttl": record["ttl"],
    }


def execute(state: Json, command: Json) -> tuple[Json, int, Json]:
    now: float = json_float(state["clock"])
    entries: Json = state["entries"]
    active: Json = live(entries, now)
    operation: str = json_string(command["op"])
    name: str = json_string(command["key"])
    result: Json = {"clock": now}
    status: int = 200
    if operation == "put":
        if name not in active and len(json_keys(active)) >= setting("TTL_KEYS", 256):
            return (state, 507, {"error": "live key storage is full"})
        status = 200 if name in active else 201
        ttl: int = json_int(command["ttl"])
        seconds: float = ttl
        record: Json = {"value": command["value"], "written": now, "ttl": ttl, "expires": now + seconds}
        active[name] = record
        entries = active  # A successful put reclaims all expired slots.
        result["entry"] = entry(name, record)
    elif operation == "get":
        if name in active:
            result["entry"] = entry(name, active[name])
        else:
            status = 404
            result["error"] = "key is absent or expired"
    elif operation == "delete":
        result["deleted"] = name in active
        if name in entries:
            del entries[name]
    elif operation == "sweep":
        result["removed"] = len(json_keys(entries)) - len(json_keys(active))
        entries = active
    else:
        matches: list[Json] = []
        for item in json_keys(active):
            if item.startswith(json_string(command["prefix"])):
                matches.append(entry(item, active[item]))
        offset: int = json_int(command["offset"])
        limit: int = json_int(command["limit"])
        result["entries"] = matches[offset : offset + limit]
        result["count"] = len(matches)
        result["more"] = offset + limit < len(matches)
    state["entries"] = entries
    return (state, status, result)
