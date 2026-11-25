"""Cache stable-key membership in growing sets, invalidating misses on growth."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .map_positions import projection_bindings
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def only_adds(region: ast.AST, name: str) -> bool:
    parents = {id(child): node for node in ast.walk(region) for child in ast.iter_child_nodes(node)}
    for use in ast.walk(region):
        if not isinstance(use, ast.Name) or use.id != name:
            continue
        if not isinstance(use.ctx, ast.Load):
            return False
        parent = parents.get(id(use))
        if isinstance(parent, ast.Attribute) and parent.value is use and parent.attr == "add":
            call = parents.get(id(parent))
            if isinstance(call, ast.Call) and call.func is parent and len(call.args) == 1 and not call.keywords:
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


def prepare_growing_sets(
    compiler: ServiceCompiler, outer: ast.For, inner: ast.For, groups: dict[str, list[ast.Call]], index: str
) -> tuple[list[str], list[tuple[str, str]]]:
    region = ast.Module(body=outer.body, type_ignores=[])
    sets = {
        name
        for name, typ in compiler.locals.items()
        if typ == Type("set", (Type("str"),)) and name != outer.target.id and only_adds(region, name)
    }
    projected = {id(call): field for field, calls in groups.items() for call in calls}
    keys = projection_bindings(inner, groups)
    plans = {}
    setup, caches = [], []
    for node in ast.walk(inner):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)):
            container, key, mode = node.comparators[0], node.left, "contains"
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and len(node.args) == 1
            and not node.keywords
        ):
            container, key, mode = node.func.value, node.args[0], "add"
        else:
            continue
        if not isinstance(container, ast.Name) or container.id not in sets:
            continue
        field = projected.get(id(key))
        if isinstance(key, ast.Name) and key.id in keys and key.lineno > keys[key.id][1]:
            field = keys[key.id][0]
        if field is None:
            continue
        pair = (container.id, field)
        if pair not in plans:
            cache = f"__set_membership_{inner.lineno}_{inner.col_offset}_{len(plans)}"
            plans[pair] = cache
            setup.append(f"let mut {cache}: Vec<std::cell::Cell<Option<(usize, bool)>>> = Vec::new();")
            caches.append((cache, "|| std::cell::Cell::new(None)"))
        compiler.growing_sets[id(node)] = (plans[pair], index, container.id, key, mode)
    if plans:
        compiler.record_decision(inner, "set_membership", "growth_checked_cache", "stable_key_and_growing_set")
    return setup, caches


def cached_set_operation(compiler: ServiceCompiler, node: ast.AST) -> Expr | None:
    plan = compiler.growing_sets.get(id(node))
    if plan is None:
        return None
    cache, index, name, key_node, mode = plan
    key = compiler.argument_place(key_node)
    if key is None or key.type != Type("str"):
        return None
    value = f"let __value: &str = AsRef::<str>::as_ref({compiler.reference(key)});"
    slot = f"{cache}[{index}]"
    if mode == "contains":
        expression = (
            f"(match {slot}.get() {{ Some((_, true)) => true, "
            f"Some((__size, false)) if __size == {name}.len() => false, "
            f"_ => {{ {value} let __present = {name}.contains(__value); "
            f"{slot}.set(Some(({name}.len(), __present))); __present }} }})"
        )
        if isinstance(node.ops[0], ast.NotIn):
            expression = "!" + expression
        return Expr(expression, Type("bool"))
    return Expr(
        f"{{ if !matches!({slot}.get(), Some((_, true))) {{ {value} "
        f"if !{name}.contains(__value) {{ {name}.insert(__value.to_owned()); }} "
        f"{slot}.set(Some(({name}.len(), true))); }} }}",
        Type("None"),
    )
