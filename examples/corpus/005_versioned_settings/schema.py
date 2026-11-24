"""Schema-listed, bounded values; strict types prevent bool/integer confusion."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_float,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_parse,
    json_string,
    read_text,
    regex_fullmatch,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_parse(env_get(name, str(default)), None))


def clock() -> float:
    value: str = env_get("SETTINGS_NOW", "")
    if value != "":
        return json_float(json_parse(value, None))
    return unix_time()


def validate_value(field: Json, value: Json) -> Json:
    kind: str = json_string(field["kind"])
    if kind == "bool":
        return json_bool(value)
    if kind == "int":
        number: int = json_int(value)
        assert number >= json_int(field["min"]) and number <= json_int(field["max"]), "integer outside range"
        return number
    if kind == "string" or kind == "choice":
        text: str = json_string(value)
        if kind == "string":
            assert len(text) <= json_int(field["max_length"]), "string exceeds character limit"
            pattern: str = json_string(field["pattern"])
            if pattern != "":
                assert regex_fullmatch(pattern, text), "string does not match pattern"
        else:
            assert text in json_array(field["choices"]), "unknown choice"
        return text
    assert kind == "strings", "unknown field kind"
    result: list[str] = []
    for item in json_array(value):
        text: str = json_string(item)
        assert len(text) > 0 and len(text) <= 128, "invalid list item length"
        assert text not in result, "duplicate list item"
        result.append(text)
    assert len(result) <= json_int(field["max_items"]), "too many list items"
    return result


def load_schema() -> list[Json]:
    content: str = read_text(env_get("SETTINGS_SCHEMA", "schema.json"))
    assert len(content.encode()) <= 65536, "schema exceeds byte limit"
    document: Json = json_loads(content)
    assert json_keys(document) == ["fields"], "invalid schema document"
    fields: list[Json] = json_array(document["fields"])
    assert len(fields) >= 1 and len(fields) <= 50, "invalid schema field count"
    seen: set[str] = set()
    for field in fields:
        name: str = json_string(field["name"])
        assert regex_fullmatch("[a-z][a-z0-9_]{0,47}", name), "invalid field name"
        assert name not in seen, "duplicate field name"
        seen.add(name)
        kind: str = json_string(field["kind"])
        keys: list[str] = json_keys(field)
        if kind == "bool":
            assert keys == ["default", "kind", "name"], "invalid boolean schema"
        elif kind == "int":
            assert keys == ["default", "kind", "max", "min", "name"], "invalid integer schema"
            assert json_int(field["min"]) <= json_int(field["max"]), "invalid integer bounds"
        elif kind == "string":
            assert keys == ["default", "kind", "max_length", "name", "pattern"], "invalid string schema"
            assert json_int(field["max_length"]) >= 0 and json_int(field["max_length"]) <= 4096, "invalid string bound"
            assert len(json_string(field["pattern"])) <= 256, "pattern too long"
        elif kind == "choice":
            assert keys == ["choices", "default", "kind", "name"], "invalid choice schema"
            choices: list[str] = []
            for value in json_array(field["choices"]):
                choice: str = json_string(value)
                assert len(choice) > 0 and len(choice) <= 128 and choice not in choices, "invalid choice"
                choices.append(choice)
            assert len(choices) > 0 and len(choices) <= 32, "invalid choice count"
        else:
            assert kind == "strings" and keys == ["default", "kind", "max_items", "name"], "invalid list schema"
            assert json_int(field["max_items"]) >= 0 and json_int(field["max_items"]) <= 32, "invalid list bound"
        validate_value(field, field["default"])
    assert setting("SETTINGS_PORT", 8771) >= 0 and setting("SETTINGS_PORT", 8771) <= 65535, "invalid port"
    assert setting("SETTINGS_HISTORY", 100) >= 1 and setting("SETTINGS_HISTORY", 100) <= 1000, "invalid history limit"
    assert clock() >= 0.0, "clock must be nonnegative"
    return fields


def defaults(fields: list[Json]) -> Json:
    values: Json = {}
    for field in fields:
        values[json_string(field["name"])] = validate_value(field, field["default"])
    return values


def validate_values(fields: list[Json], values: Json) -> None:
    assert json_keys(values) == json_keys(defaults(fields)), "unexpected settings fields"
    for field in fields:
        validate_value(field, values[json_string(field["name"])])
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def apply_changes(fields: list[Json], before: Json, changes: Json) -> Json:
    assert json_kind(changes) == "object", "changes must be an object"
    values: Json = {}
    for name in json_keys(before):
        values[name] = before[name]
    for name in json_keys(changes):
        assert name in before, "unknown settings field"
        for field in fields:
            if json_string(field["name"]) == name:
                values[name] = validate_value(field, changes[name])
    return values


def differences(before: Json, after: Json) -> list[str]:
    changed: list[str] = []
    for name in json_keys(after):
        if name not in before or not json_equal(before[name], after[name]):
            changed.append(name)
    return changed
