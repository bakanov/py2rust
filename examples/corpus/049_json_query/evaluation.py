"""Total filter predicates and explicit missing-path handling for heterogeneous saved JSON."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_equal,
    json_keys,
    json_kind,
    json_scalar_compare,
    json_string,
    regex_fullmatch,
)


def lookup(row: Json, spec: Json) -> tuple[bool, Json]:
    value: Json = row
    for component in json_array(spec["parts"]):
        part: str = json_string(component)
        if json_kind(value) == "object" and part in json_keys(value):
            value = value[part]
        elif json_kind(value) == "array" and len(part) < 19 and regex_fullmatch("0|[1-9][0-9]*", part):
            index: int = int(part)
            if index >= len(json_array(value)):
                return (False, None)
            value = value[index]
        else:
            return (False, None)
    return (True, value)


def required(row: Json, spec: Json) -> Json:
    found: tuple[bool, Json] = lookup(row, spec)
    assert found[0], "missing field " + json_string(spec["path"])
    return found[1]


def predicate(row: Json, spec: Json) -> bool:
    found: tuple[bool, Json] = lookup(row, spec)
    operator: str = json_string(spec["operator"])
    if operator in ["exists", "missing"]:
        return found[0] if operator == "exists" else not found[0]
    if not found[0]:
        return False
    actual: Json = found[1]
    expected: Json = spec["value"]
    if operator in ["==", "!="]:
        same: bool = json_equal(actual, expected)
        return same if operator == "==" else not same
    if operator == "contains" and json_kind(actual) == "string" and json_kind(expected) == "string":
        return json_string(expected) in json_string(actual)
    if operator in ["in", "contains"]:
        container: Json = expected if operator == "in" else actual
        needle: Json = actual if operator == "in" else expected
        if json_kind(container) == "array":
            for value in json_array(container):
                if json_equal(value, needle):
                    return True
        return False
    if json_kind(actual) != json_kind(expected) or json_kind(actual) in ["array", "object"]:
        return False
    comparison: int = json_scalar_compare(actual, expected)
    return (
        (operator == "<" and comparison < 0)
        or (operator == "<=" and comparison <= 0)
        or (operator == ">" and comparison > 0)
        or (operator == ">=" and comparison >= 0)
    )


def matches(row: Json, tests: list[Json]) -> bool:
    stack: list[bool] = []
    for test in tests:
        operator: str = json_string(test["operator"])
        if operator == "not":
            stack[-1] = not stack[-1]
        elif operator in ["and", "or"]:
            right: bool = stack.pop()
            left: bool = stack.pop()
            stack.append(left and right if operator == "and" else left or right)
        else:
            stack.append(predicate(row, test))
    return stack[0]
