"""Monotone announcement sequences; duplicates never extend a service lease."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
    regex_search,
)


def identifier(value: Json) -> str:
    text: str = json_string(value)
    assert regex_fullmatch("[A-Za-z0-9_-]{1,40}", text), "invalid identifier"
    return text


def service_type(value: Json, allow_empty: bool) -> str:
    text: str = json_string(value)
    assert (allow_empty and text == "") or regex_fullmatch("[a-z][a-z0-9_-]{0,23}", text), "invalid service type"
    return text


def description(request: Json) -> Json:
    assert json_keys(request) == [
        "id",
        "name",
        "op",
        "port",
        "request",
        "seq",
        "service",
        "tags",
        "ttl_ms",
    ], "invalid fields"
    name: str = json_string(request["name"])
    assert len(name.encode()) >= 1 and len(name.encode()) <= 80, "invalid display name"
    assert not regex_search("[\\x00-\\x1f\\x7f]", name), "control character in display name"
    port: int = json_int(request["port"])
    ttl: int = json_int(request["ttl_ms"])
    seq: int = json_int(request["seq"])
    assert port >= 1 and port <= 65535 and ttl >= 50 and ttl <= 30000 and seq >= 1, "invalid announcement numbers"
    tags: list[str] = []
    for value in json_array(request["tags"]):
        tag: str = json_string(value)
        assert regex_fullmatch("[a-z0-9_-]{1,16}", tag) and tag not in tags, "invalid or duplicate tag"
        tags.append(tag)
    assert len(tags) <= 8, "too many tags"
    tags.sort()
    return {
        "id": identifier(request["id"]),
        "service": service_type(request["service"], False),
        "name": name,
        "port": port,
        "seq": seq,
        "ttl_ms": ttl,
        "tags": tags,
    }


def sweep(state: Json, now: int) -> Json:
    now = max(now, json_int(state["clock"]))
    entries: Json = state["entries"]
    for key in json_keys(entries):
        if json_int(entries[key]["forget"]) <= now:
            del entries[key]
    state["clock"] = now
    state["entries"] = entries
    return state


def advertised(record: Json) -> Json:
    item: Json = record["description"]
    return {
        "id": item["id"],
        "service": item["service"],
        "name": item["name"],
        "port": item["port"],
        "seq": item["seq"],
        "ttl_ms": item["ttl_ms"],
        "tags": item["tags"],
        "host": record["host"],
        "expires_ms": record["expires"],
    }


def registry(state: Json) -> Json:
    active: list[Json] = []
    entries: Json = state["entries"]
    for key in json_keys(entries):
        if json_int(entries[key]["expires"]) > json_int(state["clock"]):
            active.append(advertised(entries[key]))
    return {"services": active, "retained": len(json_keys(entries)), "expired": len(json_keys(entries)) - len(active)}
