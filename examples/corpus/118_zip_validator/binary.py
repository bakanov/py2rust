"""Checked little-endian fields, strict settings and portable report primitives."""

# ruff: noqa: PLR1711 - explicit subset returns
from py2rust.stdlib import (
    Json,
    json_canonical,
    json_int,
    json_keys,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    return json_string(value)


def number(data: bytes, offset: int, width: int) -> int:
    assert 0 <= offset <= len(data) - width, "truncated field"
    return int.from_bytes(data[offset : offset + width], "little")


def limits(value: Json) -> Json:
    exact(value, ["entries", "entry_bytes", "total_bytes"])
    assert 0 <= json_int(value["entries"]) <= 2048, "entry count limit"
    assert 0 <= json_int(value["entry_bytes"]) <= 16777216, "entry expansion limit"
    assert 0 <= json_int(value["total_bytes"]) <= 67108864, "total expansion limit"
    return value


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(value: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), value))
