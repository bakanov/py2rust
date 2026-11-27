"""Build write-only JSON maps from stable borrowed items, then materialize once."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import binding_write_reasons, iteration_use
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler

OWNED = Type("dict", (Type("str"), Type("Json")))
VIEW = Type("dict", (Type("str"), Type("$json_ref")))


def prepare_borrowed_maps(compiler: ServiceCompiler, function: ast.FunctionDef) -> None:
    compiler.borrowed_maps = {}
    compiler.borrowed_map_loops = set()
    if not (compiler.optimize and compiler.optimize_iteration and compiler.optimize_json_views):
        return
    # A handler could observe partially updated owned maps after an error.
    if any(isinstance(node, (ast.Try, ast.With)) for node in ast.walk(function)):
        return
    for position, declaration in enumerate(function.body):
        if isinstance(declaration, ast.AnnAssign):
            for item in ast.walk(declaration.annotation):
                if getattr(item, "source_path", "<unknown>") == "<unknown>":
                    item.source_path = getattr(declaration, "source_path", function.name)
        if not (
            isinstance(declaration, ast.AnnAssign)
            and isinstance(declaration.target, ast.Name)
            and compiler.typ(declaration.annotation) == OWNED
            and isinstance(declaration.value, ast.Dict)
            and not declaration.value.keys
        ):
            continue
        name = declaration.target.id
        first_use = next(
            (
                statement
                for statement in function.body[position + 1 :]
                if any(isinstance(use, ast.Name) and use.id == name for use in ast.walk(statement))
            ),
            None,
        )
        if not isinstance(first_use, ast.For) or first_use.target.id == name:
            continue
        if first_use.orelse or any(isinstance(use, ast.Name) and use.id == name for use in ast.walk(first_use.iter)):
            continue
        region = ast.Module(body=first_use.body, type_ignores=[])
        parents = {id(child): node for node in ast.walk(region) for child in ast.iter_child_nodes(node)}
        candidates = {}
        for inner in first_use.body:
            if not (
                isinstance(inner, ast.For)
                and isinstance(inner.iter, ast.Name)
                and isinstance(inner.target, ast.Name)
                and inner.iter.id != first_use.target.id
            ):
                continue
            plan = iteration_use(inner)
            if plan.mode != "borrow" or not plan.borrow_item:
                continue
            source = inner.iter.id
            if source in binding_write_reasons(region, {source}):
                continue
            # No other use may consume the backing while map entries borrow it.
            if any(
                isinstance(use, ast.Name)
                and use.id == source
                and not (isinstance(parents.get(id(use)), ast.For) and parents[id(use)].iter is use)
                for use in ast.walk(region)
            ):
                continue
            candidates[id(inner)] = (inner.target.id, source)
        sources, loops = set(), set()
        valid = True
        for use in ast.walk(region):
            if not isinstance(use, ast.Name) or use.id != name:
                continue
            target = parents.get(id(use))
            assignment = parents.get(id(target))
            if not (
                isinstance(use.ctx, ast.Load)
                and isinstance(target, ast.Subscript)
                and target.value is use
                and isinstance(target.ctx, ast.Store)
                and isinstance(assignment, ast.Assign)
                and assignment.targets == [target]
                and isinstance(assignment.value, ast.Name)
            ):
                valid = False
                break
            ancestor = assignment
            while ancestor is not None and id(ancestor) not in candidates:
                ancestor = parents.get(id(ancestor))
            candidate = candidates.get(id(ancestor))
            if candidate is None or assignment.value.id != candidate[0]:
                valid = False
                break
            sources.add(candidate[1])
            loops.add(id(ancestor))
        if valid and sources:
            loops.update(
                id(inner)
                for inner in ast.walk(region)
                if isinstance(inner, ast.For) and isinstance(inner.iter, ast.Name) and inner.iter.id in sources
            )
            compiler.borrowed_maps.setdefault(id(first_use), []).append((name, sources, loops))
    return


def begin_borrowed_maps(compiler: ServiceCompiler, loop: ast.For) -> list[str]:
    names = []
    for name, sources, loops in compiler.borrowed_maps.get(id(loop), []):
        if compiler.locals.get(name) != OWNED or any(
            compiler.locals.get(source) != Type("list", (Type("Json"),)) for source in sources
        ):
            continue
        compiler.locals[name] = VIEW
        compiler.borrowed_map_loops.update(loops)
        names.append(name)
        compiler.record_decision(loop, "dictionary_values", "borrow", "write_only_map_of_stable_iteration_items")
    return names


def finish_borrowed_maps(names: list[str], loop: str) -> str:
    if not names:
        return loop
    declarations = "\n".join(f"let mut {name}: {VIEW.rust()} = indexmap::IndexMap::new();" for name in names)
    owned = [f"__owned_map_{name}" for name in names]
    values = [
        f"{name}.into_iter().map(|(__key, __value)| (__key, __value.clone())).collect::<{OWNED.rust()}>()"
        for name in names
    ]
    assignments = "\n".join(f"{name} = {value};" for name, value in zip(names, owned))
    return f"let ({', '.join(owned)},) = {{\n{declarations}\n{loop}\n({', '.join(values)},)\n}};\n{assignments}"
