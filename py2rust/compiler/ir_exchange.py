"""Host adapters between immutable typed IR and the native wire representation.

Only this adapter uses Python dataclass reflection. The schema and graph checks
live in native.ir_schema and compile as production Python-subset source.
"""

from __future__ import annotations

import math
from dataclasses import fields

from py2rust.stdlib import Json

from . import ir
from .native.ir_schema import node_schema, validate_document

_CLASSES = {
    cls.__name__: cls
    for cls in (
        ir.Source,
        ir.ValueType,
        ir.Expression,
        ir.Handler,
        ir.Statement,
        ir.Parameter,
        ir.Function,
        ir.Field,
        ir.Record,
        ir.Enum,
        ir.Module,
    )
}


def encode_literal(value: str | bytes | int | float | bool | None) -> dict[str, str]:  # noqa: PYI041
    if value is None:
        return {"kind": "none", "text": ""}
    if type(value) is bytes:
        return {"kind": "bytes", "text": value.hex()}
    if type(value) is str:
        return {"kind": "str", "text": value}
    if type(value) is float and not math.isfinite(value):
        raise ValueError("nonfinite IR literal")
    if type(value) in {int, float, bool}:
        return {"kind": type(value).__name__, "text": repr(value)}
    raise ValueError("unsupported IR literal")


def decode_literal(value: Json) -> str | bytes | int | float | bool | None:
    kind, text = value["kind"], value["text"]
    if kind == "none":
        return None
    if kind == "str":
        return text
    if kind == "bytes":
        return bytes.fromhex(text)
    if kind == "bool":
        return text == "True"
    if kind == "int":
        return int(text)
    if kind == "float":
        result = float(text)
        if not math.isfinite(result):
            raise ValueError("nonfinite IR literal")
        return result
    raise ValueError("unsupported IR literal")


def to_document(modules: tuple[ir.Module, ...], entry: str) -> Json:
    """Encode every IR field losslessly; references always precede their users."""
    nodes: list[Json] = []

    def visit(node) -> int:
        kind = type(node).__name__
        if kind not in _CLASSES or type(node) is not _CLASSES[kind]:
            raise ValueError("not a compiler IR node")
        schema = node_schema(kind)
        if set(schema) != {field.name for field in fields(node)}:
            raise ValueError("IR schema is out of date: " + kind)
        row: Json = {"kind": kind}
        for name, shape in schema.items():
            value = getattr(node, name)
            if shape.startswith(("ref:", "optional:")):
                row[name] = None if value is None else visit(value)
            elif shape.startswith("list:"):
                row[name] = [visit(item) for item in value]
            elif shape == "blocks":
                row[name] = [[visit(item) for item in block] for block in value]
            elif shape == "members":
                row[name] = [[name, visit(expression)] for name, expression in value]
            elif shape == "literal":
                row[name] = encode_literal(value)
            elif shape == "texts":
                row[name] = list(value)
            else:
                row[name] = value
        nodes.append(row)
        return len(nodes) - 1

    roots = [visit(module) for module in modules]
    document: Json = {"format": 1, "entry": entry, "nodes": nodes, "modules": roots}
    validate_document(document)
    return document


def from_document(document: Json) -> tuple[tuple[ir.Module, ...], str]:
    """Decode a validated document without evaluating code or importing classes."""
    validate_document(document)
    nodes = []
    for row in document["nodes"]:
        kind = row["kind"]
        values = {}
        for name, shape in node_schema(kind).items():
            value = row[name]
            if shape.startswith(("ref:", "optional:")):
                values[name] = None if value is None else nodes[value]
            elif shape.startswith("list:"):
                values[name] = tuple(nodes[index] for index in value)
            elif shape == "blocks":
                values[name] = tuple(tuple(nodes[index] for index in block) for block in value)
            elif shape == "members":
                values[name] = tuple((name, nodes[index]) for name, index in value)
            elif shape == "literal":
                values[name] = decode_literal(value)
            elif shape == "texts":
                values[name] = tuple(value)
            else:
                values[name] = value
        nodes.append(_CLASSES[kind](**values))
    return tuple(nodes[index] for index in document["modules"]), document["entry"]
