"""Reject invalid schema rules before processing any input records."""

from fields import clean_field, convert, text

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_float,
    json_get,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
)


def load_schema() -> Json:
    return json_loads(read_text(env_get("CLEAN_SCHEMA", "schema.json")))


def validate_schema(schema: Json) -> None:
    assert json_kind(schema) == "object", "schema must be an object"
    assert text(schema, "unknown", "reject") in ["reject", "drop", "preserve"], "invalid unknown-field policy"
    rules: list[Json] = json_array(schema["fields"])
    assert len(rules) > 0 and len(rules) <= 100, "expected 1–100 field rules"
    names: set[str] = set()
    for rule in rules:
        name: str = text(rule, "name", "")
        assert len(name) > 0 and len(name) <= 100, "invalid field name"
        assert name not in names, "duplicate field name"
        names.add(name)
        kind: str = text(rule, "kind", "string")
        assert kind in ["string", "int", "float", "bool", "timestamp"], "unsupported field kind"
        allowed_keys: list[str] = ["name", "kind", "required", "nullable", "default", "choices"]
        if kind == "string":
            allowed_keys.extend(["trim", "case", "min_length", "max_length", "pattern"])
        if kind == "int" or kind == "float":
            allowed_keys.extend(["min", "max"])
        for key in json_keys(rule):
            assert key in allowed_keys, "unsupported constraint for field kind"
        json_bool(json_get(rule, "required", True))
        json_bool(json_get(rule, "nullable", False))
        json_bool(json_get(rule, "trim", True))
        assert text(rule, "case", "preserve") in ["preserve", "lower", "upper"], "invalid case policy"
        lower: int = json_int(json_get(rule, "min_length", 0))
        upper: int = json_int(json_get(rule, "max_length", 100000))
        assert lower >= 0 and lower <= upper, "invalid string length bounds"
        for bound in ["min", "max"]:
            if bound in rule:
                if kind == "int":
                    json_int(rule[bound])
                else:
                    json_float(rule[bound])
        if "min" in rule and "max" in rule:
            if kind == "int":
                assert json_int(rule["min"]) <= json_int(rule["max"]), "reversed integer bounds"
            else:
                assert json_float(rule["min"]) <= json_float(rule["max"]), "reversed numeric bounds"
        if "pattern" in rule:
            regex_fullmatch(json_string(rule["pattern"]), "")
        if "choices" in rule:
            options: list[Json] = json_array(rule["choices"])
            assert len(options) > 0, "choices cannot be empty"
            for option in options:
                assert json_equal(convert(option, rule), option), "choices must already be normalized"
        if "default" in rule:
            result: Json = clean_field(rule["default"], rule)
            assert json_bool(result["ok"]), "default violates its field rule"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
