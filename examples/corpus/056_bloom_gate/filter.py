"""A sized Bloom filter and exact audit set; probable duplicates never silently discard new keys."""

# ruff: noqa: PLR1711, C414 - explicit returns and typed conversions

import math
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_int,
    json_keys,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Filter:
    expected: int
    probability_ppm: int
    capacity: int
    bit_count: int
    hashes: int
    bits: bytearray
    keys: set[str]
    steps: int
    counts: dict[str, int]


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def bounded(value: Json, lower: int, upper: int) -> int:
    number: int = json_int(value)
    assert lower <= number <= upper, "integer outside configured bounds"
    return number


def key_text(value: Json) -> str:
    key: str = json_string(value)
    assert len(key) <= 128 and len(key.encode()) <= 512, "key exceeds 128 characters or 512 UTF-8 bytes"
    return key


def empty(expected: int, probability_ppm: int, capacity: int) -> Filter:
    assert 1 <= expected <= 4096 and 1 <= capacity <= 4096, "expected count and capacity must be 1..4096"
    assert 1 <= probability_ppm <= 999999, "probability must be 1..999999 ppm"
    logarithm: float = math.log(2.0)
    bit_count: int = math.ceil(-float(expected) * math.log(probability_ppm / 1000000) / (logarithm * logarithm))
    hashes: int = max(1, math.floor(bit_count / expected * logarithm + 0.5))
    assert 1 <= bit_count <= 117784 and 1 <= hashes <= 32, "sizing result outside bounds"
    counts: dict[str, int] = {
        "tests": 0,
        "absent_tests": 0,
        "false_positives": 0,
        "ingests": 0,
        "accepted": 0,
        "duplicates": 0,
        "refused": 0,
    }
    return Filter(
        expected, probability_ppm, capacity, bit_count, hashes, bytearray((bit_count + 7) // 8), set(), 0, counts
    )


def positions(index: Filter, key: str) -> list[int]:
    result: list[int] = []
    for number in range(index.hashes):
        payload: bytes = b"py2rust-bloom-v1\x00" + number.to_bytes(2, "big") + key.encode()
        digest: bytes = bytes.fromhex(sha256_digest(sha256_update(sha256_new(), payload)))
        result.append(int.from_bytes(digest[:7], "big") % index.bit_count)
    return result


def likely(index: Filter, key: str) -> bool:
    for position in positions(index, key):
        if index.bits[position // 8] & (1 << (position % 8)) == 0:
            return False
    return True


def insert(index: Filter, key: str) -> Filter:
    bits: bytearray = index.bits.copy()
    for position in positions(index, key):
        bits[position // 8] = bits[position // 8] | (1 << (position % 8))
    keys: set[str] = index.keys.copy()
    keys.add(key)
    index.bits = bits
    index.keys = keys
    return index


def summary(index: Filter) -> Json:
    occupied: int = 0
    for value in index.bits:
        while value != 0:
            occupied = occupied + 1
            value = value & (value - 1)
    payload_bytes: int = 0
    for key in index.keys:
        payload_bytes = payload_bytes + len(key.encode())
    measured: Json = None
    if index.counts["absent_tests"] > 0:
        measured = index.counts["false_positives"] * 1000000 // index.counts["absent_tests"]
    return {
        "expected": index.expected,
        "target_probability_ppm": index.probability_ppm,
        "capacity": index.capacity,
        "keys": len(index.keys),
        "bit_count": index.bit_count,
        "hashes": index.hashes,
        "filter_bytes": len(index.bits),
        "occupied_bits": occupied,
        "audit_key_utf8_bytes": payload_bytes,
        "counts": index.counts,
        "measured_false_positive_ppm": measured,
    }


def apply(index: Filter, command: Json) -> tuple[Filter, Json]:
    operation: str = json_string(command["op"])
    assert operation in ["INGEST", "CHECK", "INSPECT", "EXPORT"], "unknown operation"
    exact(command, ["op", "key"] if operation in ["INGEST", "CHECK"] else ["op"])
    assert index.steps < 1000000000, "step limit reached"
    index.steps = index.steps + 1
    event: Json = {"step": index.steps, "op": operation}
    if operation == "INSPECT":
        event["filter"] = summary(index)
    elif operation == "EXPORT":
        event["keys"] = sorted(list(index.keys))
    else:
        key: str = key_text(command["key"])
        present: bool = key in index.keys
        probable: bool = likely(index, key)
        assert not present or probable, "inserted key produced a false negative"
        counts: dict[str, int] = index.counts.copy()
        counts["tests"] = counts["tests"] + 1
        if not present:
            counts["absent_tests"] = counts["absent_tests"] + 1
            if probable:
                counts["false_positives"] = counts["false_positives"] + 1
        event["key"] = key
        event["likely_duplicate"] = probable
        event["exact_duplicate"] = present
        event["false_positive"] = probable and not present
        if operation == "INGEST":
            counts["ingests"] = counts["ingests"] + 1
            decision: str = "duplicate" if present else "accepted"
            if not present and len(index.keys) >= index.capacity:
                decision = "refused"
            if decision == "accepted":
                index = insert(index, key)
            counter: str = "duplicates" if decision == "duplicate" else decision
            counts[counter] = counts[counter] + 1
            event["decision"] = decision
        index.counts = counts
    return (index, event)
