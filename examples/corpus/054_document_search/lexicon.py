"""Deterministic Unicode normalization and explicit separators, without a locale or stemming."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines

from py2rust.stdlib import (
    Json,
    json_keys,
    json_string,
    regex_findall,
    unicode_normalize,
)


def exact(value: Json, names: list[str]) -> None:
    assert json_keys(value) == sorted(names), "unexpected object fields"
    return


def identifier(value: Json) -> str:
    name: str = json_string(value)
    assert 1 <= len(name.encode()) <= 128, "document ID must contain 1..128 UTF-8 bytes"
    return name


def tokens(text: str) -> list[str]:
    normalized: str = unicode_normalize("NFKC", text).casefold()
    assert len(normalized.encode()) <= 262144, "normalized text exceeds 256 KiB"
    words: list[str] = regex_findall(
        r"[^\x00-\x2f\x3a-\x40\x5b-\x60\x7b-\x9f\u00a0\u1680\u2000-\u206f\u3000-\u303f]+", normalized
    )
    assert len(words) <= 4096, "text exceeds 4096 tokens"
    for word in words:
        assert len(word.encode()) <= 128, "token exceeds 128 UTF-8 bytes"
    return words


def document(value: Json) -> Json:
    exact(value, ["id", "title", "text"])
    identifier(value["id"])
    assert len(json_string(value["title"]).encode()) <= 512, "title exceeds 512 bytes"
    assert len(json_string(value["text"]).encode()) <= 16384, "text exceeds 16 KiB"
    return value


def frequencies(value: Json) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in ["title", "text"]:
        weight: int = 3 if field == "title" else 1
        for word in tokens(json_string(value[field])):
            counts[word] = counts.get(word, 0) + weight
    assert len(counts) <= 256, "document exceeds 256 distinct terms"
    return counts
