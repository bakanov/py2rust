"""Typed call validation and emission for module call operations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_crc32(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if len(node.args) not in {1, 2}:
        compiler.error("crc32 requires data and an optional integer seed", node)
    data = compiler.expr(node.args[0])
    if data.type.name not in {"bytes", "bytearray"}:
        compiler.error("crc32 requires bytes or bytearray", node.args[0])
    seed = compiler.expr(node.args[1] if len(node.args) == 2 else ast.Constant(0), Type("int"))
    return Expr(
        f"{{ let __crc_data = {data.code}; let __crc_seed = {seed.code}; rt::crc32(&__crc_data, __crc_seed) }}",
        Type("int"),
    )


def emit_heap_operation(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    operation = name.removeprefix("heapq.")
    counts = {"heapify": 1, "heappush": 2, "heappop": 1, "heapreplace": 2, "heappushpop": 2}
    if operation not in counts or len(node.args) != counts[operation]:
        compiler.error("unsupported heapq operation or argument count", node)
    target = node.args[0]
    if not isinstance(target, ast.Name) or target.id not in compiler.locals:
        compiler.error("heapq requires a named typed list", target)
    typ = compiler.locals[target.id]

    def ordered(item: Type) -> bool:
        return item.name in {"int", "bool", "str"} or (
            item.name in {"list", "tuple", "tuple_var"} and all(ordered(child) for child in item.args)
        )

    float_priority = (
        typ.name == "list"
        and typ.args[0].name == "tuple"
        and len(typ.args[0].args) == 3
        and typ.args[0].args[0].name == "float"
        and typ.args[0].args[1].name == "int"
        and operation in {"heappush", "heappop"}
    )
    if typ.name != "list" or not ordered(typ.args[0]) and not float_priority:
        compiler.error("heapq requires ordered elements without custom comparisons", target)
    result = Type("None") if operation in {"heapify", "heappush"} else typ.args[0]
    if float_priority:
        if len(node.args) == 2:
            value = compiler.expr(node.args[1], typ.args[0])
            return Expr(f"{{ let __item = {value.code}; rt::heap_float_push(&mut {target.id}, __item) }}", result)
        return Expr(f"rt::heap_float_pop(&mut {target.id})?", result)
    fallible = "?" if operation in {"heappop", "heapreplace"} else ""
    # Evaluate the item before borrowing the heap: it can itself pop
    # from this list, and a failing item expression must not push.
    if len(node.args) == 2:
        value = compiler.expr(node.args[1], typ.args[0])
        return Expr(f"{{ let __item = {value.code}; rt::{operation}(&mut {target.id}, __item){fallible} }}", result)
    return Expr(f"rt::{operation}(&mut {target.id}){fallible}", result)
