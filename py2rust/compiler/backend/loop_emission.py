"""Host AST adapters; semantic decisions and Rust templates remain in explicit rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import (
    IterationUse,
    binding_write_reasons,
    iteration_use,
)
from ..rules.iteration import (
    render_for,
    render_iteration,
    render_range,
    select_iteration,
)
from .values import Expr, Type
from .split_emission import split_iterator, split_operands

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_for(compiler: ServiceCompiler, node: ast.For) -> str:
    from .borrowed_maps import begin_borrowed_maps, finish_borrowed_maps
    from .projection_cache import prepare_scan_caches

    projection_caches_before = compiler.projection_caches.copy()
    scan_caches_before = compiler.scan_caches.copy()
    map_positions_before = compiler.map_positions.copy()
    growing_sets_before = compiler.growing_sets.copy()
    if isinstance(node.target, ast.Tuple):
        for element in node.target.elts:
            if not isinstance(element, ast.Name):
                compiler.error("loop tuple targets must be simple names", element)
            compiler.check_name(element.id, element)
    else:
        compiler.check_name(node.target.id, node)
    before = compiler.locals.copy()
    borrowed_map_loops_before = compiler.borrowed_map_loops.copy()
    borrowed_maps = begin_borrowed_maps(compiler, node)
    borrowed_before = compiler.borrowed_parameters.copy()
    integer_views_before = compiler.integer_views.copy()
    borrowed_str_before = compiler.borrowed_str_parameters.copy()
    item_borrowed = False
    byte_iteration = False
    split_setup = prepare_scan_caches(compiler, node)
    split = split_operands(compiler, node.iter, snapshot=True) if compiler.optimize_iteration else None
    if split is not None:
        source, separator = split
        split_setup += f"let __split_source = {source.code};\n"
        source = Expr("__split_source", Type("str"))
        if separator is not None:
            split_setup += f"let __split_separator = {separator.code};\n"
            separator = Expr("__split_separator", Type("str"))
        iterator = split_iterator(compiler, source, separator)
        typ = Type("str")
        writes = binding_write_reasons(ast.Module(body=node.body, type_ignores=[]), {node.target.id})
        item_borrowed = node.target.id not in writes
        if not item_borrowed:
            iterator = f"({iterator}).map(str::to_owned)"
        compiler.record_decision(
            node,
            "split_consumer",
            "borrow_items" if item_borrowed else "owned_items",
            "snapshot_backing_preserves_loop_input",
        )
    elif (
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
            and id(node) not in compiler.scan_caches
            and id(node) not in compiler.borrowed_map_loops
            and isinstance(node.iter, ast.Name)
            and node.iter.id in compiler.locals
            and compiler.can_move_local(node.iter, compiler.locals[node.iter.id])
        ):
            plan = IterationUse("consume", False, "owned_source_dead_after_loop", node.iter.id)
        place = compiler.local_read(node.iter) if compiler.optimize_iteration and plan.mode == "borrow" else None
        if place is not None and place.type.name == "tuple":
            place = None
        value = place if place is not None else compiler.expr(node.iter)
        if value.type.name == "Json" or value.type.name == "optional" and value.type.args[0].name == "Json":
            value = compiler.convert(value, Type("list", (Type("Json"),)), node)
        if value.type.name == "optional" and value.type.args[0].name in {
            "list",
            "set",
            "dict",
            "tuple",
            "tuple_var",
            "bytes",
            "bytearray",
            "str",
        }:
            value = compiler.convert(value, value.type.args[0], node)
        if value.type.name not in {"list", "set", "dict", "tuple", "tuple_var", "bytes", "bytearray", "str"}:
            compiler.error("for requires range, string, bytes, list, set, typed dictionary or homogeneous tuple", node)
        if value.type.name == "tuple" and (
            not value.type.args or any(item != value.type.args[0] for item in value.type.args)
        ):
            compiler.error(
                f"tuple iteration requires a nonempty tuple with homogeneous element types at "
                f"{getattr(node, 'source_path', '<unknown>')}:{node.lineno}",
                node,
            )
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
        byte_iteration = value.type.name in {"bytes", "bytearray"} and isinstance(node.iter, ast.Name)
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
    targets = node.target.elts if isinstance(node.target, ast.Tuple) else [node.target]
    target_types = typ.args if isinstance(node.target, ast.Tuple) and typ.name == "tuple" else [typ]
    if len(targets) != len(target_types):
        compiler.error("loop tuple target does not match the item type", node.target)
    for target, target_type in zip(targets, target_types):
        compiler.borrowed_str_parameters.discard(target.id)
        if split is not None and item_borrowed:
            compiler.borrowed_str_parameters.add(target.id)
        compiler.locals[target.id] = target_type
        if item_borrowed:
            compiler.borrowed_parameters.add(target.id)
        else:
            compiler.borrowed_parameters.discard(target.id)
    if compiler.optimize and byte_iteration:
        from .lookup_views import integer_lookup_views

        split_setup += integer_lookup_views(compiler, node)
    body = "\n".join(compiler.block(node.body))
    compiler.locals = before
    compiler.borrowed_parameters = borrowed_before
    compiler.integer_views = integer_views_before
    compiler.borrowed_str_parameters = borrowed_str_before
    binding = (
        ("(" + ", ".join("_" if item.id == "_" else "mut " + item.id for item in node.target.elts) + ",)")
        if isinstance(node.target, ast.Tuple) and all(isinstance(item, ast.Name) for item in node.target.elts)
        else (
            ast.unparse(node.target)
            if isinstance(node.target, ast.Tuple)
            else ("_" if node.target.id == "_" else f"mut {node.target.id}")
        )
    )
    scan = compiler.scan_caches.get(id(node))
    if scan is not None and item_borrowed:
        index, caches = scan
        for cache, initializer in caches:
            split_setup += f"{cache}.resize_with({node.iter.id}.len(), {initializer});\n"
        binding = f"({index}, {binding})"
        iterator = f"({iterator}).enumerate()"
    compiler.projection_caches = projection_caches_before
    compiler.scan_caches = scan_caches_before
    compiler.map_positions = map_positions_before
    compiler.growing_sets = growing_sets_before
    compiler.borrowed_map_loops = borrowed_map_loops_before
    rendered = render_for(binding, iterator, body)
    rendered = "{\n" + split_setup + rendered + "\n}" if split_setup else rendered
    return finish_borrowed_maps(borrowed_maps, rendered)
