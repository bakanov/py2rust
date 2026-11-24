"""Decode PYTRAF version 1 without trusting lengths or retaining duplicate payloads."""

from py2rust.stdlib import (
    Json,
    int_from_bytes,
    json_int,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def problem(code: str, phase: str, record: int, offset: int, offset_kind: str) -> Json:
    return {"code": code, "phase": phase, "record": record, "offset": offset, "offset_kind": offset_kind}


def parse(data: bytes, limits: Json) -> tuple[list[Json], Json]:
    rows: list[Json] = []
    if len(data) < 12:
        return (rows, problem("truncated_header", "parse", -1, len(data), "file"))
    if data[:8] != b"PYTRAF\x01\x00":
        return (rows, problem("bad_magic", "parse", -1, 0, "file"))
    count: int = int_from_bytes(data[8:12], "big")
    if count < 1 or count > json_int(limits["records"]):
        return (rows, problem("record_limit", "parse", -1, 8, "file"))
    position: int = 12
    previous: int = 0
    for index in range(count):
        if len(data) - position < 9:
            return (rows, problem("truncated_record_header", "parse", index, len(data), "file"))
        scheduled: int = int_from_bytes(data[position : position + 4], "big")
        direction: int = data[position + 4]
        length: int = int_from_bytes(data[position + 5 : position + 9], "big")
        if scheduled < previous or scheduled > json_int(limits["scheduled_ms"]):
            return (rows, problem("invalid_schedule", "parse", index, position, "file"))
        if direction != 0 and direction != 1:
            return (rows, problem("invalid_direction", "parse", index, position + 4, "file"))
        if length > json_int(limits["payload_bytes"]):
            return (rows, problem("payload_limit", "parse", index, position + 5, "file"))
        start: int = position + 9
        if length > len(data) - start:
            return (rows, problem("truncated_payload", "parse", index, len(data), "file"))
        payload: bytes = data[start : start + length]
        rows.append(
            {
                "index": index,
                "header_offset": position,
                "payload_offset": start,
                "scheduled_ms": scheduled,
                "direction": "send" if direction == 0 else "receive",
                "length": length,
                "sha256": digest(payload),
                "preview_hex": payload[:32].hex(),
            }
        )
        position = start + length
        previous = scheduled
    if position != len(data):
        return (rows, problem("trailing_fixture_bytes", "parse", count, position, "file"))
    return (rows, None)
