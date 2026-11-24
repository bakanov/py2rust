"""Bounded line parsing and partial UTF-8 writes without blocking a peer."""

from commands import command
from model import drop, enqueue, store

from py2rust.stdlib import (
    Json,
    TcpStream,
    json_array,
    json_float,
    json_int,
    json_string,
    monotonic,
    regex_fullmatch,
    tcp_send_ready,
)


def reject(state: Json, key: str, code: str, policy: Json) -> Json:
    state = enqueue(state, key, "ERR " + code, policy)
    return drop(state, key, "protocol", True, policy)


def parse(state: Json, key: str, buffer: bytes, policy: Json) -> tuple[Json, bytes]:
    for index in range(json_int(policy["commands_per_tick"])):
        if json_string(state["peers"][key]["closing"]) != "":
            return (state, b"")
        boundary: int = buffer.find(b"\n")
        if boundary < 0:
            if len(buffer) > json_int(policy["line_bytes"]):
                return (reject(state, key, "LINE_TOO_LONG", policy), b"")
            break
        if boundary > json_int(policy["line_bytes"]):
            return (reject(state, key, "LINE_TOO_LONG", policy), b"")
        raw: bytes = buffer[:boundary]
        buffer = buffer[boundary + 1 :]
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        line: str = ""
        try:
            line = raw.decode()
        except Exception:  # noqa: BLE001 - recoverable subset boundary isolates peer failures
            return (reject(state, key, "UTF8", policy), b"")
        if not regex_fullmatch("[^\x00-\x1f\x7f]*", line):
            return (reject(state, key, "CONTROL", policy), b"")
        state = command(state, key, line, policy)
        peer: Json = state["peers"][key]
        peer["partial"] = monotonic()
        state = store(state, key, peer)
    return (state, buffer)


def flush(state: Json, key: str, stream: TcpStream, policy: Json) -> Json:
    peer: Json = state["peers"][key]
    queue: list[Json] = json_array(peer["queue"])
    budget: int = json_int(policy["write_bytes"])
    offset: int = json_int(peer["offset"])
    while len(queue) > 0 and budget > 0:
        encoded: bytes = json_string(queue[0]).encode()
        sent: int = tcp_send_ready(stream, encoded[offset : offset + budget])
        if sent == 0:
            break
        offset = offset + sent
        budget = budget - sent
        peer["queued"] = json_int(peer["queued"]) - sent
        peer["active"] = monotonic()
        if offset == len(encoded):
            queue.pop(0)
            offset = 0
    peer["offset"] = offset
    peer["queue"] = queue
    return store(state, key, peer)


def expire(state: Json, key: str, buffer: bytes, policy: Json) -> Json:
    peer: Json = state["peers"][key]
    if json_string(peer["closing"]) != "":
        return state
    now: float = monotonic()
    if (
        len(buffer) > 0
        and buffer.find(b"\n") < 0
        and now - json_float(peer["partial"]) >= json_float(policy["partial_ms"]) * 0.001
    ):
        state = enqueue(state, key, "ERR LINE_TIMEOUT", policy)
        return drop(state, key, "timeout", True, policy)
    if now - json_float(peer["active"]) >= json_float(policy["idle_ms"]) * 0.001:
        state = enqueue(state, key, "ERR IDLE", policy)
        return drop(state, key, "timeout", True, policy)
    return state
