"""Atomic snapshots, deterministic ordering and startup validation."""

from model import setting, validate_record

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_equal,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("BOOKMARK_STATE", "bookmarks.json")


def load() -> list[Json]:
    content: str = read_text(state_path())
    assert len(content.encode()) <= 8388608, "snapshot too large"
    document: Json = json_loads(content)
    assert json_int(document["version"]) == 1, "unsupported snapshot version"
    return json_array(document["bookmarks"])


def find(records: list[Json], name: str) -> Json:
    for record in records:
        if json_string(record["name"]) == name:
            return record
    return None


def ordered(records: list[Json]) -> list[Json]:
    names: list[str] = []
    for record in records:
        names.append(json_string(record["name"]))
    names.sort()
    result: list[Json] = []
    for name in names:
        result.append(find(records, name))
    return result


def save(records: list[Json]) -> None:
    assert len(records) <= setting("BOOKMARK_LIMIT", 1000), "bookmark limit exceeded"
    content: str = pretty({"version": 1, "bookmarks": ordered(records)})
    assert len(content.encode()) <= 8388608, "snapshot too large"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def replace(records: list[Json], record: Json) -> list[Json]:
    result: list[Json] = []
    for previous in records:
        if json_string(previous["name"]) != json_string(record["name"]):
            result.append(previous)
    result.append(record)
    return result


def initialize() -> None:
    if not path_exists(state_path()):
        save([])
    records: list[Json] = load()
    assert len(records) <= setting("BOOKMARK_LIMIT", 1000), "stored bookmark limit exceeded"
    seen: set[str] = set()
    for record in records:
        assert json_equal(record, validate_record(record)), "stored bookmark is not normalized"
        name: str = json_string(record["name"])
        assert name not in seen, "duplicate stored bookmark"
        seen.add(name)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
