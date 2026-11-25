"""Fuse pure string-key integer counter updates without allocating hit keys."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..rules.assignment import render_counter_update
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def integer_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return type(node.value) is int
    return (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, ast.USub)
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) is int
    )


def emit_counter_update(compiler: ServiceCompiler, node: ast.Assign) -> str | None:
    if not compiler.optimize:
        return None
    target, value = node.targets[0], node.value
    if not (
        isinstance(target, ast.Subscript)
        and isinstance(target.value, ast.Name)
        and isinstance(target.slice, ast.Name)
        and isinstance(value, ast.BinOp)
        and isinstance(value.op, ast.Add)
        and integer_literal(value.right)
    ):
        return None
    name, key = target.value.id, target.slice.id
    if compiler.locals.get(name) != Type("dict", (Type("str"), Type("int"))) or compiler.locals.get(key) != Type("str"):
        return None
    call = value.left
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == name
        and call.func.attr == "get"
        and len(call.args) == 2
        and not call.keywords
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == key
        and integer_literal(call.args[1])
    ):
        return None
    default = compiler.expr(call.args[1], Type("int"))
    increment = compiler.expr(value.right, Type("int"))
    borrowed = compiler.read_value(target.slice)
    compiler.record_decision(node, "dictionary_counter", "borrow_key", "pure_checked_update_allocates_only_on_miss")
    return render_counter_update(name, compiler.reference(borrowed), default.code, increment.code)
