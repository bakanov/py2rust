"""Incremental, bounded RESP2 decoding; binary payloads never pass through UTF-8."""

from py2rust.stdlib import (
    Json,
    int_from_decimal,
    json_array,
    json_is_null,
    json_string,
    regex_fullmatch,
)


def error(message: str) -> bytes:
    return ("-ERR " + message + "\r\n").encode()


def bulk(value: bytes) -> bytes:
    return ("$" + str(len(value)) + "\r\n").encode() + value + b"\r\n"


def integer(value: int) -> bytes:
    return (":" + str(value) + "\r\n").encode()


def parse(source: bytes, start: int, depth: int, budget: int) -> tuple[Json, int, int]:
    assert depth <= 8 and budget >= 1, "RESP nesting/node limit"
    if start >= len(source):
        return (None, start, 0)
    suffix: bytes = source[start:]
    end: int = suffix.find(b"\r\n")
    if end < 0:
        assert len(suffix) <= 64 and suffix.find(b"\n") < 0, "RESP header exceeds limit or has bare LF"
        return (None, start, 0)
    assert end <= 64 and end >= 1 and suffix[:end].find(b"\r") < 0, "invalid RESP header"
    tag: int = suffix[0]
    text: bytes = suffix[1:end]
    cursor: int = start + end + 2
    if tag == 43 or tag == 45:
        return ({"kind": "simple", "value": text.hex()}, cursor, 1)
    assert tag in [36, 42, 58], "unsupported RESP type"
    decimal: str = text.decode()
    assert regex_fullmatch("[+-]?[0-9]{1,19}", decimal), "invalid RESP integer"
    count: int = int_from_decimal(decimal)
    if tag == 58:
        return ({"kind": "integer", "value": count}, cursor, 1)
    kind: str = "bulk"
    if tag == 42:
        kind = "array"
    if count == -1:
        return ({"kind": kind, "value": None}, cursor, 1)
    assert count >= 0, "invalid negative length"
    if tag == 36:
        assert count <= 65536, "bulk string exceeds limit"
        if len(source) < cursor + count + 2:
            return (None, start, 0)
        assert source[cursor + count : cursor + count + 2] == b"\r\n", "bulk terminator missing"
        return ({"kind": "bulk", "value": source[cursor : cursor + count].hex()}, cursor + count + 2, 1)
    assert count <= 64, "array exceeds limit"
    children: list[Json] = []
    used: int = 1
    for index in range(count):
        child: tuple[Json, int, int] = parse(source, cursor, depth + 1, budget - used)
        if json_is_null(child[0]):
            return (None, start, 0)
        children.append(child[0])
        cursor = child[1]
        used = used + child[2]
    return ({"kind": "array", "value": children}, cursor, used)


def arguments(frame: Json) -> list[bytes]:
    assert json_string(frame["kind"]) == "array" and not json_is_null(frame["value"]), "expected command array"
    result: list[bytes] = []
    for part in json_array(frame["value"]):
        assert json_string(part["kind"]) == "bulk" and not json_is_null(part["value"]), "expected bulk argument"
        result.append(bytes.fromhex(json_string(part["value"])))
    assert len(result) > 0, "empty command"
    return result
