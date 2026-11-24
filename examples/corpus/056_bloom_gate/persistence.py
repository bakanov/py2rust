"""Checksummed snapshots are rebuilt from audit keys before their saved bits are trusted."""

# ruff: noqa: C414 - explicit returns and typed conversions

from filter import Filter, bounded, empty, exact, insert, key_text

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


def save(index: Filter) -> str:
    state: Json = {
        "version": 1,
        "expected": index.expected,
        "probability_ppm": index.probability_ppm,
        "capacity": index.capacity,
        "bit_count": index.bit_count,
        "hashes": index.hashes,
        "bits_hex": index.bits.hex(),
        "keys": sorted(list(index.keys)),
        "steps": index.steps,
        "counts": index.counts,
    }
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, configured: Filter) -> Filter:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert json_string(envelope["sha256"]) == digest(state), "snapshot checksum mismatch"
    exact(
        state,
        [
            "version",
            "expected",
            "probability_ppm",
            "capacity",
            "bit_count",
            "hashes",
            "bits_hex",
            "keys",
            "steps",
            "counts",
        ],
    )
    assert json_int(state["version"]) == 1, "unsupported Bloom version"
    index: Filter = empty(json_int(state["expected"]), json_int(state["probability_ppm"]), json_int(state["capacity"]))
    assert (
        index.expected == configured.expected
        and index.probability_ppm == configured.probability_ppm
        and index.capacity == configured.capacity
    ), "configured sizing differs from saved state"
    assert (
        json_int(state["bit_count"]) == index.bit_count and json_int(state["hashes"]) == index.hashes
    ), "saved sizing differs from calculated sizing"
    previous: str = ""
    for value in json_array(state["keys"]):
        key: str = key_text(value)
        assert len(index.keys) == 0 or key > previous, "saved keys must be unique and sorted"
        assert len(index.keys) < index.capacity, "saved keys exceed capacity"
        index = insert(index, key)
        previous = key
    assert json_string(state["bits_hex"]) == index.bits.hex(), "saved bits differ from rebuilt audit keys"
    index.steps = bounded(state["steps"], 0, 1000000000)
    counters: Json = state["counts"]
    exact(counters, ["tests", "absent_tests", "false_positives", "ingests", "accepted", "duplicates", "refused"])
    counts: dict[str, int] = index.counts.copy()
    for name in counts:
        counts[name] = bounded(counters[name], 0, 1000000000)
    assert counts["accepted"] == len(index.keys), "accepted count differs from audit keys"
    assert (
        counts["accepted"] + counts["duplicates"] + counts["refused"] == counts["ingests"]
    ), "invalid ingestion counts"
    assert counts["ingests"] <= counts["tests"] <= index.steps, "invalid test counts"
    assert counts["false_positives"] <= counts["absent_tests"] <= counts["tests"], "invalid false-positive counts"
    assert counts["accepted"] + counts["refused"] <= counts["absent_tests"], "invalid absent counts"
    assert counts["duplicates"] <= counts["tests"] - counts["absent_tests"], "invalid duplicate counts"
    index.counts = counts
    return index
