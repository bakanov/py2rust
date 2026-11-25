"""Lazy checked string projections across repeated scans of immutable JSON lists."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import binding_write_reasons, iteration_use
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def prepare_scan_caches(compiler: ServiceCompiler, outer: ast.For) -> str:
    if not (compiler.optimize and compiler.optimize_iteration and compiler.optimize_json_views):
        return ""
    setup = []
    region = ast.Module(body=outer.body, type_ignores=[])
    for inner in outer.body:
        if not (
            isinstance(inner, ast.For)
            and isinstance(inner.iter, ast.Name)
            and isinstance(inner.target, ast.Name)
            and inner.iter.id != outer.target.id
            and compiler.locals.get(inner.iter.id) == Type("list", (Type("Json"),))
            and inner.iter.id not in binding_write_reasons(region, {inner.iter.id})
        ):
            continue
        plan = iteration_use(inner)
        if plan.mode != "borrow" or not plan.borrow_item:
            continue
        groups: dict[str, list[ast.Call]] = {}
        for call in ast.walk(inner):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.keywords:
                continue
            projection = compiler.projected_strings.get(call.func.id)
            if projection is None or len(call.args) != 2:
                continue
            source, key = call.args[projection[0]], call.args[projection[1]]
            if (
                isinstance(source, ast.Name)
                and source.id == inner.target.id
                and isinstance(key, ast.Constant)
                and isinstance(key.value, str)
            ):
                groups.setdefault(key.value, []).append(call)
        if not groups:
            continue
        index = f"__projection_index_{inner.lineno}_{inner.col_offset}"
        caches = []
        for number, calls in enumerate(groups.values()):
            cache = f"__projection_cache_{inner.lineno}_{inner.col_offset}_{number}"
            caches.append((cache, "std::cell::OnceCell::new"))
            setup.append(f"let mut {cache}: Vec<std::cell::OnceCell<String>> = Vec::new();")
            for call in calls:
                compiler.projection_caches[id(call)] = (cache, index)
        from .map_positions import prepare_map_positions

        map_setup, map_caches = prepare_map_positions(compiler, outer, inner, groups, index)
        setup.extend(map_setup)
        caches.extend(map_caches)
        from .growing_sets import prepare_growing_sets

        set_setup, set_caches = prepare_growing_sets(compiler, outer, inner, groups, index)
        setup.extend(set_setup)
        caches.extend(set_caches)
        compiler.scan_caches[id(inner)] = (index, caches)
        compiler.record_decision(inner, "json_projection", "lazy_cache", "immutable_list_repeated_scan")
    return "\n".join(setup) + ("\n" if setup else "")
