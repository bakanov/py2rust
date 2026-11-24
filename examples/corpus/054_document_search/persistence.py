"""Checksummed snapshots retain documents and verify every stored posting against a rebuilt index."""

from index import Index, capacity, documents, empty, replace
from lexicon import document, exact, identifier

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


def digest(state: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(state).encode()))


def save(index: Index) -> str:
    state: Json = {
        "version": 1,
        "capacity": index.capacity,
        "steps": index.steps,
        "documents": documents(index),
        "postings": index.postings,
    }
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, expected_capacity: int) -> Index:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "snapshot checksum mismatch"
    exact(state, ["version", "capacity", "steps", "documents", "postings"])
    assert json_int(state["version"]) == 1, "unsupported index version"
    size: int = capacity(state["capacity"])
    assert size == expected_capacity, "configured capacity differs from saved state"
    index: Index = empty(size)
    for raw in json_array(state["documents"]):
        value: Json = document(raw)
        name: str = identifier(value["id"])
        assert name not in index.records, "duplicate document ID"
        assert len(index.records) < size, "saved index exceeds capacity"
        index = replace(index, name, value)
    index.steps = json_int(state["steps"])
    assert 0 <= index.steps <= 1000000000, "invalid step count"
    assert json_equal(state["postings"], index.postings), "postings do not match documents"
    return index
