"""Typed call validation and emission for scalar call operations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from ..rules.collections import (
    length_rule,
    render_length,
)
from ..rules.conversions import render_conversion, select_conversion
from ..rules.numeric import render_unary, select_unary_rule
from ..rust_text import quote
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_sequence_extreme(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.read_value(node.args[0])
    if value.type.name == "tuple" and value.type.args and all(item == value.type.args[0] for item in value.type.args):
        value = compiler.convert(value, Type("tuple_var", (value.type.args[0],)), node)
    if value.type.name not in {"list", "tuple_var"} or value.type.args[0].name not in {
        "int",
        "float",
        "str",
        "bool",
    }:
        compiler.error("one-argument min/max require a typed list or homogeneous tuple of ordered scalars", node)
    comparison = "<" if name == "min" else ">"
    # Borrow the collection and clone only the selected scalar. Strict
    # comparison keeps the first equal item, including signed float zero.
    return Expr(
        f"{{ let __values = {compiler.reference(value)}; let mut __items = __values.iter(); "
        f'let mut __best = __items.next().ok_or("{name}() arg is an empty sequence")?; '
        f"for __candidate in __items {{ if __candidate {comparison} __best {{ __best = __candidate; }} }} "
        "(*__best).clone() }",
        value.type.args[0],
    )


def emit_scalar_extreme(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    left = compiler.expr(node.args[0])
    right = compiler.expr(node.args[1], left.type)
    if left.type.name not in {"int", "float", "str", "bool"}:
        compiler.error("two-argument min/max require ordered scalar values", node)
    return Expr(f"({left.code}).{name}({right.code})", left.type)


def emit_ord(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if len(node.args) != 1:
        compiler.error("ord requires one string, bytes or bytearray argument", node)
    argument = node.args[0]
    if (
        compiler.optimize_text
        and isinstance(argument, ast.Subscript)
        and not isinstance(argument.slice, ast.Slice)
        and isinstance(argument.value, ast.Name)
        and argument.value.id in compiler.indexed_text
        and runtime_argument_use(RuntimeParameter("str", "shared"), [argument], 0).mode == "borrow"
    ):
        position = compiler.expr(argument.slice, Type("int"))
        return Expr(f"{compiler.text_index(argument.value.id)}.codepoint({position.code})?", Type("int"))
    value = compiler.read_value(node.args[0])
    if value.type.name not in {"str", "bytes", "bytearray"}:
        compiler.error("ord requires a string, bytes or bytearray", node)
    helper = "ord_text" if value.type.name == "str" else "ord_bytes"
    return Expr(f"rt::{helper}(&({value.code}))?", Type("int"))


def emit_length(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    argument = node.args[0]
    value = compiler.read_value(argument)
    local_name = argument.id if isinstance(argument, ast.Name) and argument.id in compiler.locals else ""
    rule = length_rule(value.type.name, local_name in compiler.indexed_text, local_name in compiler.cached_lengths)
    if not rule:
        compiler.error("len requires a string or collection", node)
    index = compiler.text_index(local_name) if rule == "length.text_index" else ""
    return Expr(render_length(rule, value.code, len(value.type.args), local_name, index), Type("int"))


def emit_conversion(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    value = compiler.expr(node.args[0])
    rule = select_conversion(name, value.type.name)
    if not rule.key:
        messages = {
            "float": "float conversion requires a string, int or float",
            "int": "int conversion requires a decimal string",
            "str": "str conversion supports str, int and float",
        }
        compiler.error(messages[name], node)
    if compiler.optimize and rule.form == "runtime_reference":
        use = runtime_argument_use(RuntimeParameter(value.type.name, "shared"), node.args, 0)
        place = compiler.argument_place(node.args[0], allow_place=use.mode == "borrow")
        if place is not None and place.type == value.type:
            value = place
    call = render_conversion(rule, value.code, compiler.reference(value))
    if compiler.collect_costs and rule.form in {"runtime_value", "runtime_reference"}:
        compiler.record_runtime_helper(node, rule.target)
    return Expr(
        call + ("?" if rule.fallible else ""),
        Type(rule.result),
        result_call=call if rule.fallible else None,
    )


def emit_abs(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    value = compiler.expr(node.args[0])
    rule = select_unary_rule("abs", value.type.name)
    if not rule.key:
        compiler.error("abs requires an int or float", node)
    return Expr(render_unary(rule, value.code), Type(rule.result))


def emit_print(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    values = [compiler.expr(a) for a in node.args]
    if any(v.type.name not in {"str", "int", "float", "bool", "Exception"} for v in values):
        compiler.error("use pretty for structured values", node)
    args = [
        (
            f'if {v.code} {{ "True" }} else {{ "False" }}'
            if v.type.name == "bool"
            else f"rt::float_to_string({v.code})?" if v.type.name == "float" else v.code
        )
        for v in values
    ]
    return Expr(
        f"println!({quote(' '.join('{}' for _ in values))}{', ' if args else ''}{', '.join(args)})",
        Type("None"),
    )
