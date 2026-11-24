"""Recursive object overlay; arrays/scalars replace as complete values."""

from model import Change, Merged, Recorded, child, locations

from py2rust.stdlib import Json, json_equal, json_keys, json_kind


def combine(before: Json, incoming: Json, path: str, allowed: set[str]) -> Merged:
    old_kind: str = json_kind(before)
    new_kind: str = json_kind(incoming)
    if old_kind != new_kind and path not in allowed:
        return Merged(before, [Change(path, "conflict", old_kind, new_kind, [], [])])
    if old_kind == "object" and new_kind == "object":
        result: Json = {}
        changes: list[Change] = [Change(path, "merge", old_kind, new_kind, [], [path])]
        for key in json_keys(before):
            result[key] = before[key]
        for key in json_keys(incoming):
            following: str = child(path, key)
            if key in before:
                merged: Merged = combine(before[key], incoming[key], following, allowed)
                result[key] = merged.value
                changes.extend(merged.changes)
            else:
                result[key] = incoming[key]
                changes.append(
                    Change(
                        following,
                        "add",
                        "missing",
                        json_kind(incoming[key]),
                        [],
                        locations(incoming[key], following, 0),
                    )
                )
        return Merged(result, changes)
    action: str = "replace"
    if old_kind != new_kind:
        action = "type_change"
    elif json_equal(before, incoming):
        action = "unchanged"
    return Merged(
        incoming,
        [Change(path, action, old_kind, new_kind, locations(before, path, 0), locations(incoming, path, 0))],
    )


def record(changes: list[Change], layer: str, origins: dict[str, str]) -> Recorded:
    updated: dict[str, str] = origins.copy()
    events: list[Json] = []
    conflicts: list[Json] = []
    used: list[str] = []
    for change in changes:
        event: Json = {
            "path": change.path,
            "layer": layer,
            "previous_layer": updated.get(change.path, ""),
            "action": change.action,
            "before": change.before,
            "after": change.after,
        }
        events.append(event)
        if change.action == "conflict":
            conflicts.append(event)
        else:
            for path in change.removed:
                del updated[path]
            for path in change.written:
                updated[path] = layer
            if change.action == "type_change":
                used.append(change.path)
    return Recorded(updated, events, conflicts, used)
