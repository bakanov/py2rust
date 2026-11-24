# ruff: noqa: PLR1711, C414 - explicit returns and supported subset operations
"""Stable min-priority scheduling; running jobs remain available for acknowledgement or retry."""

import heapq
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
class Queue:
    capacity: int
    next_sequence: int
    jobs: dict[str, Json]
    heap: list[tuple[int, int, str]]
    stats: dict[str, int]


def counters() -> list[str]:
    return ["steps", "enqueued", "popped", "retried", "completed", "cancelled_queued", "cancelled_running"]


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def capacity(value: Json) -> int:
    result: int = json_int(value)
    assert 1 <= result <= 256, "capacity must be 1..256"
    return result


def identifier(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result.encode()) <= 128, "job ID must contain 1..128 UTF-8 bytes"
    return result


def depth(value: Json, level: int) -> None:
    assert level <= 16, "payload nesting exceeds 16"
    if json_kind(value) == "array":
        for item in json_array(value):
            depth(item, level + 1)
    elif json_kind(value) == "object":
        for name in json_keys(value):
            depth(value[name], level + 1)
    return


def payload(value: Json) -> None:
    depth(value, 0)
    assert len(json_canonical(value).encode()) <= 16384, "payload exceeds 16 KiB"
    return


def empty(size: int) -> Queue:
    jobs: dict[str, Json] = {}
    heap: list[tuple[int, int, str]] = []
    stats: dict[str, int] = {}
    for name in counters():
        stats[name] = 0
    return Queue(size, 1, jobs, heap, stats)


def rebuild(jobs: dict[str, Json]) -> list[tuple[int, int, str]]:
    heap: list[tuple[int, int, str]] = []
    for name in jobs:
        if json_string(jobs[name]["status"]) == "queued":
            heap.append((json_int(jobs[name]["priority"]), json_int(jobs[name]["sequence"]), name))
    heapq.heapify(heap)
    return heap


def current(ticket: tuple[int, int, str], jobs: dict[str, Json]) -> bool:
    name: str = ticket[2]
    return (
        name in jobs and json_string(jobs[name]["status"]) == "queued" and json_int(jobs[name]["sequence"]) == ticket[1]
    )


def view(queue: Queue) -> Json:
    heap: list[tuple[int, int, str]] = rebuild(queue.jobs)
    queued: list[Json] = []
    while len(heap) > 0:
        ticket: tuple[int, int, str] = heapq.heappop(heap)
        queued.append(queue.jobs[ticket[2]])
    running: list[Json] = []
    for name in sorted(list(queue.jobs)):
        if json_string(queue.jobs[name]["status"]) == "running":
            running.append(queue.jobs[name])
    return {"queued": queued, "running": running, "capacity": queue.capacity, "stats": queue.stats}


def apply(queue: Queue, command: Json) -> tuple[Queue, Json]:
    operation: str = json_string(command["op"])
    assert operation in ["ENQUEUE", "POP", "PEEK", "ACK", "CANCEL", "RETRY", "INSPECT"], "unknown queue operation"
    fields: list[str] = ["op"]
    name: str = ""
    if operation in ["ENQUEUE", "ACK", "CANCEL", "RETRY"]:
        fields.append("id")
        name = identifier(command["id"])
    priority: int = 0
    if operation in ["ENQUEUE", "RETRY"]:
        fields.append("priority")
        priority = json_int(command["priority"])
    if operation == "ENQUEUE":
        fields.append("payload")
        payload(command["payload"])
    exact(command, fields)
    jobs: dict[str, Json] = queue.jobs
    heap: list[tuple[int, int, str]] = queue.heap
    stats: dict[str, int] = queue.stats
    sequence: int = queue.next_sequence
    assert stats["steps"] < 1000000000, "lifetime command limit reached"
    stats["steps"] = stats["steps"] + 1
    event: Json = {"step": stats["steps"], "op": operation, "accepted": True}
    if operation in ["ENQUEUE", "ACK", "CANCEL", "RETRY"]:
        event["id"] = name
    reason: str = ""
    if operation == "ENQUEUE":
        if name in jobs:
            reason = "duplicate_id"
        elif len(jobs) >= queue.capacity:
            reason = "capacity"
        else:
            jobs[name] = {
                "id": name,
                "priority": priority,
                "sequence": sequence,
                "payload": command["payload"],
                "status": "queued",
                "attempts": 0,
            }
            heapq.heappush(heap, (priority, sequence, name))
            sequence = sequence + 1
            stats["enqueued"] = stats["enqueued"] + 1
            event["job"] = jobs[name]
    elif operation in ["POP", "PEEK"]:
        while len(heap) > 0 and not current(heap[0], jobs):
            heapq.heappop(heap)
        event["job"] = None
        if len(heap) == 0:
            reason = "empty"
        else:
            name = heap[0][2]
            job: Json = jobs[name]
            if operation == "POP":
                heapq.heappop(heap)
                job["status"] = "running"
                job["attempts"] = json_int(job["attempts"]) + 1
                jobs[name] = job
                stats["popped"] = stats["popped"] + 1
            event["job"] = job
    elif operation in ["ACK", "RETRY", "CANCEL"]:
        if name not in jobs:
            reason = "not_found"
        elif operation != "CANCEL" and json_string(jobs[name]["status"]) != "running":
            reason = "not_running"
        else:
            job: Json = jobs[name]
            if operation == "RETRY":
                job["priority"] = priority
                job["sequence"] = sequence
                job["status"] = "queued"
                jobs[name] = job
                heapq.heappush(heap, (priority, sequence, name))
                sequence = sequence + 1
                stats["retried"] = stats["retried"] + 1
            else:
                counter: str = "completed" if operation == "ACK" else "cancelled_" + json_string(job["status"])
                stats[counter] = stats[counter] + 1
                del jobs[name]
            event["job"] = job
    if reason != "":
        event["accepted"] = False
        event["reason"] = reason
    # Cancellation leaves stale tickets. Bound them independently of the trace length.
    if len(heap) > queue.capacity * 2 + 16:
        heap = rebuild(jobs)
    result: Queue = Queue(queue.capacity, sequence, jobs, heap, stats)
    if operation == "INSPECT":
        event["queue"] = view(result)
    return (result, event)
