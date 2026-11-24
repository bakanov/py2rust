"""Explicit schema, ordered projection and unambiguous CSV null values."""

from py2rust.stdlib import (
    Json,
    int_from_decimal,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    regex_fullmatch,
)


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(names), "unexpected document fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def rules(config: Json) -> Json:
    columns: list[Json] = json_array(config["columns"])
    assert 1 <= len(columns) <= 64, "schema requires 1..64 columns"
    result: Json = {}
    for column in columns:
        fields(column, ["name", "type", "nullable"])
        name: str = json_string(column["name"])
        assert name != "" and len(name.encode()) <= 256 and "\x00" not in name, "invalid column name"
        assert name not in result, "duplicate schema column"
        assert json_string(column["type"]) in ["string", "integer", "number", "boolean", "json"], "invalid column type"
        json_bool(column["nullable"])
        result[name] = column
    return result


def selection(config: Json, columns: Json) -> list[str]:
    result: list[str] = []
    for item in json_array(config["select"]):
        name: str = json_string(item)
        assert name in columns and name not in result, "invalid selected column"
        result.append(name)
    assert len(result) > 0, "select at least one column"
    return result


def typed(value: Json, column: Json) -> Json:
    if value is None:
        assert json_bool(column["nullable"]), "null is not permitted"
        return None
    kind: str = json_string(column["type"])
    actual: str = json_kind(value)
    if kind == "string":
        assert actual == "string", "expected string"
    elif kind == "integer":
        json_int(value)
    elif kind == "number":
        assert actual == "number", "expected number"
    elif kind == "boolean":
        assert actual == "bool", "expected boolean"
    return value


def decode(cell: str, column: Json) -> Json:
    value: str = cell
    if value == "\\N":
        return typed(None, column)
    if value.startswith("\\\\"):
        value = value[1:]
    kind: str = json_string(column["type"])
    if kind == "string":
        return value
    if kind == "integer":
        return int_from_decimal(value)
    if kind == "number":
        assert regex_fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?", value.strip()), "expected JSON number"
    if kind == "boolean":
        assert value.strip() in ["true", "false"], "expected JSON boolean"
    return typed(json_loads(value), column)


def encode(value: Json, column: Json) -> str:
    if value is None:
        return "\\N"
    text: str = json_string(value) if json_string(column["type"]) == "string" else json_canonical(value)
    return "\\" + text if text.startswith("\\") else text
