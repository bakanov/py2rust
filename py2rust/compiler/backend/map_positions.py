"""Stable entry positions for append-only dictionaries in repeated JSON scans."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import binding_write_reasons
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def append_only(region: ast.AST, name: str) -> bool:
    parents = {id(child): node for node in ast.walk(region) for child in ast.iter_child_nodes(node)}
    for use in ast.walk(region):
        if not isinstance(use, ast.Name) or use.id != name:
            continue
        parent = parents.get(id(use))
        if not isinstance(use.ctx, ast.Load):
            return False
        if isinstance(parent, ast.Subscript) and parent.value is use:
            if isinstance(parent.ctx, ast.Load):
                continue
            statement = parents.get(id(parent))
            if isinstance(statement, ast.Assign) and statement.targets == [parent]:
                continue
        if (
            isinstance(parent, ast.Compare)
            and parent.comparators == [use]
            and len(parent.ops) == 1
            and isinstance(parent.ops[0], (ast.In, ast.NotIn))
        ):
            continue
        return False
    return True


def projection_bindings(inner: ast.For, groups: dict[str, list[ast.Call]]) -> dict[str, tuple[str, int]]:
    body = ast.Module(body=inner.body, type_ignores=[])
    projected = {id(call): field for field, calls in groups.items() for call in calls}
    keys = {}
    for declaration in inner.body:
        if not isinstance(declaration, ast.AnnAssign) or not isinstance(declaration.target, ast.Name):
            continue
        field = projected.get(id(declaration.value))
        if field is None:
            continue
        name = declaration.target.id
        if name not in binding_write_reasons(body, {name}, frozenset({id(declaration.target)})):
            keys[name] = (field, declaration.lineno)
    return keys


def prepare_map_positions(
    compiler: ServiceCompiler, outer: ast.For, inner: ast.For, groups: dict[str, list[ast.Call]], index: str
) -> tuple[list[str], list[tuple[str, str]]]:
    region = ast.Module(body=outer.body, type_ignores=[])
    body = ast.Module(body=inner.body, type_ignores=[])
    keys = projection_bindings(inner, groups)
    maps = {
        name
        for name, typ in compiler.locals.items()
        if typ.name == "dict" and typ.args[0] == Type("str") and name != outer.target.id and append_only(region, name)
    }
    plans = {}
    setup, caches = [], []
    parents = {id(child): node for node in ast.walk(body) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(body):
        if isinstance(node, ast.Subscript):
            container, key = node.value, node.slice
            mode = "read" if isinstance(node.ctx, ast.Load) else "write"
            target = node if mode == "read" else parents.get(id(node))
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            container, key, mode, target = node.comparators[0], node.left, "contains", node
        else:
            continue
        if not (
            isinstance(container, ast.Name) and container.id in maps and isinstance(key, ast.Name) and key.id in keys
        ):
            continue
        if key.lineno <= keys[key.id][1]:
            continue
        pair = (container.id, keys[key.id][0])
        if pair not in plans:
            cache = f"__map_positions_{inner.lineno}_{inner.col_offset}_{len(plans)}"
            plans[pair] = cache
            setup.append(f"let mut {cache}: Vec<std::cell::Cell<Option<usize>>> = Vec::new();")
            caches.append((cache, "|| std::cell::Cell::new(None)"))
        compiler.map_positions[id(target)] = (plans[pair], index, container.id, key, mode)
    if plans:
        compiler.record_decision(inner, "dictionary_lookup", "entry_position", "stable_keys_append_only_map")
    return setup, caches


def cached_map_operation(compiler: ServiceCompiler, node: ast.AST) -> Expr | None:
    plan = compiler.map_positions.get(id(node))
    if plan is None:
        return None
    cache, index, name, key_node, mode = plan
    typ = compiler.locals[name]
    key = compiler.argument_place(key_node)
    if key is None or key.type != Type("str"):
        return None
    slot = f"&{cache}[{index}]"
    reference = compiler.reference(key)
    if mode == "contains":
        suffix = "is_none" if isinstance(node.ops[0], ast.NotIn) else "is_some"
        return Expr(f"rt::cached_map_position({slot}, &{name}, {reference}).{suffix}()", Type("bool"))
    if mode == "read":
        return Expr(f"rt::cached_map_get({slot}, &{name}, {reference})?.clone()", typ.args[1])
    value = compiler.expr(node.value, typ.args[1])
    return Expr(
        f"{{ let __value = {value.code}; let __key: &str = {reference}; "
        f"rt::cached_map_insert({slot}, &mut {name}, __key, __value); }}",
        Type("None"),
    )
