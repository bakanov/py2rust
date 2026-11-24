"""Bounded documents and normalized tokens with positions in the untouched source text."""

# ruff: noqa: PLR1711, C414 - explicit returns and sorting typed lists

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_string,
    regex_findall,
    unicode_normalize,
)


@dataclass
class Token:
    value: str
    start: int
    end: int


@dataclass
class Source:
    identifier: str
    text: str
    tokens: list[Token]


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def tokenize(text: str) -> list[Token]:
    words: list[str] = regex_findall(
        r"[^\x00-\x2f\x3a-\x40\x5b-\x60\x7b-\x9f\u00a0\u1680\u2000-\u206f\u3000-\u303f]+", text
    )
    assert len(words) <= 2048, "document exceeds 2048 tokens"
    result: list[Token] = []
    cursor: int = 0
    for word in words:
        start: int = cursor + text[cursor:].find(word)
        cursor = start + len(word)
        normalized: str = unicode_normalize("NFC", unicode_normalize("NFC", word).casefold())
        assert len(normalized.encode()) <= 128, "normalized token exceeds 128 bytes"
        result.append(Token(normalized, start, cursor))
    return result


def load(value: Json) -> list[Source]:
    exact(value, ["version", "documents"])
    assert json_int(value["version"]) == 1, "unsupported document version"
    documents: list[Json] = json_array(value["documents"])
    assert len(documents) <= 16, "document count exceeds 16"
    sources: dict[str, Source] = {}
    total: int = 0
    for document in documents:
        exact(document, ["id", "text"])
        identifier: str = json_string(document["id"])
        assert (
            1 <= len(identifier) <= 128 and len(identifier.encode()) <= 512 and "\x00" not in identifier
        ), "invalid id"
        assert identifier not in sources, "duplicate document id"
        text: str = json_string(document["text"])
        assert len(text.encode()) <= 65536, "document exceeds 64 KiB"
        tokens: list[Token] = tokenize(text)
        total = total + len(tokens)
        assert total <= 8192, "corpus exceeds 8192 tokens"
        sources[identifier] = Source(identifier, text, tokens)
    result: list[Source] = []
    for identifier in sorted(list(sources)):
        result.append(sources[identifier])
    return result


def document(sources: list[Source]) -> Json:
    rows: list[Json] = []
    for source in sources:
        rows.append({"id": source.identifier, "text": source.text})
    return {"version": 1, "documents": rows}
