"""Structural field changes for reviewing a migration before it writes anything."""

from py2rust.stdlib import Json, json_equal, json_keys, json_kind


def changes(before: Json, after: Json, prefix: str) -> list[Json]:
    result: list[Json] = []
    if json_equal(before, after):
        return result
    if json_kind(before) != "object" or json_kind(after) != "object":
        result.append({"path": prefix, "change": "replace", "before": before, "after": after})
        return result
    keys: list[str] = json_keys(before)
    for key in json_keys(after):
        if key not in keys:
            keys.append(key)
    keys.sort()
    for key in keys:
        path: str = key
        if prefix != "":
            path = prefix + "." + key
        if key not in before:
            result.append({"path": path, "change": "add", "after": after[key]})
        elif key not in after:
            result.append({"path": path, "change": "remove", "before": before[key]})
        else:
            result.extend(changes(before[key], after[key], path))
    return result
