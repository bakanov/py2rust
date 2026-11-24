"""Typed merge results and bounded, unambiguous paths into JSON values."""

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_keys, json_kind, regex_fullmatch


@dataclass
class Change:
    path: str
    action: str
    before: str
    after: str
    removed: list[str]
    written: list[str]


@dataclass
class Merged:
    value: Json
    changes: list[Change]


@dataclass
class Recorded:
    origins: dict[str, str]
    events: list[Json]
    conflicts: list[Json]
    used: list[str]


def child(path: str, key: str) -> str:
    return path + "/" + key.replace("~", "~0").replace("/", "~1")


def pointer(path: str) -> str:
    assert len(path.encode()) <= 4096 and (path == "" or path.startswith("/")), "invalid JSON Pointer"
    assert regex_fullmatch("([^~]|~[01])*", path), "invalid JSON Pointer escape"
    return path


def locations(value: Json, path: str, depth: int) -> list[str]:
    assert depth <= 24, "configuration exceeds 24 nesting levels"
    pointer(path)
    result: list[str] = [path]
    if json_kind(value) == "object":
        for key in json_keys(value):
            result.extend(locations(value[key], child(path, key), depth + 1))
            assert len(result) <= 20000, "configuration exceeds 20000 nodes"
    elif json_kind(value) == "array":
        items: list[Json] = json_array(value)
        for index in range(len(items)):
            result.extend(locations(items[index], child(path, str(index)), depth + 1))
            assert len(result) <= 20000, "configuration exceeds 20000 nodes"
    return result
