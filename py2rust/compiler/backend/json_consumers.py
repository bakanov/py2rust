"""Immediate JSON collection consumers retain validation without temporary lists."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def projection_source(compiler: ServiceCompiler, node: ast.AST, names: set[str]) -> tuple[str, Expr] | None:
    if not compiler.optimize or not compiler.optimize_json_views:
        return None
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in names
        and node.func.id in compiler.imports
        and len(node.args) == 1
        and not node.keywords
    ):
        return None
    source = compiler.read_value(node.args[0])
    if source.type != Type("Json"):
        return None
    return node.func.id, source


def collection_length(compiler: ServiceCompiler, node: ast.AST) -> Expr | None:
    selected = projection_source(compiler, node, {"json_keys", "json_array"})
    if selected is None:
        return None
    name, source = selected
    kind = "object" if name == "json_keys" else "array"
    compiler.record_decision(node, "json_consumer", "length", "temporary_collection_does_not_escape")
    if name == "json_array":
        return Expr(f"(rt::json_array_ref({compiler.reference(source)})?.len() as i64)", Type("int"))
    return Expr(
        f'(({compiler.reference(source)}).as_{kind}().ok_or("expected JSON {kind}")?.len() as i64)',
        Type("int"),
    )


def key_membership(compiler: ServiceCompiler, node: ast.Compare) -> Expr | None:
    if len(node.ops) != 1 or not isinstance(node.ops[0], (ast.In, ast.NotIn)):
        return None
    # Preserve left-to-right evaluation even when either operand has effects.
    needle = compiler.expr(node.left)
    if needle.type != Type("str"):
        return None
    selected = projection_source(compiler, node.comparators[0], {"json_keys"})
    if selected is None:
        return None
    _, source = selected
    use = runtime_argument_use(RuntimeParameter("str", "shared"), [node.left, node.comparators[0]], 0)
    place = compiler.argument_place(node.left, allow_place=use.mode == "borrow")
    if place is not None:
        needle = place
    prefix = "!" if isinstance(node.ops[0], ast.NotIn) else ""
    compiler.record_decision(node, "json_consumer", "membership", "temporary_keys_do_not_escape")
    return Expr(
        f"{{ let __needle = {compiler.reference(needle)}; "
        f"let __object = {compiler.reference(source)}; "
        f'{prefix}__object.as_object().ok_or("expected JSON object")?.contains_key(__needle) }}',
        Type("bool"),
    )


def borrowed_string_membership(compiler: ServiceCompiler, node: ast.Compare) -> Expr | None:
    from .growing_sets import cached_set_operation

    cached = cached_set_operation(compiler, node)
    if cached is not None:
        return cached
    from .map_positions import cached_map_operation

    cached = cached_map_operation(compiler, node)
    if cached is not None:
        return cached
    if not compiler.optimize or len(node.ops) != 1 or not isinstance(node.ops[0], (ast.In, ast.NotIn)):
        return None
    container_node = node.comparators[0]
    if runtime_argument_use(RuntimeParameter("*", "shared"), [container_node], 0).mode != "borrow":
        return None
    needle = compiler.argument_place(node.left)
    if needle is None or needle.type != Type("str"):
        return None
    container = compiler.read_value(container_node)
    if container.type.name not in {"dict", "set"} or container.type.args[0] != Type("str"):
        return None
    method = "contains_key" if container.type.name == "dict" else "contains"
    prefix = "!" if isinstance(node.ops[0], ast.NotIn) else ""
    compiler.record_decision(node, "string_membership", "borrow", "stable_string_key_and_container")
    return Expr(
        f"{{ let __needle: &str = AsRef::<str>::as_ref({compiler.reference(needle)}); "
        f"let __container = {compiler.reference(container)}; {prefix}__container.{method}(__needle) }}",
        Type("bool"),
    )
