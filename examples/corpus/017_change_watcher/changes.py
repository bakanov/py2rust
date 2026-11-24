"""Bounded recursive JSON traversal, ignored subtrees and explicit structural changes."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_equal,
    json_keys,
    json_kind,
    regex_fullmatch,
)


def pointer(value: str) -> str:
    assert len(value) <= 1024 and (value == "" or value.startswith("/")), "expected a JSON Pointer"
    assert regex_fullmatch("([^~]|~[01])*", value), "invalid pointer escape"
    return value


def child(path: str, key: str) -> str:
    return path + "/" + key.replace("~", "~0").replace("/", "~1")


def hidden(path: str, ignored: list[str]) -> bool:
    for prefix in ignored:
        if prefix == "" or path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def nodes(value: Json, depth: int) -> int:
    assert depth <= 24, "snapshot exceeds 24 levels"
    count: int = 1
    if json_kind(value) == "object":
        for key in json_keys(value):
            count = count + nodes(value[key], depth + 1)
            assert count <= 2000, "snapshot exceeds 2000 nodes"
    elif json_kind(value) == "array":
        for item in json_array(value):
            count = count + nodes(item, depth + 1)
            assert count <= 2000, "snapshot exceeds 2000 nodes"
    return count


def mask(value: Json, path: str, ignored: list[str]) -> Json:
    if hidden(path, ignored):
        return None
    if json_kind(value) == "object":
        result: Json = {}
        for key in json_keys(value):
            following: str = child(path, key)
            if not hidden(following, ignored):
                result[key] = mask(value[key], following, ignored)
        return result
    if json_kind(value) == "array":
        items: list[Json] = []
        source: list[Json] = json_array(value)
        for index in range(len(source)):
            # Ignored array slots keep their index and contain a null placeholder.
            items.append(mask(source[index], child(path, str(index)), ignored))
        return items
    return value


def difference(before: Json, after: Json, path: str) -> list[Json]:
    changes: list[Json] = []
    if json_equal(before, after):
        return changes
    if json_kind(before) == "object" and json_kind(after) == "object":
        keys: list[str] = json_keys(before)
        for key in json_keys(after):
            if key not in before:
                keys.append(key)
        keys.sort()
        for key in keys:
            following: str = child(path, key)
            if key not in before:
                changes.append({"op": "add", "path": following, "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"op": "remove", "path": following, "before": before[key], "after": None})
            else:
                changes.extend(difference(before[key], after[key], following))
    elif json_kind(before) == "array" and json_kind(after) == "array":
        left: list[Json] = json_array(before)
        right: list[Json] = json_array(after)
        for index in range(max(len(left), len(right))):
            following: str = child(path, str(index))
            if index >= len(left):
                changes.append({"op": "add", "path": following, "before": None, "after": right[index]})
            elif index >= len(right):
                changes.append({"op": "remove", "path": following, "before": left[index], "after": None})
            else:
                changes.extend(difference(left[index], right[index], following))
    else:
        changes.append({"op": "replace", "path": path, "before": before, "after": after})
    return changes
