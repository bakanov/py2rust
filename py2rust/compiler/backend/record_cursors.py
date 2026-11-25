"""Borrow read-only traversal cursors rooted in borrowed record parameters."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, place_root, runtime_argument_use
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def prepare_record_cursors(compiler: ServiceCompiler, function: ast.FunctionDef) -> None:
    compiler.record_cursors = {}
    compiler.record_cursor_steps = {}
    if not compiler.optimize:
        return
    nodes = list(ast.walk(function))
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    for declaration in function.body:
        if not (
            isinstance(declaration, ast.AnnAssign)
            and isinstance(declaration.target, ast.Name)
            and isinstance(declaration.value, ast.Name)
            and declaration.value.id in compiler.borrowed_parameters
        ):
            continue
        owner = declaration.value.id
        typ = compiler.locals.get(owner)
        if typ is None or typ.name not in compiler.records or not compiler.move_safe_type(typ):
            continue
        declared = getattr(declaration, "py2rust_representation_type", None) or compiler.typ(declaration.annotation)
        if declared != typ:
            continue
        name = declaration.target.id
        steps = []
        valid = True
        for node in nodes:
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and place_root(node.func.value) == name
            ):
                # Mutating methods can be hidden behind several field/index projections.
                valid = False
                break
            if (
                isinstance(node, (ast.Attribute, ast.Subscript))
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and place_root(node) == name
            ):
                valid = False
                break
            if not isinstance(node, ast.Name) or node.id != name or not isinstance(node.ctx, (ast.Store, ast.Del)):
                continue
            if node is declaration.target:
                continue
            parent = parents.get(id(node))
            if not (
                isinstance(parent, ast.Assign)
                and len(parent.targets) == 1
                and parent.targets[0] is node
                and isinstance(parent.value, (ast.Attribute, ast.Subscript))
                and place_root(parent.value) == name
                and runtime_argument_use(RuntimeParameter("*", "shared"), [parent.value], 0).mode == "borrow"
            ):
                valid = False
                break
            steps.append(parent)
        if valid and steps:
            compiler.record_cursors[id(declaration)] = owner
            compiler.record_cursor_steps.update({id(step): name for step in steps})
    return


def bind_record_cursor(compiler: ServiceCompiler, node: ast.AnnAssign, typ: Type) -> str | None:
    owner = compiler.record_cursors.get(id(node))
    if owner is None:
        return None
    compiler.locals[node.target.id] = typ
    compiler.borrowed_parameters.add(node.target.id)
    compiler.record_decision(node, "record_cursor", "borrow", "readonly_descents_from_borrowed_record")
    return f"let {compiler.binding(node.target.id)}: &{typ.rust()} = {owner};"


def advance_record_cursor(compiler: ServiceCompiler, node: ast.Assign) -> str | None:
    name = compiler.record_cursor_steps.get(id(node))
    if name is None:
        return None
    value = compiler.local_read(node.value)
    if value is None or value.type != compiler.locals[name]:
        compiler.error("record cursor descent requires a checked projection of the same record type", node)
    return f"{name} = {compiler.reference(value)};"
