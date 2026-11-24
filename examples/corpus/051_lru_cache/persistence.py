"""Validate ordered cache snapshots and cumulative accounting before any resumed replay."""

from model import Cache, capacity, counters, empty, entries, exact, key, value_check

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


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def save(cache: Cache) -> str:
    state: Json = {"version": 1, "capacity": cache.capacity, "entries": entries(cache.values), "stats": cache.stats}
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, expected_capacity: int) -> Cache:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert digest(state) == json_string(envelope["sha256"]), "state checksum mismatch"
    exact(state, ["version", "capacity", "entries", "stats"])
    assert json_int(state["version"]) == 1, "unsupported cache state version"
    size: int = capacity(state["capacity"])
    assert size == expected_capacity, "configured capacity differs from saved state"
    cache: Cache = empty(size)
    values: dict[str, Json] = {}
    for entry in json_array(state["entries"]):
        exact(entry, ["key", "value"])
        name: str = key(entry["key"])
        assert name not in values, "duplicate saved cache key"
        value_check(entry["value"])
        values[name] = entry["value"]
    assert len(values) <= size, "saved cache exceeds capacity"
    raw_stats: Json = state["stats"]
    exact(raw_stats, counters())
    stats: dict[str, int] = cache.stats
    for name in counters():
        stats[name] = json_int(raw_stats[name])
        assert stats[name] >= 0, "negative saved counter"
    assert stats["gets"] == stats["hits"] + stats["misses"], "inconsistent get counters"
    assert stats["deleted"] <= stats["deletes"], "inconsistent delete counters"
    assert stats["overwrites"] + stats["dropped"] <= stats["puts"], "inconsistent put counters"
    assert (
        len(values) == stats["puts"] - stats["overwrites"] - stats["dropped"] - stats["deleted"] - stats["evictions"]
    ), "inconsistent saved entry accounting"
    steps: int = 0
    for name in ["gets", "puts", "deletes", "resizes", "peeks", "inspections"]:
        steps = steps + stats[name]
    assert stats["steps"] == steps, "inconsistent saved operation count"
    return Cache(size, values, stats)
