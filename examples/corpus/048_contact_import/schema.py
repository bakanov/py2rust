"""Explicit contact normalization and composite matching policies; original rows stay intact."""

import unicodedata
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_get,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


@dataclass
class Parsed:
    values: dict[str, str]
    errors: list[str]


def field_names() -> list[str]:
    return ["name", "email", "phone", "address", "organization"]


def exact(value: Json, keys: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(keys), "unexpected document fields"
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def identifier(value: Json) -> str:
    text: str = json_string(value)
    assert 1 <= len(text.encode()) <= 128 and text.strip() == text, "invalid source or id"
    assert regex_fullmatch("[^\x00-\x1f\x7f]+", text), "invalid source or id"
    return text


def normalize(name: str, value: str) -> str:
    assert len(value.encode()) <= 2048, "field exceeds 2048 bytes"
    # Normalize whitespace before checking remaining controls; never infer country/address abbreviations.
    text: str = unicodedata.normalize("NFC", " ".join(value.split()))
    assert regex_fullmatch("[^\x00-\x1f\x7f]*", text), "control character in field"
    if text == "":
        return text
    if name == "email":
        assert regex_fullmatch("[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+", text), "invalid email address"
        pieces: list[str] = text.split("@")
        assert len(pieces[0]) <= 64 and not pieces[0].startswith(".") and not pieces[0].endswith(".")
        assert ".." not in pieces[0] and len(pieces[1]) <= 253
        for label in pieces[1].split("."):
            assert regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        return pieces[0] + "@" + pieces[1].lower()
    if name == "phone":
        assert regex_fullmatch("[+0-9 ().-]+", text), "invalid phone punctuation"
        for separator in [" ", "(", ")", ".", "-"]:
            text = text.replace(separator, "")
        assert regex_fullmatch("\\+[1-9][0-9]{6,14}", text), "phone requires an explicit international prefix"
        return text
    return text


def parse(row: Json) -> Parsed:
    errors: list[str] = []
    values: dict[str, str] = {}
    if json_kind(row) != "object":
        return Parsed(values, ["object"])
    for key in json_keys(row):
        if key not in field_names() and key not in ["source", "id"]:
            errors.append("unknown:" + key)
    for key in ["source", "id"]:
        try:
            identifier(json_get(row, key, None))
        except Exception:  # noqa: BLE001 - retain all invalid fields
            errors.append(key)
    meaningful: bool = False
    for key in field_names():
        try:
            value: str = normalize(key, json_string(json_get(row, key, "")))
            values[key] = value
            if key != "organization" and value != "":
                meaningful = True
        except Exception:  # noqa: BLE001 - retain all invalid fields
            errors.append(key)
    if not meaningful:
        errors.append("empty_contact")
    return Parsed(values, errors)


def policy(value: Json) -> list[list[str]]:
    rules: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for rule in json_array(value):
        keys: list[str] = []
        for item in json_array(rule):
            name: str = json_string(item)
            assert name in field_names() and name not in keys, "invalid matching field"
            keys.append(name)
        assert len(keys) > 0 and tuple(sorted(keys)) not in seen, "empty or duplicate matching rule"
        seen.add(tuple(sorted(keys)))
        rules.append(sorted(keys))
    assert 1 <= len(rules) <= 8, "expected 1..8 matching rules"
    # Rules have OR semantics; the fields within each rule have AND semantics.
    return sorted(rules)
