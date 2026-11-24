"""Strict job primitives and named, immutable original image bytes."""

# ruff: noqa: PLR1711 - explicit returns

from dataclasses import dataclass

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


@dataclass
class Source:
    name: str
    data: bytes


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def name_of(value: Json) -> str:
    name: str = text(value)
    assert 1 <= len(name) <= 64 and name.strip() != "", "image name length"
    for character in name:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control in image name"
    return name


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def unsigned(data: bytes) -> int:
    return int.from_bytes(data, "little")


def signed32(data: bytes) -> int:
    value: int = unsigned(data)
    return value - 4294967296 if value >= 2147483648 else value
