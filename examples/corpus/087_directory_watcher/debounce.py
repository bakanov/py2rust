"""Persist quiet windows, flush lifecycle boundaries, and retain a contiguous event journal."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from events import changes
from py2rust.stdlib import (
    Json, json_array, json_canonical, json_int, json_keys, json_loads, json_string,
)


def emit(state: Json, item: Json, now: int, retain: int) -> Json:
    next_id: int = json_int(state["next_id"])
    assert next_id < 1000000000000, "event ID space exhausted"
    item["id"] = next_id
    item["emitted_ms"] = now
    journal: list[Json] = json_array(state["journal"])
    journal.append(item)
    state["journal"] = journal[max(0, len(journal) - retain) :]
    state["next_id"] = next_id + 1
    return state


def flush(state: Json, path: str, now: int, retain: int) -> Json:
    pending: Json = state["pending"]
    if path in json_keys(pending):
        state = emit(state, pending[path], now, retain)
        del pending[path]
        state["pending"] = pending
    return state


def advance(config: Json, saved: Json, current: Json, observed: int) -> Json:
    state: Json = json_loads(json_canonical(saved))
    now: int = max(observed, json_int(state["clock_ms"]))
    delay: int = json_int(config["debounce_ms"])
    retain: int = json_int(config["retain"])
    for path in sorted(json_keys(state["pending"])):
        if json_int(state["pending"][path]["last_ms"]) + delay <= now:
            state = flush(state, path, now, retain)
    batch: list[Json] = changes(state["snapshot"], current, now)
    for item in batch:
        if json_string(item["kind"]) in ["deleted", "renamed"]:
            state = flush(state, json_string(item["path"]), now, retain)
            state = flush(state, json_string(item["previous_path"]), now, retain)
    for item in batch:
        kind: str = json_string(item["kind"])
        path: str = json_string(item["path"])
        if kind in ["deleted", "renamed"]:
            state = emit(state, item, now, retain)
        else:
            pending: Json = state["pending"]
            if path in json_keys(pending):
                previous: Json = pending[path]
                previous["after"] = item["after"]
                previous["last_ms"] = now
                pending[path] = previous
            else:
                pending[path] = item
            state["pending"] = pending
    for path in sorted(json_keys(state["pending"])):
        if json_int(state["pending"][path]["last_ms"]) + delay <= now:
            state = flush(state, path, now, retain)
    state["snapshot"] = current
    state["clock_ms"] = now
    return state
