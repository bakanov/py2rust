"""Prove durable claims, exact lease fencing, priority and worker retries."""

import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import Application, Response, Server


def post(server: Server, path: str, value: object) -> Response:
    return server.request("POST", path, json.dumps(value).encode())


def receipt(claim: dict) -> dict:
    return {"id": claim["job"]["id"], "worker": claim["job"]["worker"], "token": claim["token"]}


def check(app: Application, directory: Path) -> dict:
    state = directory / "queue.json"
    settings = {"QUEUE_STATE": str(state), "QUEUE_PORT": "0", "QUEUE_NOW": "1000", "QUEUE_LIMIT": "5"}
    jobs = [
        {"id": "low", "payload": {"text": "世界 😀"}},
        {"id": "high", "payload": [1, False, None], "priority": 9},
        {"id": "delayed", "payload": None, "priority": 9, "delay": 10},
        {"id": "other", "payload": "separate", "queue": "other"},
    ]
    with app.server(directory, settings) as server:
        for job in jobs:
            assert post(server, "/jobs", job).status == 201
        snapshot = state.read_bytes()
        duplicate = post(server, "/jobs", jobs[0])
        assert duplicate.status == 200 and duplicate.json()["duplicate"] is True
        assert post(server, "/jobs", {**jobs[0], "payload": "changed"}).status == 409
        for field, value in [
            ("id", "bad/id"),
            ("priority", True),
            ("priority", 10),
            ("delay", -1),
            ("delay", 86401),
            ("queue", ""),
            ("payload", "x" * 16385),
        ]:
            assert post(server, "/jobs", {**jobs[0], field: value}).status == 400
        assert post(server, "/claim", {"worker": "worker", "seconds": True}).status == 400
        assert state.read_bytes() == snapshot
        high = post(server, "/claim", {"worker": "worker-a", "seconds": 5}).json()
        assert high["job"]["id"] == "high" and high["job"]["attempts"] == 1 and high["job"]["lease_until"] == 1005
        assert re.fullmatch("[0-9a-f]{64}", high["token"])
        assert "token" not in server.request("GET", "/jobs/high").json()
        low = post(server, "/claim", {"worker": "worker-b", "seconds": 20}).json()
        assert low["job"]["id"] == "low"
        assert post(server, "/claim", {"worker": "worker-c"}).json() == {"job": None}
        assert server.request("GET", "/jobs?queue=other").json()["count"] == 1
        assert server.request("DELETE", "/jobs/high").status == 409
        assert post(server, "/ack", {**receipt(high), "worker": "foreign"}).status == 409
        assert post(server, "/ack", {**receipt(high), "token": "f" * 64}).status == 409
        released = post(server, "/release", {**receipt(low), "delay": 3})
        assert released.status == 200 and released.json()["job"]["available_at"] == 1003
        assert post(server, "/ack", receipt(low)).status == 409
        assert post(server, "/claim", {"worker": "worker-c"}).json() == {"job": None}
    # Before the old lease deadline, restart must neither lose nor reclaim it.
    with app.server(directory, dict(settings, QUEUE_NOW="1004.999")) as server:
        assert server.request("GET", "/jobs/high").json()["state"] == "leased"
        assert server.request("GET", "/jobs/high").json()["lease_until"] == 1005
    # A worker crashes with a lease. At the exact deadline a new worker claims
    # the same job; an acknowledgement from the old generation must not win.
    with app.server(directory, dict(settings, QUEUE_NOW="1005")) as server:
        assert post(server, "/sweep", {}).json() == {"requeued": ["high"]}
        replacement = post(server, "/claim", {"worker": "worker-new", "seconds": 5}).json()
        assert replacement["job"]["id"] == "high" and replacement["job"]["attempts"] == 2
        assert replacement["token"] != high["token"] and replacement["job"]["lease_until"] == 1010
        before = state.read_bytes()
        assert post(server, "/ack", receipt(high)).status == 409
        assert state.read_bytes() == before
        assert post(server, "/ack", receipt(replacement)).json()["job"]["state"] == "done"
        done_bytes = state.read_bytes()
        duplicate_ack = post(server, "/ack", receipt(replacement))
        assert duplicate_ack.status == 200 and duplicate_ack.json()["duplicate"] is True
        assert state.read_bytes() == done_bytes
        assert post(server, "/jobs", jobs[1]).json()["job"]["state"] == "done"
        body = json.dumps({"worker": "same-worker", "seconds": 5}).encode()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: server.request("POST", "/claim", body).json(), range(2)))
        claimed = [value for value in outcomes if value["job"] is not None]
        assert len(claimed) == 1 and claimed[0]["job"]["id"] == "low"
        current_low = claimed[0]
        assert current_low["job"]["attempts"] == 2 and current_low["token"] != low["token"]
        other = post(server, "/claim", {"queue": "other", "worker": "other-worker"}).json()
        assert other["job"]["id"] == "other"
        assert post(server, "/ack", receipt(other)).status == 200
    with app.server(directory, dict(settings, QUEUE_NOW="1010")) as server:
        assert post(server, "/ack", receipt(current_low)).status == 409
        delayed = post(server, "/claim", {"worker": "later", "seconds": 10}).json()
        assert delayed["job"]["id"] == "delayed" and delayed["job"]["attempts"] == 1
        assert post(server, "/ack", receipt(delayed)).status == 200
        final_low = post(server, "/claim", {"worker": "later", "seconds": 10}).json()
        assert final_low["job"]["id"] == "low" and final_low["job"]["attempts"] == 3
        assert post(server, "/ack", receipt(final_low)).status == 200
        results = server.request("GET", "/jobs?state=done").json()
        assert results["count"] == 4
        assert all("token" not in value for value in results["jobs"])
        assert server.request("DELETE", "/jobs/high").status == 200
        assert server.request("DELETE", "/jobs/high").status == 404
        assert post(server, "/jobs", {"id": "high", "payload": "recycled"}).status == 201
        recycled = post(server, "/claim", {"worker": "worker-new", "seconds": 10}).json()
        assert recycled["job"]["attempts"] == 1 and recycled["token"] != replacement["token"]
        assert post(server, "/ack", receipt(replacement)).status == 409
    # The persisted watermark prevents a backward wall clock from lengthening
    # this outstanding lease or admitting its delayed work early.
    with app.server(directory, dict(settings, QUEUE_NOW="900")) as server:
        assert server.request("GET", "/jobs/high").json()["lease_until"] == 1020
        assert post(server, "/ack", receipt(recycled)).json()["job"]["completed_at"] == 1010
        assert post(server, "/jobs", {"id": "last", "payload": {}}).status == 201
        before = state.read_bytes()
        assert post(server, "/jobs", {"id": "overflow", "payload": {}}).status == 507
        assert state.read_bytes() == before
    snapshot = state.read_bytes()
    original = json.loads(snapshot)
    for field, value in [("attempts", -1), ("token", "short"), ("completed_at", 999999), ("state", "invented")]:
        corrupted = copy.deepcopy(original)
        corrupted["jobs"][0][field] = value
        state.write_text(json.dumps(corrupted))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    state.write_bytes(snapshot)
    return {
        "completed": results,
        "fenced_after_expiry": True,
        "fenced_after_id_reuse": True,
        "competing_claims": len(claimed),
        "ack_retry_idempotent": True,
        "clock_watermark": 1010,
    }
