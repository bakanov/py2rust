"""Borrow checked JSON string projections behind simple pure helper functions."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def prepare_projected_strings(compiler: ServiceCompiler, functions: list[ast.FunctionDef]) -> None:
    compiler.projected_strings = {}
    if not compiler.optimize or "json_string" not in compiler.imports:
        return
    for function in functions:
        body = function.body[1:] if ast.get_docstring(function) is not None else function.body
        if len(body) != 1 or not isinstance(body[0], ast.Return):
            continue
        call = body[0].value
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "json_string"
            and len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Subscript)
            and isinstance(call.args[0].value, ast.Name)
            and isinstance(call.args[0].slice, ast.Name)
            and len(function.args.args) == 2
            and not function.args.defaults
        ):
            continue
        parameters = [argument.arg for argument in function.args.args]
        projection = call.args[0]
        if projection.value.id not in parameters or projection.slice.id not in parameters:
            continue
        source_index, key_index = parameters.index(projection.value.id), parameters.index(projection.slice.id)
        types, result = compiler.functions[function.name]
        if (
            source_index == key_index
            or types[source_index] != Type("Json")
            or types[key_index] != Type("str")
            or result != Type("str")
        ):
            continue
        compiler.projected_strings[function.name] = (source_index, key_index)
    return


def projected_string(compiler: ServiceCompiler, node: ast.AST) -> Expr | None:
    if not compiler.optimize or not compiler.optimize_json_views:
        return None
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
        return None
    plan = compiler.projected_strings.get(node.func.id)
    if plan is None or len(node.args) != 2:
        return None
    source_node, key_node = node.args[plan[0]], node.args[plan[1]]
    # Named backing and a named/literal key have no effects to reorder. More
    # complicated actual arguments retain the ordinary owned helper invocation.
    if not isinstance(source_node, ast.Name) or not (
        isinstance(key_node, ast.Name) or isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)
    ):
        return None
    source = compiler.local_read(source_node)
    key = compiler.argument_place(key_node)
    if source is None or source.type != Type("Json") or key is None or key.type != Type("str"):
        return None
    cache = compiler.projection_caches.get(id(node))
    if cache is not None:
        name, index = cache
        return Expr(
            f"rt::cached_json_string(&{name}[{index}], {compiler.reference(source)}, {compiler.reference(key)})?",
            Type("str"),
            borrowed=True,
        )
    return Expr(
        f"rt::json_string_ref(rt::json_key_ref({compiler.reference(source)}, {compiler.reference(key)})?)?",
        Type("str"),
        borrowed=True,
    )


def projection_backing(compiler: ServiceCompiler, node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return None
    plan = compiler.projected_strings.get(node.func.id)
    if plan is None or len(node.args) != 2:
        return None
    source = node.args[plan[0]]
    return source.id if isinstance(source, ast.Name) else None


def bind_projected_string(compiler: ServiceCompiler, node: ast.AnnAssign, typ: Type) -> str | None:
    name = node.target.id
    backing = projection_backing(compiler, node.value)
    if typ != Type("str") or name in compiler.mutable_bindings or backing not in compiler.borrowed_parameters:
        return None
    value = projected_string(compiler, node.value)
    if value is None:
        return None
    # The backing is already a proven borrowed parameter/iteration item. The
    # local string cannot mutate, and owned uses materialize through emit_name.
    compiler.locals[name] = typ
    compiler.borrowed_parameters.add(name)
    compiler.borrowed_str_parameters.add(name)
    compiler.record_decision(node, "projected_string", "borrow", "immutable_local_from_borrowed_json_backing")
    return f"let {name}: &str = {value.code};"


def insert_borrowed_string(compiler: ServiceCompiler, node: ast.Call) -> Expr | None:
    from .growing_sets import cached_set_operation

    cached = cached_set_operation(compiler, node)
    if cached is not None:
        return cached
    if not compiler.optimize:
        return None
    value = compiler.argument_place(node.args[0])
    if value is None or value.type != Type("str"):
        return None
    name = node.func.value.id
    compiler.record_decision(node, "set_add", "borrow", "materialize_string_only_when_absent")
    return Expr(
        f"{{ let __value: &str = AsRef::<str>::as_ref({compiler.reference(value)}); "
        f"if !{name}.contains(__value) {{ {name}.insert(__value.to_owned()); }} }}",
        Type("None"),
    )
