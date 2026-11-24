"""Bounded, atomically replaced UTF-8 paste snapshots."""

from model import setting, validate_record

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_int,
    json_loads,
    json_string,
    path_exists,
    pretty,
    read_text,
    write_text_atomic,
)


def state_path() -> str:
    return env_get("PASTE_STATE", "pastes.json")


def document(records: list[Json]) -> str:
    return pretty({"version": 1, "pastes": records})


def load() -> list[Json]:
    content: str = read_text(state_path())
    assert len(content.encode()) <= setting("PASTE_MAX_STATE", 8388608), "snapshot exceeds byte limit"
    parsed: Json = json_loads(content)
    assert json_int(parsed["version"]) == 1, "unsupported snapshot version"
    return json_array(parsed["pastes"])


def save(records: list[Json]) -> None:
    assert len(records) <= setting("PASTE_LIMIT", 1000), "paste count exceeds limit"
    content: str = document(records)
    assert len(content.encode()) <= setting("PASTE_MAX_STATE", 8388608), "snapshot exceeds byte limit"
    write_text_atomic(state_path(), content)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def find(records: list[Json], identifier: str) -> Json:
    for record in records:
        if json_string(record["id"]) == identifier:
            return record
    return None


def initialize() -> None:
    if not path_exists(state_path()):
        save([])
    records: list[Json] = load()
    assert len(records) <= setting("PASTE_LIMIT", 1000), "stored paste count exceeds limit"
    seen: set[str] = set()
    for record in records:
        validate_record(record)
        for key in ["id", "read_key", "delete_key"]:
            value: str = json_string(record[key])
            if value != "":
                assert value not in seen, "duplicate identifier or capability"
                seen.add(value)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
