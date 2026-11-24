"""Interpret response quotas separately from each request's success or retry state."""

from model import clock, delay, result_nodes

from py2rust.stdlib import (
    HttpReader,
    Json,
    env_get,
    http_retry_after,
    json_bool,
    json_float,
    json_int,
    json_loads,
    json_string,
    regex_fullmatch,
    web_open,
    web_open_ca,
    web_read,
)


def decimal(value: str) -> float:
    assert regex_fullmatch("[0-9]{1,15}", value), "invalid quota number"
    # JSON forbids leading zeroes; headers allow them.
    number: float = 0.0
    for index in range(len(value)):
        number = number * 10.0 + json_float(json_loads(value[index]))
    assert number <= 253402300799.0, "quota number exceeds supported range"
    return number


def quota_deadline(headers: dict[str, str], now: float, fallback: float) -> Json:
    deadline: float = now
    invalid: bool = False
    try:
        if "retry-after" in headers:
            deadline = max(deadline, http_retry_after(headers["retry-after"], now))
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        invalid = True
    try:
        remaining: bool = "x-ratelimit-remaining" in headers
        reset: bool = "x-ratelimit-reset" in headers
        assert remaining == reset, "quota remaining/reset headers must occur together"
        if remaining:
            tokens: float = decimal(headers["x-ratelimit-remaining"])
            resets_at: float = decimal(headers["x-ratelimit-reset"])
            if tokens == 0.0:
                deadline = max(deadline, max(resets_at, now + fallback))
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        invalid = True
    return {"deadline": deadline, "invalid": invalid}


def open_request(entry: Json, policy: Json) -> HttpReader:
    url: str = json_string(entry["job"]["url"])
    headers: dict[str, str] = {"Accept": "application/json", "Accept-Encoding": "identity"}
    ca: str = env_get("BATCH_CA", "")
    if ca != "":
        return web_open_ca(url, headers, json_int(policy["timeout_ms"]), json_int(policy["max_body"]), ca)
    return web_open(url, headers, json_int(policy["timeout_ms"]), json_int(policy["max_body"]))


def finish(entry: Json, policy: Json, quota: Json) -> Json:
    status: int = 0
    headers: dict[str, str] = {}
    body: bytes = b""
    error: str = "transport"
    try:
        with open_request(entry, policy) as response:
            status = response.status
            headers = response.headers
            if status >= 200 and status < 300:
                chunks: list[bytes] = []
                while True:
                    chunk: bytes = web_read(response, 65536)
                    if len(chunk) == 0:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks)
            error = "http"
    except Exception:  # noqa: S110, BLE001 - transport failures become persisted retry receipts
        pass
    now: float = clock()
    assert now >= json_float(entry["last_at"]), "clock moved backwards during request"
    fallback: float = delay(policy, json_int(entry["attempts"]))
    parsed: Json = quota_deadline(headers, now, fallback)
    gate: float = json_float(parsed["deadline"])
    if json_bool(parsed["invalid"]):
        quota["blocked"] = "invalid quota headers"
    if status == 429:
        gate = max(gate, now + fallback)
    quota["not_before"] = max(json_float(quota["not_before"]), gate)
    result: Json = None
    successful: bool = status >= 200 and status < 300 and error != "transport"
    if successful:
        try:
            assert headers.get("content-encoding", "identity") == "identity", "encoded response is unsupported"
            if status != 204:
                result = json_loads(body.decode())
                result_nodes(result, 0)
            error = ""
        except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
            successful = False
            error = "invalid JSON result"
            result = None
    state: str = "complete"
    next_at: float = 0.0
    if not successful:
        state = "failed"
        transient: bool = error == "transport" or status == 408 or status == 429 or status >= 500
        if transient and json_int(entry["attempts"]) < json_int(policy["attempts"]):
            state = "pending"
            next_at = max(now + fallback, gate)
    return {
        "entry": {
            "job": entry["job"],
            "state": state,
            "attempts": entry["attempts"],
            "next_at": next_at,
            "last_at": now,
            "status": status,
            "error": error,
            "result": result,
        },
        "quota": quota,
    }
