"""Per-service attempts, monotonic retry scheduling and bounded stream retention."""

# ruff: noqa: I001, BLE001 - compact imports and per-spawn failure reporting
from configuration import environment
from files import append
from py2rust.stdlib import (
    Json, ProcessPool, floor, json_array, json_bool, json_int, json_is_null, json_string, monotonic, path_join,
    process_poll, process_spawn,
)


def clock(started: float) -> int:
    return floor((monotonic() - started) * 1000.0)


def initial(name: str) -> Json:
    return {
        "id": name,
        "state": "waiting",
        "handle": 0,
        "pid": 0,
        "attempts": 0,
        "next_ms": 0,
        "returncode": None,
        "error": "",
        "history": [],
        "stdout": {"kept": 0, "seen": 0, "file": name + ".stdout"},
        "stderr": {"kept": 0, "seen": 0, "file": name + ".stderr"},
    }


def finished(row: Json, spec: Json, now: int, stopping: bool, kind: str, code: Json) -> Json:
    history: list[Json] = json_array(row["history"])
    last: Json = history[-1]
    last["ended_ms"] = now
    last["kind"] = kind
    last["returncode"] = code
    row["handle"] = 0
    row["pid"] = 0
    row["returncode"] = code
    row["state"] = "stopped" if stopping else "exited"
    if not stopping and (json_is_null(code) or json_int(code) != 0):
        row["state"] = "failed"
        if json_int(row["attempts"]) <= json_int(spec["restarts"]):
            delay: int = json_int(spec["backoff_ms"])
            for attempt in range(json_int(row["attempts"]) - 1):
                delay = min(delay * 2, json_int(spec["max_backoff_ms"]))
            last["delay_ms"] = delay
            row["next_ms"] = now + delay
            row["state"] = "backoff"
    history[-1] = last
    row["history"] = history
    return row


def start(pool: ProcessPool, row: Json, spec: Json, started: float) -> Json:
    now: int = clock(started)
    row["attempts"] = json_int(row["attempts"]) + 1
    history: list[Json] = json_array(row["history"])
    history.append(
        {
            "attempt": row["attempts"],
            "started_ms": now,
            "ended_ms": None,
            "kind": "running",
            "returncode": None,
            "delay_ms": 0,
        }
    )
    row["history"] = history
    row["state"] = "running"
    row["returncode"] = None
    row["error"] = ""
    arguments: list[str] = []
    for argument in json_array(spec["argv"]):
        arguments.append(json_string(argument))
    try:
        row["handle"] = process_spawn(pool, arguments, environment(spec["environment"]), json_string(spec["cwd"]))
    except Exception as error:
        row["error"] = str(error)
        row = finished(row, spec, clock(started), False, "spawn_error", None)
    return row


def capture(row: Json, spec: Json, root: str, stream: str, data: bytes) -> Json:
    details: Json = row[stream]
    take: int = min(len(data), json_int(spec["log_bytes"]) - json_int(details["kept"]))
    if take > 0:
        append(path_join(root, json_string(details["file"])), data[:take])
    details["kept"] = json_int(details["kept"]) + take
    details["seen"] = json_int(details["seen"]) + len(data)
    row[stream] = details
    return row


def poll(pool: ProcessPool, row: Json, spec: Json, root: str, started: float, stopping: bool) -> Json:
    result: tuple[Json, bytes, bytes] = process_poll(pool, json_int(row["handle"]), 8192)
    row["pid"] = result[0]["pid"]
    row = capture(row, spec, root, "stdout", result[1])
    row = capture(row, spec, root, "stderr", result[2])
    if json_bool(result[0]["complete"]):
        row = finished(row, spec, clock(started), stopping, "exited", result[0]["returncode"])
    return row
