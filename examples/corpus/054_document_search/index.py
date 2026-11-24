"""Updating one document removes old postings and adds only its current weighted terms."""

# ruff: noqa: C414 - typed list conversion is explicit in this subset

from dataclasses import dataclass

from lexicon import frequencies

from py2rust.stdlib import Json, json_int


@dataclass
class Index:
    capacity: int
    steps: int
    records: dict[str, Json]
    postings: dict[str, dict[str, int]]


def capacity(value: Json) -> int:
    result: int = json_int(value)
    assert 1 <= result <= 128, "capacity must be 1..128"
    return result


def empty(size: int) -> Index:
    records: dict[str, Json] = {}
    postings: dict[str, dict[str, int]] = {}
    return Index(size, 0, records, postings)


def replace(index: Index, name: str, value: Json) -> Index:
    records: dict[str, Json] = index.records.copy()
    postings: dict[str, dict[str, int]] = index.postings.copy()
    old: dict[str, int] = {}
    fresh: dict[str, int] = {}
    if name in records:
        old = frequencies(records[name])
        del records[name]
    if value is not None:
        fresh = frequencies(value)
        records[name] = value
    changed: set[str] = set(list(old)) | set(list(fresh))
    for term in changed:
        members: dict[str, int] = postings.get(term, {}).copy()
        if name in members:
            del members[name]  # noqa: RUF051 - dict.pop is outside the typed subset
        if term in fresh:
            members[name] = fresh[term]
        if len(members) == 0:
            del postings[term]
        else:
            postings[term] = members
    assert len(postings) <= 4096, "index exceeds 4096 distinct terms"
    return Index(index.capacity, index.steps, records, postings)


def documents(index: Index) -> list[Json]:
    result: list[Json] = []
    for name in sorted(list(index.records)):
        result.append(index.records[name])
    return result


def summary(index: Index) -> Json:
    edges: int = 0
    for term in index.postings:
        edges = edges + len(index.postings[term])
    return {
        "documents": len(index.records),
        "terms": len(index.postings),
        "postings": edges,
        "capacity": index.capacity,
    }
