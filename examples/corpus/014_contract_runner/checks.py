"""Named field and snapshot comparisons with explicit missing-value handling."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_equal,
    json_get,
    json_int,
    json_kind,
    json_loads,
    json_parse,
    json_string,
    path_exists,
    path_join,
    pretty,
    read_text,
    regex_fullmatch,
    write_text_atomic,
)


def field_path(document: Json, path: str) -> Json:
    current: Json = document
    if path == "$":
        return {"exists": True, "value": current}
    for part in path.split("."):
        if json_kind(current) == "object":
            if part not in current:
                return {"exists": False, "value": None}
            current = current[part]
        elif json_kind(current) == "array":
            if not regex_fullmatch("0|[1-9][0-9]*", part):
                return {"exists": False, "value": None}
            index: int = json_int(json_parse(part, -1))
            values: list[Json] = json_array(current)
            if index < 0 or index >= len(values):
                return {"exists": False, "value": None}
            current = values[index]
        else:
            return {"exists": False, "value": None}
    return {"exists": True, "value": current}


def same_value(left: Json, right: Json) -> bool:
    return json_equal(left, right)


def field_mismatches(document: Json, rules: list[Json]) -> list[Json]:
    failures: list[Json] = []
    for rule in rules:
        path: str = json_string(rule["path"])
        actual: Json = field_path(document, path)
        expected_presence: bool = json_bool(json_get(rule, "exists", True))
        present: bool = json_bool(actual["exists"])
        if present != expected_presence:
            failures.append({"check": "presence", "path": path, "expected": expected_presence, "actual": present})
        elif present and "value" in rule and not same_value(actual["value"], rule["value"]):
            failures.append({"check": "value", "path": path, "expected": rule["value"], "actual": actual["value"]})
    return failures


def snapshot_mismatches(name: str, body: Json, directory: str, update: bool) -> list[Json]:
    failures: list[Json] = []
    if name == "":
        return failures
    destination: str = path_join(directory, name)
    if update:
        write_text_atomic(destination, pretty(body))
        return failures
    if not path_exists(destination):
        failures.append({"check": "snapshot", "snapshot": name, "reason": "missing"})
        return failures
    try:
        expected: Json = json_loads(read_text(destination))
        if not same_value(body, expected):
            failures.append({"check": "snapshot", "snapshot": name, "reason": "different"})
    except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
        failures.append({"check": "snapshot", "snapshot": name, "reason": "unreadable"})
    return failures
