"""A small, inspectable JSON store. The HTTP adapter serializes callbacks.

Every successful mutation atomically replaces state.json. Uploaded bytes live in
separate files, so messages and search do not read attachment contents.
"""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_get,
    json_kind,
    json_loads,
    json_string,
    mkdir_all,
    path_exists,
    path_join,
    pretty,
    read_text,
    write_text_atomic,
)


def data_directory() -> str:
    return env_get("PAPER_PLANE_DATA", "data")


def data_path(name: str) -> str:
    return path_join(data_directory(), name)


def text(value: Json, key: str) -> str:
    if json_kind(value) != "object":
        return ""
    field: Json = json_get(value, key, "")
    if json_kind(field) == "string":
        return json_string(field)
    return ""


def items(value: Json, key: str) -> list[Json]:
    field: Json = json_get(value, key, [])
    if json_kind(field) == "array":
        return json_array(field)
    return []


def load_state() -> Json:
    return json_loads(read_text(data_path("state.json")))


def save_state(state: Json) -> None:
    write_text_atomic(data_path("state.json"), pretty(state))


def initialize() -> None:
    mkdir_all(data_directory())
    mkdir_all(data_path("uploads"))
    if not path_exists(data_path("state.json")):
        initial: Json = {
            "revision": 1,
            "users": [],
            "chats": [{"id": "general", "title": "General", "kind": "chat", "owner": ""}],
            "messages": [],
            "uploads": [],
        }
        save_state(initial)
