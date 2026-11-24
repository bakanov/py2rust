"""Replay immutable fixture bytes with one absolute deadline per logical record."""

# ruff: noqa: BLE001 - convert recoverable socket errors into record diagnostics
from records import problem

from py2rust.stdlib import (
    Json,
    TcpStream,
    floor,
    json_int,
    json_is_null,
    json_string,
    monotonic,
    sleep,
    tcp_connect,
    tcp_recv,
    tcp_sendall,
    tcp_set_deadline,
    tcp_shutdown_write,
)


def milliseconds(seconds: float) -> int:
    return max(0, floor(seconds * 1000.0))


def exchange(stream: TcpStream, data: bytes, row: Json, deadline: float) -> Json:
    index: int = json_int(row["index"])
    offset: int = 0
    start: int = json_int(row["payload_offset"])
    length: int = json_int(row["length"])
    direction: str = json_string(row["direction"])
    try:
        remaining: int = milliseconds(deadline - monotonic())
        if remaining < 1:
            return problem("deadline", direction, index, offset, "payload")
        tcp_set_deadline(stream, remaining)
        while offset < length:
            if monotonic() >= deadline:
                return problem("deadline", direction, index, offset, "payload")
            size: int = min(65536, length - offset)
            expected: bytes = data[start + offset : start + offset + size]
            if direction == "send":
                tcp_sendall(stream, expected)
                offset = offset + size
            else:
                actual: bytes = tcp_recv(stream, size)
                if len(actual) == 0:
                    return problem("early_eof", direction, index, offset, "payload")
                for position in range(len(actual)):
                    if actual[position] != expected[position]:
                        error: Json = problem("mismatch", direction, index, offset + position, "payload")
                        error["expected"] = expected[position]
                        error["actual"] = actual[position]
                        return error
                offset = offset + len(actual)
    except Exception:
        # A failed send may have reached the peer in part. Offset is the last
        # fully completed chunk; it is never claimed to be an exact wire count.
        return problem("io_error", direction, index, offset, "completed_prefix")
    return None


def finish(stream: TcpStream, count: int, deadline: float) -> Json:
    try:
        remaining: int = milliseconds(deadline - monotonic())
        if remaining < 1:
            return problem("deadline", "eof", count, 0, "trailing_reply")
        tcp_set_deadline(stream, remaining)
        tcp_shutdown_write(stream)
        extra: bytes = tcp_recv(stream, 1)
        if len(extra) > 0:
            error: Json = problem("extra_reply", "eof", count, 0, "trailing_reply")
            error["actual"] = extra[0]
            return error
    except Exception:
        return problem("io_error", "eof", count, 0, "trailing_reply")
    return None


def connected(stream: TcpStream, data: bytes, rows: list[Json], timeouts: Json, deadline: float) -> Json:
    origin: float = monotonic()
    events: list[Json] = []
    for row in rows:
        index: int = json_int(row["index"])
        due: float = origin + float(json_int(row["scheduled_ms"])) / 1000.0
        if due >= deadline:
            return {"events": events, "error": problem("deadline", "schedule", index, 0, "payload")}
        while monotonic() < due:
            sleep(min(0.02, max(0.0, due - monotonic())))
        started: float = monotonic()
        record_deadline: float = min(deadline, started + float(json_int(timeouts["record_ms"])) / 1000.0)
        error: Json = exchange(stream, data, row, record_deadline)
        events.append(
            {
                "record": index,
                "started_ms": milliseconds(started - origin),
                "lag_ms": milliseconds(started - due),
                "duration_ms": milliseconds(monotonic() - started),
                "status": "passed" if json_is_null(error) else "failed",
            }
        )
        if not json_is_null(error):
            return {"events": events, "error": error}
    ending: float = min(deadline, monotonic() + float(json_int(timeouts["record_ms"])) / 1000.0)
    return {"events": events, "error": finish(stream, len(rows), ending)}


def run(data: bytes, rows: list[Json], job: Json) -> Json:
    timeouts: Json = job["timeouts"]
    started: float = monotonic()
    deadline: float = started + float(json_int(timeouts["total_ms"])) / 1000.0
    peer: Json = job["peer"]
    timeout: int = min(json_int(timeouts["connect_ms"]), json_int(timeouts["total_ms"]))
    try:
        with tcp_connect(json_string(peer["host"]), json_int(peer["port"]), timeout) as stream:
            result: Json = connected(stream, data, rows, timeouts, deadline)
            result["elapsed_ms"] = milliseconds(monotonic() - started)
            return result
    except Exception:
        return {"events": [], "error": problem("io_error", "connect", -1, 0, "none")}
