"""Exact UTF-8 line tokens, including LF, CRLF, lone CR and unterminated final lines."""

# ruff: noqa: PLR1711 - explicit returns
from py2rust.stdlib import (
    Json,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def exact(value: Json, keys: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(keys), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside permitted range"
    return result


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def lines(data: bytes) -> list[str]:
    assert len(data) <= 65536, "text byte limit exceeded"
    data.decode()
    result: list[str] = []
    start: int = 0
    offset: int = 0
    while offset < len(data):
        current: int = data[offset]
        offset = offset + 1
        if current in [10, 13]:
            if current == 13 and offset < len(data) and data[offset] == 10:
                offset = offset + 1
            result.append(data[start:offset].decode())
            start = offset
    if start < len(data):
        result.append(data[start:].decode())
    assert len(result) <= 1024, "text line limit exceeded"
    return result


def identity(data: bytes) -> Json:
    ending: str = "none"
    if data.endswith(b"\r\n"):
        ending = "crlf"
    elif data.endswith(b"\n"):
        ending = "lf"
    elif data.endswith(b"\r"):
        ending = "cr"
    return {"bytes": len(data), "lines": len(lines(data)), "sha256": digest(data), "ending": ending}


def metadata(value: Json) -> None:
    exact(value, ["bytes", "lines", "sha256", "ending"])
    integer(value["bytes"], 0, 65536)
    integer(value["lines"], 0, 1024)
    assert regex_fullmatch("[0-9a-f]{64}", json_string(value["sha256"])), "invalid digest"
    assert json_string(value["ending"]) in ["none", "lf", "crlf", "cr"], "invalid final line ending"
    return
