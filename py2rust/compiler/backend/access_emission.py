"""Adapt record attributes and checked indexing/slicing.

Host AST adaptation only; portable semantic decisions live in rules/.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..library_contracts import LOG_LEVELS
from ..memory import RuntimeParameter, runtime_argument_use
from ..rules.access import (
    index_rule,
    render_index,
    render_sequence_slice,
    render_tuple_index,
    slice_rule,
)
from ..rules.records import runtime_field_type
from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_attribute(compiler: ServiceCompiler, node: ast.Attribute) -> Expr:
    if isinstance(node.value, ast.Name) and node.value.id in compiler.enums:
        if node.attr not in compiler.enums[node.value.id]:
            compiler.error("unknown enum member", node)
        return Expr(f"{node.value.id}::{node.attr}", Type(node.value.id))
    if (
        isinstance(node.value, ast.Name)
        and node.value.id == "logging"
        and "logging" in compiler.modules
        and node.attr in LOG_LEVELS
    ):
        return Expr(f"{LOG_LEVELS[node.attr]}i64", Type("int"))
    obj = compiler.expr(node.value)
    if obj.type.name == "WebRequest":
        field_type = runtime_field_type(obj.type.name, node.attr)
        if field_type:
            if isinstance(node.value, ast.Name):
                return Expr(f"{node.value.id}.{node.attr}.clone()", compiler.named_type(field_type))
            return Expr(f"({obj.code}).{node.attr}", compiler.named_type(field_type))
    if obj.type.name == "HttpResponse" and node.attr in {"body", "status"}:
        return Expr(
            f"({obj.code}).{node.attr}",
            Type("str" if node.attr == "body" else "int"),
        )
    if (obj.type.name == "WebResponse" and node.attr in {"status", "body", "headers"}) or (
        obj.type.name == "HttpReader" and node.attr in {"status", "headers"}
    ):
        receiver = node.value.id if isinstance(node.value, ast.Name) else f"({obj.code})"
        if node.attr == "status":
            return Expr(f"({receiver}.status as i64)", Type("int"))
        typ = Type("bytes") if node.attr == "body" else compiler.named_type("dict[str,str]")
        return Expr(f"{receiver}.{node.attr}.clone()", typ)
    if obj.type.name in compiler.records:
        fields = compiler.records[obj.type.name]
        if node.attr not in fields:
            compiler.error("unknown dataclass field: " + node.attr, node)
        receiver = node.value.id if isinstance(node.value, ast.Name) else f"({obj.code})"
        return Expr(f"{receiver}.{node.attr}.clone()", fields[node.attr][0])
    if obj.type.name in compiler.enums and node.attr in {"name", "value"}:
        values = compiler.enums[obj.type.name]
        arms = []
        for name, value in values.items():
            out = name if node.attr == "name" else value
            arms.append(
                f"{obj.type.name}::{name} => {quote(out) + '.to_string()' if isinstance(out, str) else str(out) + 'i64'}"
            )
        typ = Type("str" if node.attr == "name" or isinstance(next(iter(values.values())), str) else "int")
        return Expr(f"match {obj.code} {{ {', '.join(arms)} }}", typ)
    compiler.error("unsupported attribute", node)


def emit_subscript(compiler: ServiceCompiler, node: ast.Subscript) -> Expr:
    use = runtime_argument_use(RuntimeParameter("*", "shared"), [node], 0)
    obj = compiler.read_value(node.value) if use.mode == "borrow" else compiler.expr(node.value)
    if obj.type.name == "str" and isinstance(node.slice, ast.Slice):
        return compiler.string_slice(node, obj)
    if obj.type.name in {"str", "bytes", "bytearray", "list", "tuple_var"} and isinstance(node.slice, ast.Slice):
        if node.slice.step is not None:
            compiler.error("string/bytes/list slice steps are unsupported", node)
        start = compiler.expr(node.slice.lower, Type("int")).code if node.slice.lower else "0i64"
        end = compiler.expr(node.slice.upper, Type("int")).code if node.slice.upper else "i64::MAX"
        return Expr(render_sequence_slice(slice_rule(obj.type.name), compiler.reference(obj), start, end), obj.type)
    if obj.type.name == "tuple":
        if (
            not isinstance(node.slice, ast.Constant)
            or type(node.slice.value) is not int
            or not 0 <= node.slice.value < len(obj.type.args)
        ):
            compiler.error("tuple index must be a nonnegative constant in bounds", node)
        return Expr(render_tuple_index(obj.code, node.slice.value), obj.type.args[node.slice.value])
    key = compiler.expr(node.slice)
    prepared_text = isinstance(node.value, ast.Name) and node.value.id in compiler.indexed_text
    if obj.type.name == "Json":
        if key.type.name not in {"str", "int"}:
            compiler.error("JSON index must be str or int", node)
        result = Type("Json")
    elif obj.type.name == "dict":
        key = compiler.convert(key, obj.type.args[0], node)
        result = obj.type.args[1]
    else:
        key = compiler.convert(key, Type("int"), node)
        if obj.type.name == "str":
            result = Type("str")
        elif obj.type.name in {"bytes", "bytearray"}:
            result = Type("int")
        elif obj.type.name in {"list", "tuple_var"}:
            result = obj.type.args[0]
        else:
            compiler.error("unsupported indexed value", node)
    rule = index_rule(obj.type.name, key.type.name, prepared_text)
    source = compiler.reference(obj)
    if rule == "dictionary.value":
        source = obj.code
    elif rule == "text.indexed":
        source = compiler.text_index(node.value.id)
    return Expr(render_index(rule, source, key.code), result)
