"""A fixed-capacity circular buffer with inclusive time windows and numeric summaries."""

# ruff: noqa: PLR1711 - explicit returns in the typed subset

from dataclasses import dataclass

from py2rust.stdlib import Json, json_float, json_int, json_keys, json_string


@dataclass
class Sample:
    sequence: int
    time_ms: int
    value: float


@dataclass
class Ring:
    capacity: int
    window_ms: int
    clock_ms: int
    head: int
    count: int
    slots: list[Sample]
    stats: dict[str, int]


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def bounded(value: Json, minimum: int, maximum: int) -> int:
    number: int = json_int(value)
    assert minimum <= number <= maximum, "integer outside configured bounds"
    return number


def timestamp(value: Json) -> int:
    return bounded(value, 0, 253402300799999)


def numeric(value: Json) -> float:
    number: float = json_float(value)
    assert -1000000000.0 <= number <= 1000000000.0, "sample value exceeds magnitude limit"
    return 0.0 if number == 0.0 else number


def counter_names() -> list[str]:
    return ["steps", "ingested", "advances", "summaries", "exports", "inspections", "expired", "overwritten"]


def empty(capacity: int, window_ms: int) -> Ring:
    slots: list[Sample] = []
    for index in range(capacity):
        slots.append(Sample(0, 0, 0.0))
    stats: dict[str, int] = {}
    for name in counter_names():
        stats[name] = 0
    return Ring(capacity, window_ms, 0, 0, 0, slots, stats)


def document(sample: Sample) -> Json:
    return {"sequence": sample.sequence, "time_ms": sample.time_ms, "value": sample.value}


def select(ring: Ring, start_ms: int, end_ms: int) -> list[Sample]:
    result: list[Sample] = []
    for offset in range(ring.count):
        sample: Sample = ring.slots[(ring.head + offset) % ring.capacity]
        if start_ms <= sample.time_ms <= end_ms:
            result.append(sample)
    return result


def records(samples: list[Sample]) -> list[Json]:
    result: list[Json] = []
    for sample in samples:
        result.append(document(sample))
    return result


def magnitude(value: float) -> float:
    return value if value >= 0.0 else -value


def summary(samples: list[Sample]) -> Json:
    result: Json = {
        "count": len(samples),
        "sum": 0.0,
        "mean": None,
        "minimum": None,
        "maximum": None,
        "first_ms": None,
        "last_ms": None,
    }
    if len(samples) == 0:
        return result
    total: float = 0.0
    correction: float = 0.0
    low: float = samples[0].value
    high: float = low
    for sample in samples:
        value: float = sample.value
        combined: float = total + value
        # Neumaier summation retains small contributions during cancellation.
        if magnitude(total) >= magnitude(value):
            correction = correction + ((total - combined) + value)
        else:
            correction = correction + ((value - combined) + total)
        total = combined
        low = min(low, value)
        high = max(high, value)
    total = total + correction
    result["sum"] = 0.0 if total == 0.0 else total
    result["mean"] = total / float(len(samples))
    result["minimum"] = low
    result["maximum"] = high
    result["first_ms"] = samples[0].time_ms
    result["last_ms"] = samples[-1].time_ms
    return result


def view(ring: Ring) -> Json:
    return {
        "capacity": ring.capacity,
        "window_ms": ring.window_ms,
        "clock_ms": ring.clock_ms,
        "summary": summary(select(ring, 0, ring.clock_ms)),
        "stats": ring.stats,
    }


def advance(ring: Ring, now: int) -> Ring:
    assert now >= ring.clock_ms, "clock cannot move backwards"
    slots: list[Sample] = ring.slots
    stats: dict[str, int] = ring.stats
    while ring.count > 0 and slots[ring.head].time_ms < now - ring.window_ms:
        slots[ring.head] = Sample(0, 0, 0.0)
        ring.head = (ring.head + 1) % ring.capacity
        ring.count = ring.count - 1
        stats["expired"] = stats["expired"] + 1
    if ring.count == 0:
        ring.head = 0
    ring.clock_ms = now
    ring.slots = slots
    ring.stats = stats
    return ring


def apply(ring: Ring, command: Json) -> tuple[Ring, Json]:
    operation: str = json_string(command["op"])
    counters: dict[str, str] = {
        "INGEST": "ingested",
        "ADVANCE": "advances",
        "SUMMARY": "summaries",
        "EXPORT": "exports",
        "INSPECT": "inspections",
    }
    assert operation in counters, "unknown recorder operation"
    required: list[str] = ["op"]
    if operation in ["INGEST", "ADVANCE"]:
        required.append("time_ms")
    if operation == "INGEST":
        required.append("value")
    if operation in ["SUMMARY", "EXPORT"]:
        required.extend(["start_ms", "end_ms"])
    exact(command, required)
    stats: dict[str, int] = ring.stats
    assert stats["steps"] < 1000000000, "lifetime command limit reached"
    stats["steps"] = stats["steps"] + 1
    stats[counters[operation]] = stats[counters[operation]] + 1
    ring.stats = stats
    event: Json = {"step": stats["steps"], "op": operation}
    if operation in ["INGEST", "ADVANCE"]:
        before: int = stats["expired"]
        ring = advance(ring, timestamp(command["time_ms"]))
        event["expired"] = ring.stats["expired"] - before
        event["clock_ms"] = ring.clock_ms
    if operation == "INGEST":
        sample: Sample = Sample(stats["ingested"], ring.clock_ms, numeric(command["value"]))
        stats = ring.stats
        slots: list[Sample] = ring.slots
        overwritten: Json = None
        if ring.count == ring.capacity:
            overwritten = document(slots[ring.head])
            ring.head = (ring.head + 1) % ring.capacity
            ring.count = ring.count - 1
            stats["overwritten"] = stats["overwritten"] + 1
        slots[(ring.head + ring.count) % ring.capacity] = sample
        ring.count = ring.count + 1
        ring.slots = slots
        ring.stats = stats
        event["sample"] = document(sample)
        event["overwritten"] = overwritten
    elif operation in ["SUMMARY", "EXPORT"]:
        start: int = timestamp(command["start_ms"])
        end: int = timestamp(command["end_ms"])
        assert start <= end, "interval start exceeds end"
        selected: list[Sample] = select(ring, start, end)
        event["start_ms"] = start
        event["end_ms"] = end
        if operation == "SUMMARY":
            event["summary"] = summary(selected)
        else:
            event["samples"] = records(selected)
    elif operation == "INSPECT":
        event["recorder"] = view(ring)
    return (ring, event)
