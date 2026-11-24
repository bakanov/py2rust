"""Strict numeric/text fields and safe XML labels for the complete dashboard project."""

# ruff: noqa: PLR1711 - explicit returns

from py2rust.stdlib import (
    Json,
    json_canonical,
    json_float,
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


def label(value: Json, limit: int, empty: bool) -> str:
    result: str = text(value)
    assert len(result) <= limit and (empty or result.strip() != ""), "label length or empty label"
    for character in result:
        code: int = ord(character)
        assert code >= 32 and not 127 <= code <= 159 and not 55296 <= code <= 57343, "control or surrogate in label"
        assert code % 65536 not in [65534, 65535], "noncharacter in label"
    return result


def number(value: Json) -> float:
    result: float = json_float(value)
    assert abs(result) <= 1e12 and (result == 0.0 or abs(result) >= 1e-12), "value magnitude range"
    return result


def escaped(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def encoded(value: Json) -> bytes:
    return (json_canonical(value) + "\n").encode()


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))
