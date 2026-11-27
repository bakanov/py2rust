"""Typed call validation and emission for constructor operations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..rules.collections import (
    render_sequence_constructor,
    sequence_constructor_rule,
)
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_bytes_constructor(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    if len(node.args) > 1:
        compiler.error("byte constructors accept zero or one argument", node)
    if not node.args:
        return Expr("Vec::<u8>::new()", Type(name))
    value = (
        compiler.expr(node.args[0], compiler.named_type("list[int]"))
        if isinstance(node.args[0], ast.List)
        else compiler.read_value(node.args[0])
    )
    if value.type.name == "int":
        code = f"rt::byte_buffer_new({value.code})?"
    elif value.type.name in {"bytes", "bytearray"}:
        code = f"rt::byte_buffer_copy({compiler.reference(value)})?"
    elif value.type == compiler.named_type("list[int]"):
        code = f"rt::byte_buffer_from_ints({compiler.reference(value)})?"
    else:
        compiler.error("byte constructors require an integer length, byte buffer or list[int]", node)
    return Expr(code, Type(name))


def emit_hex_constructor(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.expr(node.args[0], Type("str"))
    code = f"rt::bytes_from_hex(&({value.code}))?"
    if name == "bytearray.fromhex":
        code = f"rt::byte_buffer_checked({code})?"
    return Expr(code, Type(name.split(".")[0]))


def emit_sequence_constructor(
    compiler: ServiceCompiler, node: ast.Call, name: str, expected: Type | None = None
) -> Expr:
    source_type = Type("list", expected.args) if expected is not None and expected.args else None
    value = (
        compiler.expr(node.args[0], source_type)
        if source_type is not None
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "__comprehend"
        else compiler.read_value(node.args[0])
    )
    if value.type.name == "tuple" and value.type.args and all(item == value.type.args[0] for item in value.type.args):
        value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
    rule = sequence_constructor_rule(value.type.name)
    if not rule:
        compiler.error("list/tuple(value) requires a typed dictionary, list, set or variadic tuple", node)
    element = Type("int") if rule == "sequence.byte_values" else value.type.args[0]
    return Expr(
        render_sequence_constructor(rule, value.code),
        Type("tuple_var" if name == "tuple" else "list", (element,)),
    )


def emit_set_constructor(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    value = compiler.expr(node.args[0])
    if value.type.name == "dict":
        value = Expr(
            f"({value.code}).keys().cloned().collect::<Vec<_>>()",
            Type("list", (value.type.args[0],)),
        )
    if value.type.name == "Json" or value.type.name == "optional" and value.type.args[0].name == "Json":
        value = compiler.convert(value, Type("list", (Type("Json"),)), node)
    if value.type.name == "tuple" and value.type.args and all(item == value.type.args[0] for item in value.type.args):
        value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
    if value.type.name not in {"list", "set", "tuple_var"} or not compiler.hashable(value.type.args[0]):
        compiler.error(f"set(value) requires a typed collection of hashable values, got {value.type}", node)
    return Expr(
        f"({value.code}).into_iter().collect::<std::collections::BTreeSet<_>>()",
        Type("set", value.type.args),
    )


def emit_empty_constructor(compiler: ServiceCompiler, node: ast.Call, name: str, expected: Type | None) -> Expr:
    name = "set" if name == "frozenset" else name
    if expected is None or expected.name != ("tuple_var" if name == "tuple" else name):
        compiler.error("empty collection constructor requires a matching type annotation", node)
    constructor = {
        "set": "std::collections::BTreeSet",
        "list": "Vec",
        "tuple": "Vec",
        "dict": "indexmap::IndexMap",
    }[name]
    return Expr(f"{constructor}::new()", expected)
