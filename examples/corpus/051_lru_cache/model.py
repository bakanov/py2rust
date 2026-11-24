"""An insertion-ordered mapping is the cache's LRU-to-MRU order; values remain opaque JSON."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_string,
)


@dataclass
class Cache:
    capacity: int
    values: dict[str, Json]
    stats: dict[str, int]


def counters() -> list[str]:
    return [
        "steps",
        "gets",
        "hits",
        "misses",
        "puts",
        "overwrites",
        "dropped",
        "deletes",
        "deleted",
        "evictions",
        "resizes",
        "peeks",
        "inspections",
    ]


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return  # noqa: PLR1711


def capacity(value: Json) -> int:
    result: int = json_int(value)
    assert 0 <= result <= 256, "capacity must be 0..256"
    return result


def key(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result.encode()) <= 128, "key must contain 1..128 UTF-8 bytes"
    return result


def depth(value: Json, level: int) -> None:
    assert level <= 16, "value nesting exceeds 16"
    if json_kind(value) == "array":
        for item in json_array(value):
            depth(item, level + 1)
    elif json_kind(value) == "object":
        for name in json_keys(value):
            depth(value[name], level + 1)
    return  # noqa: PLR1711


def value_check(value: Json) -> None:
    depth(value, 0)
    assert len(json_canonical(value).encode()) <= 16384, "value exceeds 16 KiB"
    return  # noqa: PLR1711


def empty(size: int) -> Cache:
    values: dict[str, Json] = {}
    stats: dict[str, int] = {}
    for name in counters():
        stats[name] = 0
    return Cache(size, values, stats)


def entries(values: dict[str, Json]) -> list[Json]:
    result: list[Json] = []
    for name in values:  # noqa: PLC0206 - ordered key iteration in the subset
        result.append({"key": name, "value": values[name]})
    return result


def metrics(stats: dict[str, int]) -> Json:
    rate: float = 0.0
    if stats["gets"] > 0:
        rate = stats["hits"] / stats["gets"]
    return {"counters": stats, "hit_rate": rate}


def apply(cache: Cache, command: Json) -> tuple[Cache, Json]:
    operation: str = json_string(command["op"])
    required: list[str] = ["op", "key"]
    if operation == "PUT":
        required.append("value")
    elif operation == "RESIZE":
        required = ["op", "capacity"]
    elif operation == "INSPECT":
        required = ["op"]
    assert operation in ["GET", "PUT", "DELETE", "RESIZE", "PEEK", "INSPECT"], "unknown cache operation"
    exact(command, required)
    name: str = ""
    if operation in ["GET", "PUT", "DELETE", "PEEK"]:
        name = key(command["key"])
    if operation == "PUT":
        value_check(command["value"])
    size: int = capacity(command["capacity"]) if operation == "RESIZE" else cache.capacity
    values: dict[str, Json] = cache.values
    stats: dict[str, int] = cache.stats
    stats["steps"] = stats["steps"] + 1
    event: Json = {"step": stats["steps"], "op": operation}
    found: bool = name in values
    previous: Json = values.get(name, None)
    if operation in ["GET", "PEEK"]:
        event["key"] = name
        event["hit"] = found
        event["value"] = previous
        if operation == "GET":
            stats["gets"] = stats["gets"] + 1
            counter: str = "hits" if found else "misses"
            stats[counter] = stats[counter] + 1
            if found:
                del values[name]
                values[name] = previous
        else:
            stats["peeks"] = stats["peeks"] + 1
    elif operation == "PUT":
        stats["puts"] = stats["puts"] + 1
        if found:
            del values[name]
            stats["overwrites"] = stats["overwrites"] + 1
        if size > 0:
            values[name] = command["value"]
        else:
            stats["dropped"] = stats["dropped"] + 1
        event["key"] = name
        event["stored"] = size > 0
        event["replaced"] = found
        event["previous"] = previous
    elif operation == "DELETE":
        stats["deletes"] = stats["deletes"] + 1
        if found:
            del values[name]
            stats["deleted"] = stats["deleted"] + 1
        event["key"] = name
        event["deleted"] = found
        event["value"] = previous
    elif operation == "RESIZE":
        stats["resizes"] = stats["resizes"] + 1
        event["capacity"] = size
    else:
        stats["inspections"] = stats["inspections"] + 1
        event["capacity"] = size
        event["entries"] = entries(values)
        event["stats"] = metrics(stats)
    if operation in ["PUT", "RESIZE"]:
        evicted: list[Json] = []
        for victim in list(values):
            if len(values) <= size:
                break
            evicted.append({"key": victim, "value": values[victim]})
            del values[victim]
            stats["evictions"] = stats["evictions"] + 1
        event["evicted"] = evicted
    return (Cache(size, values, stats), event)
