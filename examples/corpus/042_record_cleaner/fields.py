"""Typed field validation and deterministic normalization, with named reasons."""

from py2rust.stdlib import (
    DateTime,
    Json,
    datetime_iso,
    datetime_parse,
    json_array,
    json_bool,
    json_equal,
    json_float,
    json_get,
    json_int,
    json_kind,
    json_string,
    regex_fullmatch,
)


def text(value: Json, name: str, default: str) -> str:
    return json_string(json_get(value, name, default))


def validate_string(value: Json, rule: Json) -> Json:
    assert json_kind(value) == "string", "expected string"
    content: str = json_string(value)
    if json_bool(json_get(rule, "trim", True)):
        content = content.strip()
    casing: str = text(rule, "case", "preserve")
    if casing == "lower":
        content = content.lower()
    if casing == "upper":
        content = content.upper()
    minimum: int = json_int(json_get(rule, "min_length", 0))
    maximum: int = json_int(json_get(rule, "max_length", 100000))
    assert len(content) >= minimum, "string is too short"
    assert len(content) <= maximum, "string is too long"
    if "pattern" in rule:
        assert regex_fullmatch(json_string(rule["pattern"]), content), "pattern mismatch"
    return content


def validate_integer(value: Json, rule: Json) -> Json:
    assert json_kind(value) == "number", "expected integer"
    integer: int = json_int(value)
    if "min" in rule:
        assert integer >= json_int(rule["min"]), "integer below minimum"
    if "max" in rule:
        assert integer <= json_int(rule["max"]), "integer above maximum"
    return integer


def validate_float(value: Json, rule: Json) -> Json:
    assert json_kind(value) == "number", "expected number"
    number: float = json_float(value)
    if "min" in rule:
        assert number >= json_float(rule["min"]), "number below minimum"
    if "max" in rule:
        assert number <= json_float(rule["max"]), "number above maximum"
    return number


def convert(value: Json, rule: Json) -> Json:
    if json_kind(value) == "null":
        assert json_bool(json_get(rule, "nullable", False)), "null is not permitted"
        return None
    kind: str = text(rule, "kind", "string")
    if kind == "string":
        return validate_string(value, rule)
    if kind == "int":
        return validate_integer(value, rule)
    if kind == "float":
        return validate_float(value, rule)
    if kind == "bool":
        assert json_kind(value) == "bool", "expected boolean"
        return json_bool(value)
    assert kind == "timestamp", "unsupported field kind"
    assert json_kind(value) == "string", "expected timestamp string"
    stamp: DateTime = datetime_parse(json_string(value).strip())
    return datetime_iso(stamp)


def allowed(value: Json, rule: Json) -> bool:
    if "choices" not in rule:
        return True
    for option in json_array(rule["choices"]):
        if json_equal(option, value):
            return True
    return False


def clean_field(value: Json, rule: Json) -> Json:
    result: Json = None
    try:
        result = convert(value, rule)
    except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
        # Stable diagnostics across runtimes; exact parser exceptions vary.
        return {"ok": False, "reason": "invalid " + text(rule, "kind", "string") + " value"}
    if not allowed(result, rule):
        return {"ok": False, "reason": "value is not in choices"}
    return {"ok": True, "value": result}
