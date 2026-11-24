"""Validate complete imports and rebuild the derived index from canonical snapshots."""

# ruff: noqa: C414 - explicit typed dictionary iteration

from index import Event, Index, bounded, document, empty, exact, parse, rebuild

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(state: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(state).encode()))


def import_events(index: Index, value: Json) -> tuple[Index, Json]:
    rows: list[Json] = json_array(value)
    assert len(rows) <= 1024, "import exceeds 1024 records"
    seen: set[str] = set()
    events: dict[str, Event] = index.events
    added: int = 0
    replaced: int = 0
    for row in rows:
        event: Event = parse(row)
        assert event.identifier not in seen, "duplicate imported ID"
        seen.add(event.identifier)
        if event.identifier in events:
            replaced = replaced + 1
        else:
            added = added + 1
        events[event.identifier] = event
        assert len(events) <= index.capacity, "import exceeds capacity"
    index.events = events
    return (rebuild(index), {"read": len(rows), "added": added, "replaced": replaced})


def save(index: Index) -> str:
    rows: list[Json] = []
    for name in sorted(list(index.events)):
        rows.append(document(index.events[name]))
    state: Json = {"version": 1, "capacity": index.capacity, "steps": index.steps, "events": rows}
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, capacity: int) -> Index:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert digest(state) == json_string(envelope["sha256"]), "snapshot checksum mismatch"
    exact(state, ["version", "capacity", "steps", "events"])
    assert json_int(state["version"]) == 1, "unsupported index snapshot version"
    assert json_int(state["capacity"]) == capacity, "configured capacity differs from snapshot"
    loaded: tuple[Index, Json] = import_events(empty(capacity), state["events"])
    index: Index = loaded[0]
    index.steps = bounded(state["steps"], 0, 1000000000)
    return index
