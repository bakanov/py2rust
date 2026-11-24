"""Deterministic recursive differences with positional array edits and guarded old values."""

from model import child, digest, same

from py2rust.stdlib import Json, json_array, json_keys, json_kind


def changes(before: Json, after: Json, path: str, limit: int) -> list[Json]:
    result: list[Json] = []
    if same(before, after):
        return result
    if json_kind(before) == "object" and json_kind(after) == "object":
        keys: list[str] = json_keys(before)
        for name in json_keys(after):
            if name not in before:
                keys.append(name)
        keys.sort()
        for name in keys:
            following: str = child(path, name)
            if name not in before:
                result.append({"op": "add", "path": following, "before": None, "after": after[name]})
            elif name not in after:
                result.append({"op": "remove", "path": following, "before": before[name], "after": None})
            else:
                result.extend(changes(before[name], after[name], following, limit))
            assert len(result) <= limit, "patch change limit exceeded"
    elif json_kind(before) == "array" and json_kind(after) == "array":
        left: list[Json] = json_array(before)
        right: list[Json] = json_array(after)
        for position in range(min(len(left), len(right))):
            result.extend(changes(left[position], right[position], child(path, str(position)), limit))
            assert len(result) <= limit, "patch change limit exceeded"
        # Removing the tail from the end keeps every subsequent path valid.
        for position in range(len(left) - 1, len(right) - 1, -1):
            result.append({"op": "remove", "path": child(path, str(position)), "before": left[position], "after": None})
            assert len(result) <= limit, "patch change limit exceeded"
        for position in range(len(left), len(right)):
            result.append({"op": "add", "path": child(path, str(position)), "before": None, "after": right[position]})
            assert len(result) <= limit, "patch change limit exceeded"
    else:
        result.append({"op": "replace", "path": path, "before": before, "after": after})
    return result


def difference(before: Json, after: Json, limit: int) -> Json:
    return {
        "version": 1,
        "base_sha256": digest(before),
        "target_sha256": digest(after),
        "changes": changes(before, after, "", limit),
    }
