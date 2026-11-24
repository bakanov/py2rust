"""Run one due-delivery pass, retaining retries and dead letters across restarts."""

import logging
import sys

from model import clock, headers_for, setting, validate_configuration
from storage import import_jobs, load, save

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    json_dumps,
    json_float,
    json_int,
    json_parse,
    json_string,
    log,
    log_configure,
    path_exists,
    path_resolve,
    pretty,
    regex_fullmatch,
    web_request,
    web_request_ca,
    write_text_atomic,
)


def validate_paths() -> None:
    output: str = env_get("OUTBOX_REPORT", "outbox-report.json")
    protected: list[str] = [env_get("OUTBOX_STATE", "outbox-state.json"), env_get("OUTBOX_IMPORT", "")]
    for path in protected:
        if path != "":
            assert output != path, "report must not overwrite queue or import"
            if path_exists(output) and path_exists(path):
                assert path_resolve(output) != path_resolve(path), "report aliases queue or import"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def retry_delay(attempts: int, retry_after: str) -> int:
    delay: int = setting("OUTBOX_DELAY", 2)
    for index in range(1, attempts):
        delay = min(delay * 2, 3600)
    if regex_fullmatch("0|[1-9][0-9]{0,8}", retry_after):
        delay = max(delay, min(json_int(json_parse(retry_after, None)), 3600))
    return delay


def send(job: Json) -> WebResponse:
    url: str = json_string(job["url"])
    body: bytes = json_dumps(job["payload"]).encode()
    ca_file: str = env_get("OUTBOX_CA", "")
    if ca_file != "":
        return web_request_ca("POST", url, body, headers_for(job), setting("OUTBOX_TIMEOUT", 2000), 65536, ca_file)
    return web_request("POST", url, body, headers_for(job), setting("OUTBOX_TIMEOUT", 2000), 65536)


def attempt(entry: Json, now: float) -> Json:
    job: Json = entry["job"]
    count: int = json_int(entry["attempts"]) + 1
    code: int = 0
    error: str = ""
    retry_after: str = ""
    try:
        response: WebResponse = send(job)
        code = response.status
        retry_after = response.headers.get("retry-after", "")
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        error = "transport error"
    if env_get("OUTBOX_STOP", "") == "after_send":
        sys.exit(75)
    state: str = "pending"
    next_attempt: float = 0.0
    if code >= 200 and code < 300:
        state = "delivered"
    else:
        if code != 0:
            error = "HTTP " + str(code)
        transient: bool = code == 0 or code == 408 or code == 429 or code >= 500
        if not transient or count >= setting("OUTBOX_ATTEMPTS", 4):
            state = "dead"
        else:
            delay: float = retry_delay(count, retry_after)
            next_attempt = now + delay
    return {
        "job": job,
        "state": state,
        "attempts": count,
        "next_attempt": next_attempt,
        "last_status": code,
        "last_error": error,
        "last_attempt": now,
    }


def deliver(entries: list[Json]) -> list[Json]:
    now: float = clock()
    updated: list[Json] = entries.copy()
    for index in range(len(updated)):
        entry: Json = updated[index]
        if json_string(entry["state"]) == "pending" and json_float(entry["next_attempt"]) <= now:
            if json_int(entry["attempts"]) >= setting("OUTBOX_ATTEMPTS", 4):
                entry["state"] = "dead"
                entry["last_error"] = "attempt limit reduced"
                updated[index] = entry
            else:
                updated[index] = attempt(entry, now)
            save(updated)
            log(logging.INFO, json_string(entry["job"]["id"]) + ": " + json_string(updated[index]["state"]))
    return updated


def report(entries: list[Json]) -> Json:
    pending: list[Json] = []
    delivered: list[Json] = []
    dead: list[Json] = []
    for entry in entries:
        receipt: Json = {
            "id": entry["job"]["id"],
            "attempts": entry["attempts"],
            "status": entry["last_status"],
            "error": entry["last_error"],
            "last_attempt": entry["last_attempt"],
            "next_attempt": entry["next_attempt"],
        }
        status: str = json_string(entry["state"])
        if status == "pending":
            pending.append(receipt)
        elif status == "delivered":
            delivered.append(receipt)
        else:
            dead.append(receipt)
    return {
        "pending": pending,
        "delivered": delivered,
        "dead": dead,
        "counts": {"pending": len(pending), "delivered": len(delivered), "dead": len(dead)},
    }


def main() -> None:
    validate_configuration()
    validate_paths()
    log_configure(logging.INFO)
    entries: list[Json] = load()
    if env_get("OUTBOX_MODE", "run") == "run":
        entries = import_jobs(entries)
        entries = deliver(entries)
    result: Json = report(entries)
    validate_paths()
    write_text_atomic(env_get("OUTBOX_REPORT", "outbox-report.json"), pretty(result))
    print(json_dumps(result["counts"]))
    if json_int(result["counts"]["dead"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
