"""Version-one compiler-owned IR wire schema, portable to native Rust.

Rows form a topologically ordered graph. Every reference points to an earlier
row of the declared kind: malformed input cannot introduce cycles or forward
references. Named fields retain the meaning of the production typed IR.
"""

# ruff: noqa: PLC0206, FURB188 -- explicit subset loops and string operations

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_is_null,
    json_keys,
    json_string,
)


def node_schema(kind: str) -> dict[str, str]:
    if kind == "Source":
        return {"path": "text", "line": "integer", "column": "integer"}
    if kind == "ValueType":
        return {"name": "text", "arguments": "list:ValueType"}
    if kind == "Expression":
        return {
            "operation": "text",
            "type": "ref:ValueType",
            "source": "ref:Source",
            "operands": "list:Expression",
            "value": "literal",
            "operators": "texts",
        }
    if kind == "Handler":
        return {"exception": "text", "binding": "optional_text", "body": "list:Statement", "source": "ref:Source"}
    if kind == "Statement":
        return {
            "operation": "text",
            "source": "ref:Source",
            "expressions": "list:Expression",
            "blocks": "blocks",
            "target": "optional_text",
            "target_type": "optional:ValueType",
            "handlers": "list:Handler",
            "declaration": "boolean",
        }
    if kind == "Parameter":
        return {"name": "text", "type": "ref:ValueType"}
    if kind == "Function":
        return {
            "name": "text",
            "parameters": "list:Parameter",
            "result": "ref:ValueType",
            "body": "list:Statement",
            "source": "ref:Source",
        }
    if kind == "Field":
        return {"name": "text", "type": "ref:ValueType", "source": "ref:Source", "default": "optional:Expression"}
    if kind == "Record":
        return {"name": "text", "fields": "list:Field", "source": "ref:Source"}
    if kind == "Enum":
        return {"name": "text", "members": "members", "source": "ref:Source"}
    if kind == "Module":
        return {
            "name": "text",
            "functions": "list:Function",
            "body": "list:Statement",
            "records": "list:Record",
            "enums": "list:Enum",
        }
    assert False, "unknown IR node kind"
    return {}


def check_reference(value: Json, kind: str, kinds: list[str]) -> None:
    index: int = json_int(value)
    assert index >= 0 and index < len(kinds), "IR reference must point to an earlier row"
    assert kinds[index] == kind, "IR reference kind mismatch"
    return


def check_field(value: Json, shape: str, kinds: list[str]) -> None:
    if shape == "text" or shape == "optional_text":
        if shape != "optional_text" or not json_is_null(value):
            json_string(value)
    elif shape == "integer":
        number: int = json_int(value)
        assert number >= 0, "negative source position"
    elif shape == "boolean":
        json_bool(value)
    elif shape == "texts":
        for item in json_array(value):
            json_string(item)
    elif shape.startswith("ref:"):
        check_reference(value, shape[4:], kinds)
    elif shape.startswith("optional:"):
        if not json_is_null(value):
            check_reference(value, shape[9:], kinds)
    elif shape.startswith("list:"):
        for reference in json_array(value):
            check_reference(reference, shape[5:], kinds)
    elif shape == "blocks":
        for block in json_array(value):
            for statement in json_array(block):
                check_reference(statement, "Statement", kinds)
    elif shape == "members":
        for member in json_array(value):
            pair: list[Json] = json_array(member)
            assert len(pair) == 2, "IR enum member must be a name/value pair"
            json_string(pair[0])
            check_reference(pair[1], "Expression", kinds)
    elif shape == "literal":
        keys: list[str] = json_keys(value)
        assert len(keys) == 2 and "kind" in keys and "text" in keys, "invalid IR literal fields"
        tag: str = json_string(value["kind"])
        spelling: str = json_string(value["text"])
        assert tag in ["none", "str", "bytes", "int", "float", "bool"], "invalid IR literal tag"
        if tag == "none":
            assert spelling == "", "invalid None literal"
        if tag == "bool":
            assert spelling == "True" or spelling == "False", "invalid bool literal"
        if tag == "int":
            decimal: str = spelling
            if decimal.startswith("-"):
                decimal = decimal[1:]
            assert decimal != "", "empty integer literal"
            for integer_digit in decimal:
                assert integer_digit in "0123456789", "invalid integer literal"
        if tag == "float":
            floating: float = float(spelling)
            assert floating >= -1.7976931348623157e308 and floating <= 1.7976931348623157e308, "nonfinite float literal"
        if tag == "bytes":
            assert len(spelling) % 2 == 0, "odd byte literal length"
            for digit in spelling:
                assert digit in "0123456789abcdef", "invalid byte literal"
    else:
        assert False, "unknown IR field shape"
    return


def validate_document(document: Json) -> list[str]:
    keys: list[str] = json_keys(document)
    assert len(keys) == 4, "invalid IR envelope fields"
    assert "format" in keys and "entry" in keys and "nodes" in keys and "modules" in keys, "missing IR envelope fields"
    assert json_int(document["format"]) == 1, "unsupported IR format version"
    entry: str = json_string(document["entry"])
    assert entry != "", "empty IR entry module"
    nodes: list[Json] = json_array(document["nodes"])
    kinds: list[str] = []
    for node in nodes:
        kind: str = json_string(node["kind"])
        schema: dict[str, str] = node_schema(kind)
        fields: list[str] = json_keys(node)
        assert len(fields) == len(schema) + 1, "invalid IR node fields"
        for field in schema:
            assert field in fields, "missing IR field"
            check_field(node[field], schema[field], kinds)
        kinds.append(kind)
    modules: list[str] = []
    for root in json_array(document["modules"]):
        check_reference(root, "Module", kinds)
        index: int = json_int(root)
        name: str = json_string(nodes[index]["name"])
        assert name not in modules, "duplicate IR module name"
        modules.append(name)
    assert entry in modules, "IR entry module is absent"
    return modules
