"""Session transitions close ordered active intervals and leave paused time out of totals."""

# ruff: noqa: PLR1711 - explicit subset returns
from config import setting

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
    regex_search,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def identifier(value: Json) -> str:
    text: str = json_string(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", text), "invalid session ID"
    return text


def title(value: Json) -> str:
    text: str = json_string(value)
    assert 1 <= len(text.encode()) <= 128, "invalid session name length"
    assert not regex_search("[\\x00-\\x1f\\x7f]", text), "name contains controls"
    return text


def view(key: str, row: Json, clock: int) -> Json:
    total: int = json_int(row["total_ms"])
    active: int = clock - json_int(row["open_ms"]) if json_string(row["status"]) == "running" else 0
    return {
        "id": key,
        "name": row["name"],
        "status": row["status"],
        "created_ms": row["created_ms"],
        "updated_ms": row["updated_ms"],
        "open_ms": row["open_ms"],
        "stopped_ms": row["stopped_ms"],
        "intervals": row["intervals"],
        "completed_ms": total,
        "active_ms": active,
        "elapsed_ms": total + active,
        "completed_seconds": total / 1000,
        "elapsed_seconds": (total + active) / 1000,
    }


def report(state: Json) -> Json:
    rows: list[Json] = []
    groups: Json = {}
    clock: int = json_int(state["clock_ms"])
    completed: int = 0
    elapsed: int = 0
    for key in sorted(json_keys(state["sessions"])):
        row: Json = view(key, state["sessions"][key], clock)
        rows.append(row)
        completed = completed + json_int(row["completed_ms"])
        elapsed = elapsed + json_int(row["elapsed_ms"])
        name: str = json_string(row["name"])
        if name not in json_keys(groups):
            groups[name] = {"sessions": 0, "completed_ms": 0, "elapsed_ms": 0}
        group: Json = groups[name]
        group["sessions"] = json_int(group["sessions"]) + 1
        group["completed_ms"] = json_int(group["completed_ms"]) + json_int(row["completed_ms"])
        group["elapsed_ms"] = json_int(group["elapsed_ms"]) + json_int(row["elapsed_ms"])
        groups[name] = group
    totals: list[Json] = []
    for name in sorted(json_keys(groups)):
        group: Json = groups[name]
        totals.append(
            {
                "name": name,
                "sessions": group["sessions"],
                "completed_ms": group["completed_ms"],
                "elapsed_ms": group["elapsed_ms"],
                "completed_seconds": json_int(group["completed_ms"]) / 1000,
                "elapsed_seconds": json_int(group["elapsed_ms"]) / 1000,
            }
        )
    return {
        "clock_ms": clock,
        "sessions": rows,
        "by_name": totals,
        "completed_ms": completed,
        "elapsed_ms": elapsed,
        "completed_seconds": completed / 1000,
        "elapsed_seconds": elapsed / 1000,
    }


def execute(state: Json, operation: str, key: str, name: str) -> tuple[Json, int, Json]:
    sessions: Json = state["sessions"]
    clock: int = json_int(state["clock_ms"])
    exists: bool = key in json_keys(sessions)
    if operation == "report":
        return (state, 200, report(state))
    if operation == "start":
        if exists:
            return (state, 409, {"error": "session ID already exists"})
        if len(json_keys(sessions)) >= setting("TIMER_SESSIONS", 128):
            return (state, 507, {"error": "session capacity reached"})
        sessions[key] = {
            "name": name,
            "status": "running",
            "created_ms": clock,
            "updated_ms": clock,
            "open_ms": clock,
            "stopped_ms": None,
            "intervals": [],
            "total_ms": 0,
        }
        state["sessions"] = sessions
        return (state, 201, {"clock_ms": clock, "session": view(key, sessions[key], clock)})
    if not exists:
        return (state, 404, {"error": "session does not exist"})
    row: Json = sessions[key]
    status: str = json_string(row["status"])
    if operation != "get":
        if (
            status == "stopped"
            or operation == "pause"
            and status != "running"
            or operation == "resume"
            and status != "paused"
        ):
            return (state, 409, {"error": "illegal session transition"})
        intervals: list[Json] = json_array(row["intervals"])
        if operation == "resume":
            if len(intervals) >= setting("TIMER_INTERVALS", 256):
                return (state, 507, {"error": "interval capacity reached"})
            row["open_ms"] = clock
            row["status"] = "running"
        else:
            if status == "running":
                began: int = json_int(row["open_ms"])
                intervals.append({"start_ms": began, "end_ms": clock})
                row["intervals"] = intervals
                row["total_ms"] = json_int(row["total_ms"]) + clock - began
            row["open_ms"] = None
            row["status"] = "paused" if operation == "pause" else "stopped"
            if operation == "stop":
                row["stopped_ms"] = clock
        row["updated_ms"] = clock
        sessions[key] = row
        state["sessions"] = sessions
    return (state, 200, {"clock_ms": clock, "session": view(key, row, clock)})
