"""Strict JSON values and immutable top-down RGB samples."""

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
class Image:
    width: int
    height: int
    maximum: int
    samples: list[int]


@dataclass
class Sprite:
    index: int
    name: str
    data: bytes
    image: Image


def exact(value: Json, fields: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def name_of(value: Json) -> str:
    name: str = text(value)
    assert 1 <= len(name) <= 64 and name.strip() != "", "sprite name length"
    for character in name:
        assert ord(character) >= 32 and not 127 <= ord(character) <= 159, "control in sprite name"
    return name
