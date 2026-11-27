"""Evaluate the supported filtered-generator `next` form without a temporary list."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def collection_iteration(compiler: ServiceCompiler, source: Expr, node: ast.AST) -> tuple[Type, str]:
    if source.type.name not in {"list", "set", "dict", "tuple", "tuple_var"} or not source.type.args:
        compiler.error(f"generator requires a typed collection, got {source.type} in {ast.unparse(node)}", node)
    item_type = source.type.args[0]
    if source.type.name == "tuple" and any(item != item_type for item in source.type.args):
        compiler.error(f"generator requires homogeneous tuple items, got {source.type} in {ast.unparse(node)}", node)
    return item_type, "keys" if source.type.name == "dict" else "iter"


def emit_find(compiler: ServiceCompiler, node: ast.Call, expected: Type | None) -> Expr:
    target, value_node, conditions = node.py2rust_find
    if len(node.args) != 2:
        compiler.error("filtered next requires an iterable and default", node)
    source = compiler.expr(node.args[0])
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
    default = compiler.expr(node.args[1], expected)
    result = expected or default.type
    if default.type != result:
        compiler.error("filtered next default must match the result type", node)
    item_type, method = collection_iteration(compiler, source, node)
    before = compiler.locals.copy()
    target_node = ast.parse(target, mode="eval").body

    def bind(pattern: ast.expr, typ: Type) -> None:
        if isinstance(pattern, ast.Name):
            compiler.locals[pattern.id] = typ
            return
        if isinstance(pattern, ast.Tuple) and typ.name == "tuple" and len(pattern.elts) == len(typ.args):
            for element, element_type in zip(pattern.elts, typ.args):
                bind(element, element_type)
            return
        compiler.error("tuple next target does not match the item type", node)

    bind(target_node, item_type)
    checks = [compiler.expr(condition, Type("bool")).code for condition in conditions]
    value = compiler.expr(value_node, result)
    if value.type != result:
        compiler.error("filtered next result must match its default type", node)
    compiler.locals = before
    compiler.call_counter += 1
    storage = f"__find_source_{compiler.call_counter}"
    result_name = f"__find_result_{compiler.call_counter}"
    body = ""
    if checks:
        body += "if " + " && ".join(checks) + " { "
    body += f"{result_name} = {value.code}; break;"
    if checks:
        body += " }"
    return Expr(
        f"{{ let {storage} = {source.code}; let mut {result_name}: {result.rust()} = {default.code}; "
        f"for {target} in {storage}.{method}().cloned() {{ {body} }} {result_name} }}",
        result,
    )
