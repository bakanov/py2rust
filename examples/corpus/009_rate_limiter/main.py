"""Admit weighted requests per key, preserving exact rolling-window decisions."""

import math

from model import configure, quota, request_value, setting, valid_key
from storage import fits, initialize, load, refresh, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_array,
    json_dumps,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if "remaining" in value:
        headers["X-RateLimit-Limit"] = str(json_int(value["limit"]))
        headers["X-RateLimit-Remaining"] = str(json_int(value["remaining"]))
    if status == 429:
        delay: float = json_float(value["retry_at"]) - json_float(value["now"])
        headers["Retry-After"] = str(max(1, math.ceil(delay)))
    return web_response(status, json_dumps(value).encode(), headers)


def decision(
    key: str, identifier: str, cost: int, events: list[Json], now: float, allowed: bool, duplicate: bool
) -> Json:
    needed: int = cost
    if allowed:
        needed = 0
    result: Json = quota(key, events, now, needed)
    result["id"] = identifier
    result["cost"] = cost
    result["allowed"] = allowed
    result["duplicate"] = duplicate
    return result


def admit(request: WebRequest) -> WebResponse:
    value: Json = None
    try:
        value = request_value(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid key, request ID or cost"})
    state: Json = refresh()
    now: float = json_float(state["clock"])
    key: str = json_string(value["key"])
    identifier: str = json_string(value["id"])
    cost: int = json_int(value["cost"])
    events: list[Json] = json_array(json_get(state["keys"], key, []))
    for event in events:
        if json_string(event["id"]) == identifier:
            if json_int(event["cost"]) != cost:
                return reply(409, {"error": "request ID already has a different cost"})
            return reply(200, decision(key, identifier, cost, events, now, True, True))
    before: Json = quota(key, events, now, cost)
    if json_int(before["remaining"]) < cost:
        return reply(429, decision(key, identifier, cost, events, now, False, False))
    if key not in state["keys"] and len(json_keys(state["keys"])) >= setting("RATE_KEYS", 1000):
        return reply(507, {"error": "active key storage is full"})
    events.append({"id": identifier, "at": now, "cost": cost})
    keys: Json = state["keys"]
    keys[key] = events
    state["keys"] = keys
    if not fits(state):
        return reply(507, {"error": "snapshot would exceed byte limit"})
    save(state)
    return reply(200, decision(key, identifier, cost, events, now, True, False))


def inspect(request: WebRequest) -> WebResponse:
    key: str = request.query.get("key", "")
    if not valid_key(key):
        return reply(400, {"error": "invalid key"})
    state: Json = refresh()
    events: list[Json] = json_array(json_get(state["keys"], key, []))
    return reply(200, quota(key, events, json_float(state["clock"]), 1))


def total_events(state: Json) -> int:
    count: int = 0
    for key in json_keys(state["keys"]):
        count = count + len(json_array(state["keys"][key]))
    return count


def handle(request: WebRequest) -> WebResponse:
    try:
        if len(request.body) > 4096:
            return reply(413, {"error": "request exceeds byte limit"})
        if request.path == "/admit" and request.method == "POST":
            return admit(request)
        if request.path == "/quota" and request.method == "GET":
            return inspect(request)
        if request.path == "/quotas" and request.method == "GET":
            state: Json = refresh()
            quotas: list[Json] = []
            for key in json_keys(state["keys"]):
                quotas.append(quota(key, json_array(state["keys"][key]), json_float(state["clock"]), 1))
            return reply(200, {"keys": quotas, "count": len(quotas)})
        if request.path == "/sweep" and request.method == "POST":
            before: Json = load()
            after: Json = refresh()
            return reply(
                200,
                {
                    "removed_keys": len(json_keys(before["keys"])) - len(json_keys(after["keys"])),
                    "removed_events": total_events(before) - total_events(after),
                },
            )
        return reply(404, {"error": "unknown route"})
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "rate-limit storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve("127.0.0.1", setting("RATE_PORT", 8774), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
