"""Opaque blob IDs and an atomically replaced metadata index."""

from config import data_directory

from py2rust.stdlib import (
    Json,
    json_array,
    json_get,
    json_int,
    json_kind,
    json_loads,
    json_string,
    list_dir,
    mkdir_all,
    path_exists,
    path_join,
    pretty,
    read_bytes,
    read_text,
    regex_fullmatch,
    remove_file,
    write_bytes,
    write_text_atomic,
)


def index_path() -> str:
    return path_join(data_directory(), "index.json")


def blob_path(identifier: str) -> str:
    assert valid_id(identifier), "invalid blob identifier"
    return path_join(path_join(data_directory(), "blobs"), identifier)


def valid_id(identifier: str) -> bool:
    return regex_fullmatch("[a-f0-9]{64}", identifier)


def text(record: Json, key: str) -> str:
    value: Json = json_get(record, key, "")
    if json_kind(value) == "string":
        return json_string(value)
    return ""


def records() -> list[Json]:
    document: Json = json_loads(read_text(index_path()))
    assert json_int(document["version"]) == 1, "unsupported index version"
    return json_array(document["files"])


def save(entries: list[Json]) -> None:
    document: Json = {"version": 1, "files": entries}
    write_text_atomic(index_path(), pretty(document))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def lookup(identifier: str) -> Json:
    for entry in records():
        if text(entry, "id") == identifier:
            return entry
    return {}


def add(record: Json, payload: bytes) -> None:
    entries: list[Json] = records()
    write_bytes(blob_path(text(record, "id")), payload)
    entries.append(record)
    save(entries)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def erase(identifier: str) -> None:
    remaining: list[Json] = []
    for entry in records():
        if text(entry, "id") != identifier:
            remaining.append(entry)
    save(remaining)
    path: str = blob_path(identifier)
    if path_exists(path):
        remove_file(path)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def read_blob(identifier: str) -> bytes:
    return read_bytes(blob_path(identifier))


def initialize() -> None:
    mkdir_all(data_directory())
    mkdir_all(path_join(data_directory(), "blobs"))
    if not path_exists(index_path()):
        save([])
    kept: list[Json] = []
    known: set[str] = set()
    for entry in records():
        identifier: str = text(entry, "id")
        assert valid_id(identifier), "corrupt index identifier"
        assert identifier not in known, "duplicate index identifier"
        known.add(identifier)
        if path_exists(blob_path(identifier)):
            kept.append(entry)
    save(kept)
    # An interrupted upload can leave a blob before its metadata was committed.
    for name in list_dir(path_join(data_directory(), "blobs")):
        if valid_id(name) and name not in known:
            remove_file(blob_path(name))
    return  # noqa: PLR1711 - explicit return required by repository guidelines
