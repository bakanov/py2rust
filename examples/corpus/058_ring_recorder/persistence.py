"""Canonical checksummed snapshots store chronological samples, independent of ring layout."""

from model import (
    Ring,
    Sample,
    bounded,
    counter_names,
    empty,
    exact,
    numeric,
    records,
    select,
    timestamp,
)

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


def save(ring: Ring) -> str:
    state: Json = {
        "version": 1,
        "capacity": ring.capacity,
        "window_ms": ring.window_ms,
        "clock_ms": ring.clock_ms,
        "samples": records(select(ring, 0, ring.clock_ms)),
        "stats": ring.stats,
    }
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, capacity: int, window_ms: int) -> Ring:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert digest(state) == json_string(envelope["sha256"]), "snapshot checksum mismatch"
    exact(state, ["version", "capacity", "window_ms", "clock_ms", "samples", "stats"])
    assert json_int(state["version"]) == 1, "unsupported recorder snapshot version"
    assert json_int(state["capacity"]) == capacity, "configured capacity differs from snapshot"
    assert json_int(state["window_ms"]) == window_ms, "configured window differs from snapshot"
    ring: Ring = empty(capacity, window_ms)
    ring.clock_ms = timestamp(state["clock_ms"])
    exact(state["stats"], counter_names())
    stats: dict[str, int] = {}
    for name in counter_names():
        stats[name] = bounded(state["stats"][name], 0, 1000000000)
    assert (
        stats["steps"]
        == stats["ingested"] + stats["advances"] + stats["summaries"] + stats["exports"] + stats["inspections"]
    ), "inconsistent command count"
    saved: list[Json] = json_array(state["samples"])
    assert len(saved) <= capacity, "snapshot exceeds capacity"
    assert stats["ingested"] == stats["expired"] + stats["overwritten"] + len(saved), "inconsistent retained count"
    assert stats["overwritten"] <= max(0, stats["ingested"] - capacity), "impossible overwrite count"
    assert ring.clock_ms > window_ms or stats["expired"] == 0, "impossible expiration count"
    slots: list[Sample] = ring.slots
    previous: int = 0
    for index in range(len(saved)):
        item: Json = saved[index]
        exact(item, ["sequence", "time_ms", "value"])
        sequence: int = json_int(item["sequence"])
        assert sequence == stats["ingested"] - len(saved) + index + 1, "inconsistent sample sequence"
        time: int = timestamp(item["time_ms"])
        assert previous <= time <= ring.clock_ms and time >= ring.clock_ms - window_ms, "invalid retained timestamp"
        number: float = numeric(item["value"])
        slots[index] = Sample(sequence, time, number)
        previous = time
    if stats["advances"] == 0:
        if stats["ingested"] == 0:
            assert ring.clock_ms == 0, "clock moved without samples or advances"
        else:
            assert len(saved) > 0 and previous == ring.clock_ms, "last ingestion must define the clock"
    ring.slots = slots
    ring.count = len(saved)
    ring.stats = stats
    return ring
