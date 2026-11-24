"""Explicit unsigned and signed16 codecs, strict JSON fields and stable fingerprints."""

# ruff: noqa: PLR1711 - explicit returns

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


def exact(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def unsigned(data: bytes) -> int:
    return int.from_bytes(data, "little")


def signed16(data: bytes) -> int:
    value: int = unsigned(data)
    return value - 65536 if value >= 32768 else value


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))
