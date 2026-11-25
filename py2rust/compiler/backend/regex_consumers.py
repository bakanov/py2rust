"""Omit capture spans only when a closed audit proves nobody observes them."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def groups_only(
    function: ast.FunctionDef, name: str, helpers: set[tuple[str, int]], declaration: ast.AST | None = None
) -> bool:
    parents = {id(child): node for node in ast.walk(function) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(function):
        if not isinstance(node, ast.Name) or node.id != name or node is declaration:
            continue
        if not isinstance(node.ctx, ast.Load):
            return False
        parent = parents.get(id(node))
        if (
            isinstance(parent, ast.Subscript)
            and parent.value is node
            and isinstance(parent.ctx, ast.Load)
            and isinstance(parent.slice, ast.Constant)
            and parent.slice.value == "groups"
        ):
            continue
        if (
            isinstance(parent, ast.Compare)
            and len(parent.ops) == 1
            and isinstance(parent.ops[0], (ast.Is, ast.IsNot))
            and any(
                isinstance(value, ast.Constant) and value.value is None for value in [parent.left, *parent.comparators]
            )
        ):
            continue
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and not parent.keywords:
            if all((parent.func.id, index) in helpers for index, value in enumerate(parent.args) if value is node):
                if node in parent.args:
                    continue
        return False
    return True


def prepare_regex_consumers(compiler: ServiceCompiler, functions: list[ast.FunctionDef]) -> None:
    if not compiler.optimize or not compiler.optimize_json_views or "regex_capture" not in compiler.imports:
        return
    # Only direct field consumers qualify as helpers. Recursive/unknown callees
    # keep the full representation; no optimistic fixed point is used.
    helpers = {
        (function.name, index)
        for function in functions
        for index, argument in enumerate(function.args.args)
        if groups_only(function, argument.arg, set())
    }
    for function in functions:
        for node in ast.walk(function):
            if not (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "regex_capture"
                and len(node.value.args) == 3
                and not node.value.keywords
                and groups_only(function, node.target.id, helpers, node.target)
            ):
                continue
            node.value.py2rust_regex_groups_only = True
    return
