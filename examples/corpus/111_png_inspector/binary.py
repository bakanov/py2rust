"""Small binary and JSON primitives shared by the PNG scanner and its reports."""

# ruff: noqa: BLE001, PLR1711 - normalized codec errors and explicit returns

from py2rust.stdlib import (
    Json,
    json_canonical,
    json_keys,
    json_kind,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def unsigned(data: bytes) -> int:
    return int.from_bytes(data, "big")


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def utf8(data: bytes) -> str:
    try:
        return data.decode()
    except Exception:
        assert False, "invalid UTF-8 metadata"
    return ""


def keyword(data: bytes) -> str:
    assert 1 <= len(data) <= 79, "keyword length"
    assert data[0] != 32 and data[-1] != 32 and b"  " not in data, "keyword spacing"
    for value in data:
        assert 32 <= value <= 126 or 161 <= value <= 255, "keyword character"
    return data.decode("latin-1")
