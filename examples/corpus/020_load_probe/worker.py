"""One independently scheduled HTTP request; cancellation records every unsent job."""

import math

from py2rust.stdlib import (
    Json,
    WebResponse,
    json_float,
    json_int,
    json_keys,
    json_string,
    monotonic,
    path_exists,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    web_request,
    web_request_ca,
)


def elapsed(origin: float) -> int:
    return max(0, math.ceil((monotonic() - origin) * 1000000.0))


def cancellation(task: Json, now: int) -> str:
    marker: str = json_string(task["cancel_file"])
    if marker != "" and path_exists(marker):
        return "requested"
    if now >= json_int(task["duration_ms"]) * 1000:
        return "deadline"
    return ""


def send(task: Json, timeout: int) -> WebResponse:
    target: Json = task["target"]
    headers: dict[str, str] = {}
    for name in json_keys(target["headers"]):
        headers[name] = json_string(target["headers"][name])
    url: str = json_string(target["url"])
    method: str = json_string(target["method"])
    body: bytes = bytes.fromhex(json_string(target["body_hex"]))
    ca: str = json_string(task["ca_file"])
    if ca != "" and url.startswith("https://"):
        return web_request_ca(method, url, body, headers, timeout, json_int(task["max_body"]), ca)
    return web_request(method, url, body, headers, timeout, json_int(task["max_body"]))


def perform(task: Json) -> Json:
    job: Json = task["job"]
    origin: float = json_float(task["origin"])
    planned: int = json_int(job["at_ms"]) * 1000
    sample: Json = {
        "id": job["id"],
        "target": job["target"],
        "scheduled_ms": job["at_ms"],
        "state": "cancelled",
        "reason": "",
        "status": 0,
        "started_us": None,
        "finished_us": 0,
        "latency_us": None,
        "lateness_us": 0,
        "bytes": 0,
        "sha256": "",
    }
    now: int = elapsed(origin)
    while True:
        reason: str = cancellation(task, now)
        if reason != "":
            sample["reason"] = reason
            sample["finished_us"] = now
            sample["lateness_us"] = max(0, now - planned)
            return sample
        if now >= planned:
            break
        sleep(min(0.01, json_float(planned - now) * 0.000001))
        now = elapsed(origin)
    sample["lateness_us"] = now - planned
    if now - planned > json_int(task["max_lag_ms"]) * 1000:
        sample["state"] = "late"
        sample["reason"] = "schedule_lag"
        sample["finished_us"] = now
        return sample
    remaining: int = json_int(task["duration_ms"]) * 1000 - now
    timeout: int = min(json_int(task["timeout_ms"]), max(1, (remaining + 999) // 1000))
    sample["started_us"] = now
    finished: int = now
    try:
        response: WebResponse = send(task, timeout)
        finished = elapsed(origin)
        sample["status"] = response.status
        sample["bytes"] = len(response.body)
        sample["sha256"] = sha256_digest(sha256_update(sha256_new(), response.body))
        sample["state"] = "ok"
        if response.status < 200 or response.status >= 300:
            sample["state"] = "http_error"
    except Exception:  # noqa: BLE001 - compiled subset uses a recoverable Exception boundary
        finished = elapsed(origin)
        sample["state"] = "transport_error"
        sample["reason"] = "request_failed"
    sample["finished_us"] = finished
    sample["latency_us"] = finished - now
    return sample
