"""Announcements and deterministic, size-bounded discovery pages."""

from model import advertised, description, identifier, service_type

from py2rust.stdlib import (
    Json,
    json_dumps,
    json_equal,
    json_get,
    json_int,
    json_keys,
    json_string,
)


def failure(request: str, reason: str) -> Json:
    return {"ok": False, "request": request, "error": reason}


def announce(request: Json, host: str, state: Json, policy: Json) -> tuple[Json, Json]:
    nonce: str = identifier(request["request"])
    item: Json = description(request)
    key: str = json_string(item["id"])
    entries: Json = state["entries"]
    now: int = json_int(state["clock"])
    if key in entries:
        prior: Json = entries[key]
        previous: int = json_int(prior["description"]["seq"])
        if json_int(item["seq"]) < previous:
            return (state, failure(nonce, "stale_sequence"))
        if json_int(item["seq"]) == previous:
            if not json_equal(prior["description"], item) or json_string(prior["host"]) != host:
                return (state, failure(nonce, "sequence_conflict"))
            return (
                state,
                {
                    "ok": True,
                    "request": nonce,
                    "duplicate": True,
                    "active": json_int(prior["expires"]) > now,
                    "service": advertised(prior),
                },
            )
    elif len(json_keys(entries)) >= json_int(policy["max_services"]):
        return (state, failure(nonce, "retained_capacity"))
    expires: int = now + json_int(item["ttl_ms"])
    forget: int = expires + json_int(policy["remember_ms"])
    assert forget <= 253402214400000, "lease outside clock range"
    record: Json = {"description": item, "host": host, "expires": expires, "forget": forget}
    entries[key] = record
    state["entries"] = entries
    return (state, {"ok": True, "request": nonce, "duplicate": False, "active": True, "service": advertised(record)})


def discover(request: Json, state: Json, policy: Json) -> Json:
    for key in json_keys(request):
        assert key in ["op", "request", "service", "after", "limit"], "invalid discovery fields"
    nonce: str = identifier(request["request"])
    kind: str = service_type(json_get(request, "service", ""), True)
    after: str = json_string(json_get(request, "after", ""))
    if after != "":
        identifier(after)
    limit: int = json_int(json_get(request, "limit", 20))
    assert limit >= 1 and limit <= 20, "invalid page limit"
    found: list[Json] = []
    result: Json = {"ok": True, "request": nonce, "services": found, "next": after, "more": False}
    entries: Json = state["entries"]
    for key in json_keys(entries):
        entry: Json = entries[key]
        if (
            key > after
            and json_int(entry["expires"]) > json_int(state["clock"])
            and (kind == "" or json_string(entry["description"]["service"]) == kind)
        ):
            candidate: list[Json] = found.copy()
            candidate.append(advertised(entry))
            page: Json = {"ok": True, "request": nonce, "services": candidate, "next": key, "more": False}
            if len(candidate) > limit or len(json_dumps(page).encode()) > json_int(policy["max_datagram"]):
                result["more"] = True
                return result
            found = candidate
            result = page
    return result


def handle(request: Json, host: str, state: Json, policy: Json) -> tuple[Json, Json]:
    operation: str = json_string(request["op"])
    if operation == "announce":
        return announce(request, host, state, policy)
    if operation == "discover":
        return (state, discover(request, state, policy))
    return (state, failure(identifier(request["request"]), "unknown_operation"))
