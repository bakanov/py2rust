# ruff: noqa: C414 - explicit returns and supported subset operations
"""Snapshots store logical jobs and counters; restoration rebuilds the heap from fresh tickets."""

from model import Queue, capacity, counters, exact, identifier, payload, rebuild

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


def save(queue: Queue) -> str:
    jobs: list[Json] = []
    for name in sorted(list(queue.jobs)):
        jobs.append(queue.jobs[name])
    state: Json = {
        "version": 1,
        "capacity": queue.capacity,
        "next_sequence": queue.next_sequence,
        "jobs": jobs,
        "stats": queue.stats,
    }
    return json_canonical({"state": state, "sha256": digest(state)}) + "\n"


def restore(envelope: Json, expected_capacity: int) -> Queue:
    exact(envelope, ["state", "sha256"])
    state: Json = envelope["state"]
    assert digest(state) == json_string(envelope["sha256"]), "snapshot checksum mismatch"
    exact(state, ["version", "capacity", "next_sequence", "jobs", "stats"])
    assert json_int(state["version"]) == 1, "unsupported queue snapshot version"
    size: int = capacity(state["capacity"])
    assert size == expected_capacity, "configured capacity differs from saved state"
    stats: dict[str, int] = {}
    exact(state["stats"], counters())
    for name in counters():
        stats[name] = json_int(state["stats"][name])
        assert 0 <= stats[name] <= 1000000000, "invalid lifetime counter"
    accepted: int = (
        stats["enqueued"]
        + stats["popped"]
        + stats["retried"]
        + stats["completed"]
        + stats["cancelled_queued"]
        + stats["cancelled_running"]
    )
    assert accepted <= stats["steps"], "accepted operations exceed command count"
    sequence: int = json_int(state["next_sequence"])
    assert sequence == 1 + stats["enqueued"] + stats["retried"], "inconsistent next sequence"
    jobs: dict[str, Json] = {}
    seen: set[int] = set()
    running: int = 0
    attempts: int = 0
    for job in json_array(state["jobs"]):
        exact(job, ["id", "priority", "sequence", "payload", "status", "attempts"])
        name: str = identifier(job["id"])
        assert name not in jobs, "duplicate job ID"
        json_int(job["priority"])
        ticket: int = json_int(job["sequence"])
        assert 1 <= ticket < sequence and ticket not in seen, "invalid or duplicate sequence"
        seen.add(ticket)
        status: str = json_string(job["status"])
        assert status in ["queued", "running"], "invalid job status"
        count: int = json_int(job["attempts"])
        assert 0 <= count <= stats["popped"], "invalid attempt count"
        if status == "running":
            assert count > 0, "running job has never been popped"
            running = running + 1
        attempts = attempts + count
        payload(job["payload"])
        jobs[name] = job
    assert len(jobs) <= size, "saved jobs exceed capacity"
    assert attempts <= stats["popped"], "retained attempts exceed pop count"
    assert (
        attempts + stats["completed"] + stats["cancelled_running"] <= stats["popped"]
    ), "removed running jobs need attempts"
    if stats["completed"] + stats["cancelled_queued"] + stats["cancelled_running"] == 0:
        assert attempts == stats["popped"], "unaccounted retained attempts"
    assert (
        len(jobs) == stats["enqueued"] - stats["completed"] - stats["cancelled_queued"] - stats["cancelled_running"]
    ), "inconsistent job count"
    assert (
        running == stats["popped"] - stats["retried"] - stats["completed"] - stats["cancelled_running"]
    ), "inconsistent running count"
    return Queue(size, sequence, jobs, rebuild(jobs), stats)
