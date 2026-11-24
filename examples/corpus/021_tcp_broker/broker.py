"""Idempotent submissions, durable acknowledgments and bounded pending pagination."""

from storage import find, identifier, load, payload_valid, save

from py2rust.stdlib import (
    Json,
    json_array,
    json_dumps,
    json_equal,
    json_get,
    json_int,
    json_keys,
    json_string,
)


def failure(code: str) -> Json:
    return {"ok": False, "error": code}


def receipt(job: Json, duplicate: bool) -> Json:
    return {"ok": True, "id": job["id"], "sequence": job["sequence"], "state": job["state"], "duplicate": duplicate}


def submit(request: Json, state: Json, policy: Json) -> Json:
    assert json_keys(request) == ["id", "op", "payload"], "invalid submit fields"
    name: str = identifier(request["id"])
    payload_valid(request["payload"], policy)
    index: int = find(state, name)
    jobs: list[Json] = json_array(state["jobs"])
    if index >= 0:
        if not json_equal(jobs[index]["payload"], request["payload"]):
            return failure("id_conflict")
        return receipt(jobs[index], True)
    if len(jobs) >= json_int(policy["max_jobs"]):
        return failure("capacity")
    sequence: int = json_int(state["next_sequence"])
    job: Json = {"id": name, "payload": request["payload"], "sequence": sequence, "state": "pending"}
    jobs.append(job)
    state["jobs"] = jobs
    state["next_sequence"] = sequence + 1
    save(state, policy)
    return receipt(job, False)


def acknowledge(request: Json, state: Json, policy: Json) -> Json:
    assert json_keys(request) == ["id", "op"], "invalid acknowledgment fields"
    index: int = find(state, identifier(request["id"]))
    if index < 0:
        return failure("not_found")
    jobs: list[Json] = json_array(state["jobs"])
    job: Json = jobs[index]
    if json_string(job["state"]) == "done":
        return receipt(job, True)
    job["state"] = "done"
    jobs[index] = job
    state["jobs"] = jobs
    save(state, policy)
    return receipt(job, False)


def pending(request: Json, state: Json, policy: Json) -> Json:
    for key in json_keys(request):
        assert key in ["op", "after", "limit"], "invalid pending fields"
    after: int = json_int(json_get(request, "after", 0))
    limit: int = json_int(json_get(request, "limit", 20))
    assert after >= 0 and limit >= 1 and limit <= 100, "invalid pagination"
    jobs: list[Json] = []
    result: Json = {"ok": True, "jobs": jobs, "next": after, "more": False}
    for job in json_array(state["jobs"]):
        if json_string(job["state"]) == "pending" and json_int(job["sequence"]) > after:
            proposed: list[Json] = jobs.copy()
            proposed.append(job)
            candidate: Json = {"ok": True, "jobs": proposed, "next": job["sequence"], "more": False}
            if len(proposed) > limit or len(json_dumps(candidate).encode()) > json_int(policy["max_frame"]):
                result["more"] = True
                return result
            jobs = proposed
            result = candidate
    return result


def dispatch(request: Json, policy: Json) -> Json:
    operation: str = json_string(request["op"])
    state: Json = load(policy)
    if operation == "submit":
        return submit(request, state, policy)
    if operation == "ack":
        return acknowledge(request, state, policy)
    if operation == "pending":
        return pending(request, state, policy)
    if operation == "get":
        assert json_keys(request) == ["id", "op"], "invalid get fields"
        index: int = find(state, identifier(request["id"]))
        if index < 0:
            return failure("not_found")
        return {"ok": True, "job": state["jobs"][index]}
    if operation == "stats":
        assert json_keys(request) == ["op"], "invalid stats fields"
        count: int = 0
        jobs: list[Json] = json_array(state["jobs"])
        for job in jobs:
            if json_string(job["state"]) == "pending":
                count = count + 1
        return {
            "ok": True,
            "accepted": len(jobs),
            "pending": count,
            "done": len(jobs) - count,
            "next_sequence": state["next_sequence"],
            "capacity": policy["max_jobs"],
        }
    return failure("unknown_operation")
