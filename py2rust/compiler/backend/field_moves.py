"""Conservative owned-field extraction for the current host emitter.

Only straight-line extraction/restoration regions are admitted. Reads of an old
collection's length can use a scalar snapshot; other reads retain owned copying.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


@dataclass(frozen=True)
class FieldMove:
    owner: str
    field: str
    length_calls: tuple[ast.Call, ...]
    length_name: str


def field_path(node: ast.AST, owner: str, field: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == owner
        and node.attr == field
    )


def prepare_field_moves(compiler: ServiceCompiler, function: ast.FunctionDef) -> None:
    compiler.field_moves = {}
    compiler.field_length_reads = {}
    if not compiler.optimize:
        return
    # A handler could observe a partially moved record after an intermediate error.
    if any(isinstance(n, (ast.Try, ast.With)) for n in ast.walk(function)):
        return
    for position, statement in enumerate(function.body):
        if not (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and isinstance(statement.value, ast.Attribute)
            and isinstance(statement.value.value, ast.Name)
        ):
            continue
        owner, field = statement.value.value.id, statement.value.attr
        owner_type = compiler.locals.get(owner)
        if owner_type is None or owner_type.name not in compiler.records or owner in compiler.borrowed_parameters:
            continue
        if not compiler.move_safe_type(owner_type):
            continue
        if owner_type.name in compiler.shared_records:
            continue  # A shared record cannot partially move out of its dereferenced storage.
        typ = compiler.records[owner_type.name].get(field)
        if typ is None or typ[0].name not in {"list", "dict", "set", "bytes", "bytearray", "str", "tuple_var"}:
            continue
        declared = getattr(statement, "py2rust_representation_type", None) or compiler.typ(statement.annotation)
        if declared != typ[0]:
            continue
        region = []
        restored = False
        for following in function.body[position + 1 :]:
            if (
                isinstance(following, ast.Assign)
                and len(following.targets) == 1
                and field_path(following.targets[0], owner, field)
                and isinstance(following.value, ast.Name)
                and following.value.id == statement.target.id
            ):
                restored = True
                break
            region.append(following)
        if not restored:
            continue
        roots = [node for item in region for node in ast.walk(item)]
        if any(isinstance(n, (ast.Return, ast.Break, ast.Continue, ast.Raise, ast.For, ast.While)) for n in roots):
            continue
        parents = {id(child): parent for parent in roots for child in ast.iter_child_nodes(parent)}
        valid = True
        lengths = []
        for node in roots:
            if not isinstance(node, ast.Name) or node.id != owner:
                continue
            parent = parents.get(id(node))
            if not isinstance(node.ctx, ast.Load) or not isinstance(parent, ast.Attribute) or parent.value is not node:
                valid = False
                break
            if parent.attr != field:
                continue
            call = parents.get(id(parent))
            if (
                isinstance(parent.ctx, ast.Load)
                and isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "len"
                and "len" not in compiler.functions
                and "len" not in compiler.imports
                and call.args == [parent]
                and not call.keywords
            ):
                lengths.append(call)
            else:
                valid = False
                break
        if not valid:
            continue
        length_name = "__field_length_" + statement.target.id
        plan = FieldMove(owner, field, tuple(lengths), length_name)
        compiler.field_moves[id(statement)] = plan
        compiler.field_length_reads.update({id(call): length_name for call in lengths})
    return


def emit_field_move(compiler: ServiceCompiler, node: ast.AnnAssign, typ: Type) -> str | None:
    plan = compiler.field_moves.get(id(node))
    if plan is None:
        return None
    owner_type = compiler.locals[plan.owner]
    if compiler.records[owner_type.name][plan.field][0] != typ:
        return None
    prefix = ""
    if plan.length_calls:
        # Generate the original typed len before extraction, without redirecting
        # that one evaluation to the snapshot we are declaring.
        call = plan.length_calls[0]
        saved = compiler.field_length_reads.pop(id(call))
        try:
            length = compiler.expr(call, Type("int"))
        finally:
            compiler.field_length_reads[id(call)] = saved
        prefix = f"let {plan.length_name}: i64 = {length.code}; "
    name = node.target.id
    compiler.locals[name] = typ
    compiler.record_decision(node, "record_field", "move", "owned_field_restored_without_old_value_observers")
    return prefix + f"let {compiler.binding(name)}: {typ.rust()} = {plan.owner}.{plan.field};"
