"""Describe net observed changes, including moves into occupied paths and rename cycles."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from files import identity
from py2rust.stdlib import (
    Json, json_equal, json_int, json_keys, json_string,
)


def identities(entries: Json) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in json_keys(entries):
        key: str = identity(entries[path])
        if key not in result:
            result[key] = []
        result[key].append(path)
    return result


def event(kind: str, path: str, previous: str, before: Json, after: Json, now: int) -> Json:
    return {
        "id": 0,
        "kind": kind,
        "path": path,
        "previous_path": previous,
        "before": before,
        "after": after,
        "first_ms": now,
        "last_ms": now,
        "emitted_ms": 0,
    }


def changes(before: Json, after: Json, now: int) -> list[Json]:
    old_ids: dict[str, list[str]] = identities(before)
    new_ids: dict[str, list[str]] = identities(after)
    moves: dict[str, str] = {}
    targets: set[str] = set()
    for path in sorted(json_keys(before)):
        entry: Json = before[path]
        key: str = identity(entry)
        if len(old_ids[key]) == 1 and key in new_ids and len(new_ids[key]) == 1:
            target: str = new_ids[key][0]
            regular: bool = json_string(entry["kind"]) == "file"
            if target != path and (
                not regular or (json_int(entry["links"]) == 1 and json_int(after[target]["links"]) == 1)
            ):
                moves[path] = target
                targets.add(target)
    result: list[Json] = []
    for path in sorted(json_keys(before)):
        if path not in moves and (path not in json_keys(after) or path in targets):
            result.append(event("deleted", path, "", before[path], None, now))
    for path in sorted(json_keys(before)):
        if path in moves:
            result.append(event("renamed", moves[path], path, before[path], after[moves[path]], now))
    for path in sorted(json_keys(after)):
        if path in targets:
            continue
        if path not in json_keys(before) or path in moves:
            result.append(event("created", path, "", None, after[path], now))
        elif not json_equal(before[path], after[path]):
            result.append(event("modified", path, "", before[path], after[path], now))
    return result
