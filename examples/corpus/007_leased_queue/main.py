"""Enqueue, lease and acknowledge jobs without accepting stale worker receipts."""

from model import (
    clear_lease,
    configure,
    copy_record,
    matches,
    normalize_job,
    public,
    setting,
    valid_name,
    valid_token,
)
from storage import find, initialize, load, refresh, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_array,
    json_dumps,
    json_equal,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    random_token,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(value).encode(), headers)


def enqueue(request: WebRequest) -> WebResponse:
    job: Json = None
    try:
        job = normalize_job(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid job"})
    state: Json = refresh()
    jobs: list[Json] = json_array(state["jobs"])
    index: int = find(jobs, json_string(job["id"]))
    if index >= 0:
        if not json_equal(jobs[index]["job"], job):
            return reply(409, {"error": "job ID has different content"})
        return reply(200, {"job": public(jobs[index]), "duplicate": True})
    if len(jobs) >= setting("QUEUE_LIMIT", 1000):
        return reply(507, {"error": "queue receipt storage is full"})
    now: float = json_float(state["clock"])
    delay: float = json_int(job["delay"])
    record: Json = {
        "job": job,
        "created": now,
        "available_at": now + delay,
        "state": "pending",
        "attempts": 0,
        "worker": "",
        "token": "",
        "lease_until": 0.0,
        "completed_at": 0.0,
    }
    jobs.append(record)
    state["jobs"] = jobs
    save(state)
    return reply(201, {"job": public(record), "duplicate": False})


def claim(request: WebRequest) -> WebResponse:
    queue: str = ""
    worker: str = ""
    seconds: int = 0
    try:
        value: Json = json_loads(request.body.decode())
        for key in json_keys(value):
            assert key in ["queue", "worker", "seconds"], "unexpected claim field"
        queue = json_string(json_get(value, "queue", "main"))
        worker = json_string(value["worker"])
        seconds = json_int(json_get(value, "seconds", setting("QUEUE_LEASE", 30)))
        assert valid_name(queue) and valid_name(worker) and seconds >= 1 and seconds <= 3600, "invalid claim"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid worker, queue or lease interval"})
    state: Json = refresh()
    now: float = json_float(state["clock"])
    jobs: list[Json] = json_array(state["jobs"])
    selected: int = -1
    priority: int = -1
    for index in range(len(jobs)):
        record: Json = jobs[index]
        if (
            json_string(record["job"]["queue"]) == queue
            and json_string(record["state"]) == "pending"
            and json_float(record["available_at"]) <= now
            and json_int(record["job"]["priority"]) > priority
        ):
            selected = index
            priority = json_int(record["job"]["priority"])
    if selected < 0:
        return reply(200, {"job": None})
    changed: Json = copy_record(jobs[selected])
    token: str = random_token()
    for record in jobs:
        assert json_string(record["token"]) != token, "lease token collision; retry claim"
    duration: float = seconds
    changed["state"] = "leased"
    changed["attempts"] = json_int(changed["attempts"]) + 1
    changed["worker"] = worker
    changed["token"] = token
    changed["lease_until"] = now + duration
    jobs[selected] = changed
    state["jobs"] = jobs
    save(state)
    return reply(200, {"job": public(changed), "token": token})


def finish(request: WebRequest, action: str) -> WebResponse:
    identifier: str = ""
    worker: str = ""
    token: str = ""
    delay: int = 0
    try:
        value: Json = json_loads(request.body.decode())
        keys: list[str] = json_keys(value)
        assert keys == ["id", "token", "worker"] or (
            action == "release" and keys == ["delay", "id", "token", "worker"]
        ), "invalid receipt fields"
        identifier = json_string(value["id"])
        worker = json_string(value["worker"])
        token = json_string(value["token"])
        delay = json_int(json_get(value, "delay", 0))
        assert valid_name(identifier) and valid_name(worker) and valid_token(token), "invalid receipt"
        assert delay >= 0 and delay <= 86400, "invalid retry delay"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid lease receipt"})
    state: Json = refresh()
    jobs: list[Json] = json_array(state["jobs"])
    index: int = find(jobs, identifier)
    if index < 0:
        return reply(404, {"error": "unknown job"})
    record: Json = jobs[index]
    if not matches(record, worker, token):
        return reply(409, {"error": "stale or foreign lease"})
    if json_string(record["state"]) == "done" and action == "ack":
        return reply(200, {"job": public(record), "duplicate": True})
    if json_string(record["state"]) != "leased":
        return reply(409, {"error": "job is not leased"})
    now: float = json_float(state["clock"])
    changed: Json = copy_record(record)
    if action == "ack":
        changed["state"] = "done"
        changed["lease_until"] = 0.0
        changed["completed_at"] = now
    else:
        interval: float = delay
        changed = clear_lease(record, now + interval)
    jobs[index] = changed
    state["jobs"] = jobs
    save(state)
    return reply(200, {"job": public(changed), "duplicate": False})


def dispatch(request: WebRequest) -> WebResponse:
    if len(request.body) > 65536:
        return reply(413, {"error": "request exceeds byte limit"})
    if request.path == "/jobs" and request.method == "POST":
        return enqueue(request)
    if request.path == "/claim" and request.method == "POST":
        return claim(request)
    if request.path == "/ack" and request.method == "POST":
        return finish(request, "ack")
    if request.path == "/release" and request.method == "POST":
        return finish(request, "release")
    if request.path.startswith("/jobs/"):
        identifier: str = request.path[6:]
        state: Json = refresh()
        jobs: list[Json] = json_array(state["jobs"])
        index: int = find(jobs, identifier)
        if index < 0:
            return reply(404, {"error": "unknown job"})
        if request.method == "GET":
            return reply(200, public(jobs[index]))
        if request.method == "DELETE":
            if json_string(jobs[index]["state"]) != "done":
                return reply(409, {"error": "only completed receipts can be removed"})
            kept: list[Json] = []
            for record in jobs:
                if json_string(record["job"]["id"]) != identifier:
                    kept.append(record)
            state["jobs"] = kept
            save(state)
            return reply(200, {"deleted": identifier})
        return reply(405, {"error": "use GET or DELETE"})
    if request.path == "/jobs" and request.method == "GET":
        records: list[Json] = []
        for record in json_array(refresh()["jobs"]):
            if request.query.get("queue", "") in ["", json_string(record["job"]["queue"])] and request.query.get(
                "state", ""
            ) in ["", json_string(record["state"])]:
                records.append(public(record))
        return reply(200, {"jobs": records, "count": len(records)})
    if request.path == "/sweep" and request.method == "POST":
        before: list[Json] = json_array(load()["jobs"])
        after: list[Json] = json_array(refresh()["jobs"])
        expired: list[str] = []
        for index in range(len(before)):
            if json_string(before[index]["state"]) == "leased" and json_string(after[index]["state"]) == "pending":
                expired.append(json_string(after[index]["job"]["id"]))
        return reply(200, {"requeued": expired})
    return reply(404, {"error": "unknown route"})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "queue storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve("127.0.0.1", setting("QUEUE_PORT", 8772), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
