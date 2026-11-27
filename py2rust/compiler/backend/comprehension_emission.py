"""Render synchronous comprehensions as nested result-construction loops."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .find_emission import collection_iteration
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def bind_target(compiler: ServiceCompiler, target: str, item_type: Type, node: ast.Call) -> None:
    target_node = ast.parse(target, mode="eval").body

    def bind(pattern: ast.expr, typ: Type) -> None:
        if isinstance(pattern, ast.Name):
            compiler.locals[pattern.id] = typ
            return
        if isinstance(pattern, ast.Tuple) and typ.name == "tuple" and len(pattern.elts) == len(typ.args):
            for item, item_type in zip(pattern.elts, typ.args):
                bind(item, item_type)
            return
        compiler.error("tuple comprehension target does not match the item type", node)

    bind(target_node, item_type)


def emit_comprehension(compiler: ServiceCompiler, node: ast.Call, expected: Type | None) -> Expr:
    targets, value_node, sources, conditions, result_kind = node.py2rust_comprehension
    if expected is not None and expected.name == "Json":
        expected = Type("list", (Type("Json"),))
    expected_item = (
        Type("tuple", expected.args)
        if expected is not None and expected.name == "dict"
        else expected.args[0] if expected is not None and expected.name in {"list", "set"} and expected.args else None
    )
    before = compiler.locals.copy()
    depth = compiler.comprehension_depth
    compiler.comprehension_depth = depth + 1
    assignments = {
        target.target.id
        for expression in (*sources, *(condition for group in conditions for condition in group), value_node)
        for target in ast.walk(expression)
        if isinstance(target, ast.NamedExpr)
    }
    from .legacy_adapter import annotation

    for expression in (*sources, *(condition for group in conditions for condition in group), value_node):
        for target in ast.walk(expression):
            if isinstance(target, ast.NamedExpr) and target.target.id in assignments:
                value_type = getattr(target.value, "py2rust_value_type", None)
                if value_type is not None:
                    compiler.locals[target.target.id] = compiler.typ(annotation(value_type))
    levels = []
    for index, (target, source_node) in enumerate(zip(targets, sources)):
        source = compiler.expr(source_node)
        if source.type.name == "Json" or source.type.name == "optional" and source.type.args[0].name == "Json":
            source = compiler.convert(source, Type("list", (Type("Json"),)), node)
        if source.type.name == "optional" and source.type.args[0].name in {"list", "set", "dict", "tuple", "tuple_var"}:
            source = compiler.convert(source, source.type.args[0], node)
        if (
            source.type.name == "tuple"
            and source.type.args
            and all(item == source.type.args[0] for item in source.type.args)
        ):
            source = compiler.convert(source, Type("tuple_var", (source.type.args[0],)), node)
        item_type, method = collection_iteration(compiler, source, node)
        bind_target(compiler, target, item_type, node)
        compiler.call_counter += 1
        storage = f"__comprehension_source_{compiler.call_counter}"
        checks = [compiler.expr(condition, Type("bool")).code for condition in conditions[index]]

        def dynamic(typ: Type) -> bool:
            return typ.name == "union" or any(dynamic(item) for item in typ.args)

        iteration = f"{storage}.into_iter()" if dynamic(item_type) else f"{storage}.{method}().cloned()"
        levels.append((target, storage, source, iteration, checks))
    value = compiler.expr(value_node, expected_item)
    declarations = " ".join(
        f"let mut {compiler.binding(target)}: {compiler.locals[target].rust()};" for target in sorted(assignments)
    )
    compiler.locals = before
    compiler.comprehension_depth = depth
    if expected is not None and expected.name == "tuple" and all(item == value.type for item in expected.args):
        expected = Type("list", (value.type,))
    result = expected or Type(
        result_kind.removeprefix("builtins.") if result_kind in {"builtins.set", "builtins.dict"} else "list",
        value.type.args if result_kind == "builtins.dict" else (value.type,),
    )
    if result not in {
        Type("list", (value.type,)),
        Type("set", (value.type,)),
        Type("dict", value.type.args) if value.type.name == "tuple" else Type("dict"),
    }:
        compiler.error(f"comprehension result does not match its expected type: {result} from {value.type}", node)
    compiler.call_counter += 1
    result_name = f"__comprehension_result_{compiler.call_counter}"
    if result.name == "dict":
        body = f"{{ let (__key, __value) = {value.code}; {result_name}.insert(__key, __value); }}"
        empty = "indexmap::IndexMap::new()"
    else:
        method = "insert" if result.name == "set" else "push"
        body = f"{result_name}.{method}({value.code});"
        empty = "std::collections::BTreeSet::new()" if result.name == "set" else "Vec::new()"
    for target, storage, source, iteration, checks in reversed(levels):
        if checks:
            body = "if " + " && ".join(checks) + " { " + body + " }"
        body = f"let {storage} = ({source.code}); for {target} in {iteration} {{ {body} }}"
    return Expr(
        f"{{ let mut {result_name}: {result.rust()} = {empty}; {declarations} {body} {result_name} }}",
        result,
    )
