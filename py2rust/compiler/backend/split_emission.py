"""Fuse immediate string-split consumers without materializing a Python list.

Only immediate consumers qualify: stored lists keep their independent owned
representation. Loop sources are snapshotted before the body can rebind them.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def split_operands(
    compiler: ServiceCompiler, node: ast.AST, *, snapshot: bool = False
) -> tuple[Expr, Expr | None] | None:
    if not compiler.optimize or not compiler.optimize_text:
        return None
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "split"
        and len(node.args) <= 1
        and not node.keywords
    ):
        return None
    arguments = [node.func.value, *node.args]
    use = runtime_argument_use(RuntimeParameter("str", "shared"), arguments, 0)
    source = compiler.expr(arguments[0]) if snapshot or use.mode != "borrow" else compiler.read_value(arguments[0])
    if source.type.name != "str":
        return None
    separator = None
    if node.args:
        literal = (
            compiler.argument_place(node.args[0])
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
            else None
        )
        separator = (
            literal
            if literal is not None
            else (compiler.expr(node.args[0], Type("str")) if snapshot else compiler.read_value(node.args[0]))
        )
        if separator.type.name != "str":
            return None
    return source, separator


def split_iterator(compiler: ServiceCompiler, source: Expr, separator: Expr | None) -> str:
    if separator is None:
        return f"rt::str_split_whitespace_iter({compiler.reference(source)})"
    return f"rt::str_split_iter({compiler.reference(source)}, {compiler.reference(separator)})?"


def split_consumer(compiler: ServiceCompiler, node: ast.AST, index: int | None = None) -> Expr | None:
    operands = split_operands(compiler, node)
    if operands is None:
        return None
    iterator = split_iterator(compiler, *operands)
    compiler.record_decision(
        node, "split_consumer", "count" if index is None else "index", "temporary_list_does_not_escape"
    )
    if index is None:
        source, separator = operands
        if separator is not None:
            return Expr(
                f"rt::str_split_count({compiler.reference(source)}, {compiler.reference(separator)})?", Type("int")
            )
        return Expr(f"({iterator}).count() as i64", Type("int"))
    # End iterator/Result temporary lifetimes before a surrounding tail-return
    # expression can drop the local string backing the iterator (Rust 2021).
    return Expr(f"{{ let __split_result = rt::split_item({iterator}, {index}i64)?; __split_result }}", Type("str"))
