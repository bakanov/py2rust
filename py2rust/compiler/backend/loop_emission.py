"""Host AST adapters; semantic decisions and Rust templates remain in explicit rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import (
    IterationUse,
    iteration_use,
)
from ..rules.iteration import (
    render_for,
    render_iteration,
    render_range,
    select_iteration,
)
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_for(compiler: ServiceCompiler, node: ast.For) -> str:
    compiler.check_name(node.target.id, node)
    before = compiler.locals.copy()
    borrowed_before = compiler.borrowed_parameters.copy()
    borrowed_str_before = compiler.borrowed_str_parameters.copy()
    item_borrowed = False
    if (
        isinstance(node.iter, ast.Call)
        and isinstance(node.iter.func, ast.Name)
        and node.iter.func.id == "range"
        and len(node.iter.args) in {1, 2, 3}
        and not node.iter.keywords
    ):
        args = [compiler.expr(a, Type("int")).code for a in node.iter.args]
        iterator = render_range(args)
        typ = Type("int")
    else:
        plan = iteration_use(node)
        if (
            compiler.optimize_iteration
            and isinstance(node.iter, ast.Name)
            and node.iter.id in compiler.locals
            and compiler.can_move_local(node.iter, compiler.locals[node.iter.id])
        ):
            plan = IterationUse("consume", False, "owned_source_dead_after_loop", node.iter.id)
        place = compiler.local_read(node.iter) if compiler.optimize_iteration and plan.mode == "borrow" else None
        if place is not None and place.type.name == "tuple":
            place = None
        value = place if place is not None else compiler.expr(node.iter)
        if value.type.name not in {"list", "set", "dict", "tuple", "tuple_var", "bytes", "bytearray", "str"}:
            compiler.error("for requires range, string, bytes, list, set, typed dictionary or homogeneous tuple", node)
        if value.type.name == "tuple" and (
            not value.type.args or any(item != value.type.args[0] for item in value.type.args)
        ):
            compiler.error("tuple iteration requires a nonempty tuple with homogeneous element types", node)
        if place is not None:
            mode, reason = "borrow", plan.reason
        elif plan.mode == "consume":
            mode, reason = "consume", plan.reason
        elif isinstance(node.iter, ast.Name) and node.iter.id in compiler.locals:
            mode = "snapshot"
            reason = plan.reason if plan.mode == "snapshot" else "owned_iteration_representation_required"
        else:
            mode, reason = "owned_result", "computed_owned_iteration_source"
        compiler.record_decision(node, "iteration", mode, reason)
        if value.type.name == "str":
            typ = Type("str")
        elif value.type.name in {"bytes", "bytearray"}:
            typ = Type("int")
        else:
            typ = value.type.args[0]
        rule = select_iteration(
            value.type.name, place is not None, typ.name in {"int", "float", "bool"}, plan.borrow_item
        )
        if not rule.key:
            compiler.error("unsupported iteration representation", node)
        item_borrowed = rule.borrowed_item
        iterator = render_iteration(rule, value.type.name, value.code, len(value.type.args))
    compiler.borrowed_str_parameters.discard(node.target.id)
    compiler.locals[node.target.id] = typ
    if item_borrowed:
        compiler.borrowed_parameters.add(node.target.id)
    else:
        compiler.borrowed_parameters.discard(node.target.id)
    body = "\n".join(compiler.block(node.body))
    compiler.locals = before
    compiler.borrowed_parameters = borrowed_before
    compiler.borrowed_str_parameters = borrowed_str_before
    binding = node.target.id if item_borrowed else compiler.binding(node.target.id)
    return render_for(binding, iterator, body)
