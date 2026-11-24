"""A balanced interval tree with cached subtree bounds and deterministic query ordering."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns and ordered key iteration

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
class Event:
    identifier: str
    start_ms: int
    end_ms: int
    text: str
    data: Json


@dataclass
class Node:
    event: Event
    children: list["Node"]
    minimum: int
    maximum: int
    count: int
    height: int


@dataclass
class Index:
    capacity: int
    steps: int
    events: dict[str, Event]
    root: Node


@dataclass
class Matches:
    rows: list[Event]
    visited: int


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def bounded(value: Json, minimum: int, maximum: int) -> int:
    number: int = json_int(value)
    assert minimum <= number <= maximum, "integer outside bounds"
    return number


def text(value: Json, limit: int, allow_empty: bool) -> str:
    result: str = json_string(value)
    assert len(result) <= limit and len(result.encode()) <= limit * 4, "text exceeds size limit"
    assert allow_empty or result != "", "empty identifier"
    return result


def depth(value: Json, level: int) -> None:
    assert level <= 8, "payload nesting exceeds eight"
    if json_kind(value) == "array":
        for item in json_array(value):
            depth(item, level + 1)
    elif json_kind(value) == "object":
        for name in json_keys(value):
            depth(value[name], level + 1)
    return


def parse(value: Json) -> Event:
    exact(value, ["id", "start_ms", "end_ms", "text", "data"])
    identifier: str = text(value["id"], 64, False)
    start: int = json_int(value["start_ms"])
    end: int = json_int(value["end_ms"])
    assert start <= end, "span start exceeds end"
    label: str = text(value["text"], 256, True)
    depth(value["data"], 0)
    assert len(json_canonical(value["data"]).encode()) <= 4096, "payload exceeds 4 KiB"
    return Event(identifier, start, end, label, value["data"])


def document(event: Event) -> Json:
    return {
        "id": event.identifier,
        "start_ms": event.start_ms,
        "end_ms": event.end_ms,
        "text": event.text,
        "data": event.data,
    }


def rank(event: Event) -> tuple[int, int, str]:
    return (event.start_ms, event.end_ms, event.identifier)


def blank() -> Node:
    return Node(Event("", 0, 0, "", None), [], 0, 0, 0, 0)


def build(rows: list[Event]) -> Node:
    if len(rows) == 0:
        return blank()
    middle: int = len(rows) // 2
    event: Event = rows[middle]
    left: Node = build(rows[:middle])
    right: Node = build(rows[middle + 1 :])
    minimum: int = event.start_ms
    maximum: int = event.end_ms
    for child in [left, right]:
        if child.count > 0:
            minimum = min(minimum, child.minimum)
            maximum = max(maximum, child.maximum)
    return Node(event, [left, right], minimum, maximum, len(rows), 1 + max(left.height, right.height))


def ordered(events: dict[str, Event]) -> list[Event]:
    rows: list[Event] = []
    for name in events:
        rows.append(events[name])
    return sorted(rows, key=rank)


def rebuild(index: Index) -> Index:
    index.root = build(ordered(index.events))
    return index


def empty(capacity: int) -> Index:
    return Index(capacity, 0, {}, blank())


def search(node: Node, start: int, end: int, point: bool, needle: str) -> Matches:
    if node.count == 0 or node.maximum <= start:
        return Matches([], 0)
    if (point and node.minimum > start) or (not point and (start == end or node.minimum >= end)):
        return Matches([], 0)
    left: Matches = search(node.children[0], start, end, point, needle)
    event: Event = node.event
    overlaps: bool = (
        event.start_ms <= start < event.end_ms
        if point
        else (event.start_ms < event.end_ms and event.start_ms < end and start < event.end_ms)
    )
    rows: list[Event] = left.rows
    if overlaps and needle in event.text.casefold():
        rows.append(event)
    right: Matches = search(node.children[1], start, end, point, needle)
    rows.extend(right.rows)
    return Matches(rows, 1 + left.visited + right.visited)


def view(index: Index) -> Json:
    return {
        "capacity": index.capacity,
        "steps": index.steps,
        "records": len(index.events),
        "height": index.root.height,
        "minimum_start_ms": index.root.minimum if index.root.count > 0 else None,
        "maximum_end_ms": index.root.maximum if index.root.count > 0 else None,
    }


def query(index: Index, command: Json, point: bool) -> Json:
    start: int = json_int(command["time_ms"] if point else command["start_ms"])
    end: int = start if point else json_int(command["end_ms"])
    assert start <= end, "query start exceeds end"
    needle: str = text(command["text"], 256, True).casefold()
    offset: int = bounded(command["offset"], 0, 1024)
    limit: int = bounded(command["limit"], 1, 1024)
    matches: Matches = search(index.root, start, end, point, needle)
    hits: list[Json] = []
    for position in range(offset, min(len(matches.rows), offset + limit)):
        hits.append(document(matches.rows[position]))
    return {
        "hits": hits,
        "count": len(matches.rows),
        "more": offset + limit < len(matches.rows),
        "visited_nodes": matches.visited,
    }


def apply(index: Index, command: Json) -> tuple[Index, Json]:
    operation: str = json_string(command["op"])
    assert operation in ["PUT", "DELETE", "GET", "QUERY", "POINT", "INSPECT"], "unknown browser operation"
    fields: list[str] = ["op"]
    if operation == "PUT":
        fields.append("event")
    elif operation in ["DELETE", "GET"]:
        fields.append("id")
    elif operation in ["QUERY", "POINT"]:
        fields.extend(["text", "offset", "limit"])
        fields.extend(["time_ms"] if operation == "POINT" else ["start_ms", "end_ms"])
    exact(command, fields)
    assert index.steps < 1000000000, "lifetime command limit reached"
    index.steps = index.steps + 1
    result: Json = {"step": index.steps, "op": operation}
    events: dict[str, Event] = index.events
    if operation == "PUT":
        event: Event = parse(command["event"])
        found: bool = event.identifier in events
        accepted: bool = found or len(events) < index.capacity
        result["accepted"] = accepted
        result["previous"] = document(events[event.identifier]) if found else None
        if accepted:
            events[event.identifier] = event
            index.events = events
            index = rebuild(index)
        else:
            result["reason"] = "capacity"
    elif operation in ["DELETE", "GET"]:
        name: str = text(command["id"], 64, False)
        found: bool = name in events
        result["found"] = found
        result["event"] = document(events[name]) if found else None
        if operation == "DELETE" and found:
            del events[name]
            index.events = events
            index = rebuild(index)
    elif operation in ["QUERY", "POINT"]:
        result["result"] = query(index, command, operation == "POINT")
    else:
        result["index"] = view(index)
    return (index, result)
