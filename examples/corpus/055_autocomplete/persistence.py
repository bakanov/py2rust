"""Checksummed logical dictionaries rebuild the trie and validate its cached size."""

from trie import Index, capacity, change, empty, entries, exact, find, normalized, usage

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


def save(index: Index) -> str:
    state: Json = {
        "version": 1,
        "capacity": index.capacity,
        "steps": index.steps,
        "entries": entries(index.root, ""),
        "nodes": index.root.nodes,
    }
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, expected_capacity: int) -> Index:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "snapshot checksum mismatch"
    exact(state, ["version", "capacity", "steps", "entries", "nodes"])
    assert json_int(state["version"]) == 1, "unsupported autocomplete version"
    size: int = capacity(state["capacity"])
    assert size == expected_capacity, "configured capacity differs from saved state"
    index: Index = empty(size)
    for value in json_array(state["entries"]):
        exact(value, ["key", "term", "uses"])
        key: str = normalized(value["term"], False)
        assert json_string(value["key"]) == key, "saved key differs from normalized term"
        assert not find(index.root, key).terminal, "duplicate normalized term"
        assert index.root.words < size, "saved trie exceeds capacity"
        index.root = change(index.root, key, 0, True, json_string(value["term"]), usage(value["uses"]))
        assert index.root.nodes <= 8192, "trie exceeds 8192 nodes"
    index.steps = json_int(state["steps"])
    assert 0 <= index.steps <= 1000000000, "invalid step count"
    assert json_int(state["nodes"]) == index.root.nodes, "saved node count differs from rebuilt trie"
    return index
