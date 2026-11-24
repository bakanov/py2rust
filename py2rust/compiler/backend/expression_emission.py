"""Dispatch checked source expression shapes to focused host adapters."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .access_emission import emit_attribute, emit_subscript
from .operator_emission import (
    emit_binary,
    emit_boolean,
    emit_comparison,
    emit_conditional,
    emit_unary,
)
from .value_emission import emit_literal, emit_mapping, emit_name, emit_sequence
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_expression(compiler: ServiceCompiler, node: ast.AST, expected: Type | None) -> Expr:
    if isinstance(node, ast.IfExp):
        return emit_conditional(compiler, node, expected)
    if isinstance(node, ast.Constant):
        return emit_literal(compiler, node, expected)
    if isinstance(node, ast.Name):
        return emit_name(compiler, node)
    if isinstance(node, (ast.List, ast.Set, ast.Tuple)):
        return emit_sequence(compiler, node, expected)
    if isinstance(node, ast.Dict):
        return emit_mapping(compiler, node, expected)
    if isinstance(node, ast.Attribute):
        return emit_attribute(compiler, node)
    if isinstance(node, ast.Subscript):
        return emit_subscript(compiler, node)
    if isinstance(node, ast.Call):
        return compiler.call(node, expected)
    if isinstance(node, ast.UnaryOp):
        return emit_unary(compiler, node)
    if isinstance(node, ast.BinOp):
        return emit_binary(compiler, node, expected)
    if isinstance(node, ast.Compare):
        return emit_comparison(compiler, node)
    if isinstance(node, ast.BoolOp):
        return emit_boolean(compiler, node)
    compiler.error(f"unsupported expression: {type(node).__name__}", node)
