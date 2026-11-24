"""Accepted-event identities, deterministic hash chaining and full audit replay."""

# ruff: noqa: BLE001 - isolated domain rejection
from model import balances, catalog, empty, exact, identifier, transition, validate

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def genesis(items: list[str]) -> str:
    return digest(encoded({"version": 1, "items": items}))


def create(items: list[str]) -> Json:
    return {"version": 1, "items": items, "revision": 0, "head": genesis(items), "events": [], "state": empty(items)}


def entry(sequence: int, previous: str, event: Json, state: Json) -> Json:
    body: Json = {"sequence": sequence, "previous": previous, "event": event, "state_sha256": digest(encoded(state))}
    body["hash"] = digest(encoded(body))
    return body


def replay(ledger: Json) -> Json:
    exact(ledger, ["version", "items", "revision", "head", "events", "state"])
    assert json_int(ledger["version"]) == 1, "unsupported ledger version"
    items: list[str] = catalog(ledger["items"])
    assert json_equal(ledger["items"], items), "noncanonical item catalog"
    events: list[Json] = json_array(ledger["events"])
    assert len(events) <= 512 and json_int(ledger["revision"]) == len(events), "invalid ledger revision"
    current: Json = empty(items)
    head: str = genesis(items)
    seen: set[str] = set()
    for index in range(len(events)):
        record: Json = events[index]
        exact(record, ["sequence", "previous", "event", "state_sha256", "hash"])
        assert json_int(record["sequence"]) == index + 1, "invalid audit sequence"
        event: Json = record["event"]
        kind: str = validate(event, items)
        name: str = identifier(event["id"])
        assert name not in seen, "duplicate stored transaction"
        seen.add(name)
        current = transition(current, event, kind)
        expected: Json = entry(index + 1, head, event, current)
        assert json_equal(record, expected), "audit record integrity mismatch"
        head = json_string(expected["hash"])
    assert json_string(ledger["head"]) == head and encoded(ledger["state"]) == encoded(
        current
    ), "ledger snapshot mismatch"
    balances(current)
    return current


def propose(ledger: Json, event: Json) -> tuple[Json, str]:
    items: list[str] = catalog(ledger["items"])
    kind: str = validate(event, items)
    name: str = identifier(event["id"])
    events: list[Json] = json_array(ledger["events"])
    for record in events:
        if json_string(record["event"]["id"]) == name:
            assert json_equal(record["event"], event), "transaction identifier conflicts"
            return (ledger, "duplicate")
    assert len(events) < 512, "ledger event limit"
    following: Json = transition(ledger["state"], event, kind)
    record: Json = entry(len(events) + 1, json_string(ledger["head"]), event, following)
    events.append(record)
    return (
        {
            "version": 1,
            "items": items,
            "revision": len(events),
            "head": record["hash"],
            "events": events,
            "state": following,
        },
        "accepted",
    )


def attempt(ledger: Json, event: Json, index: int) -> tuple[Json, Json]:
    try:
        result: tuple[Json, str] = propose(ledger, event)
        return (result[0], {"index": index, "status": result[1], "id": event["id"]})
    except Exception as error:
        return (ledger, {"index": index, "status": "rejected", "event": event, "reason": str(error)})
