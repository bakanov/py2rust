"""Normalize a bounded scalar schema and order its acyclic prerequisite graph."""

# ruff: noqa: PLR1711, BLE001 - explicit returns and safe type probes
from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_equal,
    json_get,
    json_int,
    json_keys,
    json_kind,
    json_scalar_compare,
    json_string,
    regex_fullmatch,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    number: int = json_int(value)
    assert low <= number <= high, "integer outside permitted range"
    return number


def problem(value: Json, field: Json, choices: bool) -> str:
    kind: str = json_string(field["type"])
    if value is None:
        if not json_bool(field["nullable"]):
            return "null"
    else:
        actual: str = json_kind(value)
        if kind == "integer":
            try:
                json_int(value)
            except Exception:
                return "type"
        elif actual != kind:
            return "type"
        if kind in ["integer", "number"]:
            if field["minimum"] is not None and json_scalar_compare(value, field["minimum"]) < 0:
                return "range"
            if field["maximum"] is not None and json_scalar_compare(value, field["maximum"]) > 0:
                return "range"
        if kind == "string":
            size: int = len(json_string(value))
            if size < json_int(field["min_length"]) or size > json_int(field["max_length"]):
                return "length"
    allowed: list[Json] = json_array(field["choices"])
    if choices and len(allowed) > 0:
        found: bool = False
        for option in allowed:
            if json_equal(value, option):
                found = True
        if not found:
            return "choice"
    return ""


def field(raw: Json) -> Json:
    required: list[str] = ["name", "env", "type"]
    optional: list[str] = [
        "required",
        "secret",
        "nullable",
        "default",
        "choices",
        "minimum",
        "maximum",
        "min_length",
        "max_length",
        "requires",
    ]
    keys: list[str] = json_keys(raw)
    assert set(required) <= set(keys) and set(keys) <= set(required + optional), "invalid field shape"
    name: str = json_string(raw["name"])
    variable: str = json_string(raw["env"])
    kind: str = json_string(raw["type"])
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_]{0,31}", name), "invalid field name"
    assert regex_fullmatch("[A-Z_][A-Z0-9_]{0,63}", variable), "invalid environment name"
    assert not variable.startswith("SETTINGS_"), "reserved environment name"
    assert kind in ["string", "integer", "number", "bool"], "unknown scalar type"
    normalized: Json = {
        "name": name,
        "env": variable,
        "type": kind,
        "required": json_bool(json_get(raw, "required", False)),
        "secret": json_bool(json_get(raw, "secret", False)),
        "nullable": json_bool(json_get(raw, "nullable", False)),
        "has_default": "default" in keys,
        "default": json_get(raw, "default", None),
        "minimum": json_get(raw, "minimum", None),
        "maximum": json_get(raw, "maximum", None),
        "min_length": integer(json_get(raw, "min_length", 0), 0, 1024),
        "max_length": integer(json_get(raw, "max_length", 1024), 0, 1024),
        "choices": json_array(json_get(raw, "choices", [])),
        "requires": json_array(json_get(raw, "requires", [])),
    }
    assert json_int(normalized["min_length"]) <= json_int(normalized["max_length"]), "invalid length range"
    for bound in ["minimum", "maximum"]:
        value: Json = normalized[bound]
        if bound in keys:
            assert kind in ["integer", "number"] and json_kind(value) == "number", "invalid numeric bound"
            if kind == "integer":
                json_int(value)
    if normalized["minimum"] is not None and normalized["maximum"] is not None:
        assert json_scalar_compare(normalized["minimum"], normalized["maximum"]) <= 0, "invalid numeric range"
    if "min_length" in keys or "max_length" in keys:
        assert kind == "string", "length requires a string field"
    options: list[Json] = json_array(normalized["choices"])
    assert len(options) <= 16 and ("choices" not in keys or len(options) > 0), "invalid choices"
    seen: list[Json] = []
    for option in options:
        assert problem(option, normalized, False) == "", "invalid choice value"
        for earlier in seen:
            assert not json_equal(option, earlier), "duplicate choice"
        seen.append(option)
    if json_bool(normalized["has_default"]):
        assert problem(normalized["default"], normalized, True) == "", "invalid default"
    assert len(json_array(normalized["requires"])) <= 8, "dependency limit"
    return normalized


def load(value: Json) -> Json:
    exact(value, ["version", "fields"])
    assert json_int(value["version"]) == 1, "unsupported schema version"
    items: list[Json] = json_array(value["fields"])
    assert 1 <= len(items) <= 32, "field count limit"
    fields: Json = {}
    variables: set[str] = set()
    for item in items:
        normalized: Json = field(item)
        name: str = json_string(normalized["name"])
        variable: str = json_string(normalized["env"])
        assert name not in json_keys(fields) and variable not in variables, "duplicate field or variable"
        fields[name] = normalized
        variables.add(variable)
    for name in json_keys(fields):
        dependencies: set[str] = set()
        for rule in json_array(fields[name]["requires"]):
            exact(rule, ["field", "equals"])
            target: str = json_string(rule["field"])
            assert target in json_keys(fields) and target != name and target not in dependencies, "invalid dependency"
            assert problem(rule["equals"], fields[target], True) == "", "invalid dependency predicate"
            dependencies.add(target)
    return fields


def order(fields: Json) -> list[str]:
    result: list[str] = []
    complete: set[str] = set()
    while len(result) < len(json_keys(fields)):
        before: int = len(result)
        for name in sorted(json_keys(fields)):
            ready: bool = name not in complete
            for rule in json_array(fields[name]["requires"]):
                if json_string(rule["field"]) not in complete:
                    ready = False
            if ready:
                result.append(name)
                complete.add(name)
        assert len(result) > before, "cyclic dependencies"
    return result
