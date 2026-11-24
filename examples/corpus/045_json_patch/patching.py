"""Functional patch application; no source value is mutated even when a later guard fails."""

from model import digest, fields, index, same, tokens, validate

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


def validate_patch(patch: Json, node_limit: int, change_limit: int) -> list[Json]:
    fields(patch, ["version", "base_sha256", "target_sha256", "changes"])
    assert json_int(patch["version"]) == 1, "unsupported patch version"
    for name in ["base_sha256", "target_sha256"]:
        assert regex_fullmatch("[0-9a-f]{64}", json_string(patch[name])), "invalid document hash"
    changes: list[Json] = json_array(patch["changes"])
    assert len(changes) <= change_limit, "patch change limit exceeded"
    for change in changes:
        fields(change, ["op", "path", "before", "after"])
        operation: str = json_string(change["op"])
        assert operation in ["add", "remove", "replace"], "unsupported patch operation"
        path: str = json_string(change["path"])
        tokens(path)
        assert path != "" or operation == "replace", "root permits only replacement"
        assert operation != "add" or change["before"] is None, "add requires null before placeholder"
        assert operation != "remove" or change["after"] is None, "remove requires null after placeholder"
        validate(change["before"], node_limit)
        validate(change["after"], node_limit)
    return changes


def edited(value: Json, parts: list[str], depth: int, change: Json) -> Json:
    operation: str = json_string(change["op"])
    if depth == len(parts):
        assert operation == "replace" and same(value, change["before"]), "old value mismatch"
        return change["after"]
    token: str = parts[depth]
    leaf: bool = depth + 1 == len(parts)
    if json_kind(value) == "object":
        result: Json = {}
        for name in json_keys(value):
            result[name] = value[name]
        if not leaf:
            assert token in value, "missing parent object key"
            result[token] = edited(value[token], parts, depth + 1, change)
        elif operation == "add":
            assert token not in value, "add would replace an existing object key"
            result[token] = change["after"]
        else:
            assert token in value and same(value[token], change["before"]), "old value mismatch"
            if operation == "remove":
                del result[token]
            else:
                result[token] = change["after"]
        return result
    assert json_kind(value) == "array", "path traverses a scalar"
    items: list[Json] = json_array(value)
    position: int = index(token, len(items), leaf and operation == "add")
    if not leaf:
        items[position] = edited(items[position], parts, depth + 1, change)
    elif operation == "add":
        items.insert(position, change["after"])
    else:
        assert same(items[position], change["before"]), "old value mismatch"
        if operation == "remove":
            items.pop(position)
        else:
            items[position] = change["after"]
    return items


def apply(base: Json, patch: Json, node_limit: int, change_limit: int) -> Json:
    changes: list[Json] = validate_patch(patch, node_limit, change_limit)
    assert digest(base) == json_string(patch["base_sha256"]), "stale base document"
    result: Json = base
    for change in changes:
        result = edited(result, tokens(json_string(change["path"])), 0, change)
        validate(result, node_limit)
    assert digest(result) == json_string(patch["target_sha256"]), "target document hash mismatch"
    assert digest(base) == json_string(patch["base_sha256"]), "source value was mutated"
    return result


def reverse(patch: Json) -> Json:
    changes: list[Json] = json_array(patch["changes"])
    changes.reverse()
    result: list[Json] = []
    for change in changes:
        operation: str = json_string(change["op"])
        if operation == "add":
            operation = "remove"
        elif operation == "remove":
            operation = "add"
        result.append({"op": operation, "path": change["path"], "before": change["after"], "after": change["before"]})
    return {
        "version": 1,
        "base_sha256": patch["target_sha256"],
        "target_sha256": patch["base_sha256"],
        "changes": result,
    }
