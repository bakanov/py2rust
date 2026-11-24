"""Explicit call dispatch; specific handlers own validation and rendering."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..library_contracts import LIBRARY, LOG_LEVELS, MODULE_CALLS
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler

from .callback_emission import (
    emit_function_call,
    emit_http_server,
    emit_parallel_map,
    emit_web_server,
)
from .constructor_emission import (
    emit_bytes_constructor,
    emit_empty_constructor,
    emit_hex_constructor,
    emit_sequence_constructor,
    emit_set_constructor,
)
from .module_call_emission import emit_crc32, emit_heap_operation
from .scalar_call_emission import (
    emit_abs,
    emit_conversion,
    emit_length,
    emit_ord,
    emit_print,
    emit_scalar_extreme,
    emit_sequence_extreme,
)


def emit_call(compiler: ServiceCompiler, node: ast.Call, expected: Type | None = None) -> Expr:
    name = ast.unparse(node.func)
    if name in compiler.records:
        return compiler.record_constructor(name, node)
    if name == "sorted":
        return compiler.sorted_call(node, expected)
    if node.keywords:
        compiler.error("keyword arguments are outside the service profile", node)
    if (name == "crc32" and name in compiler.imports) or (
        name in {"zlib.crc32", "binascii.crc32"} and name.split(".")[0] in compiler.modules
    ):
        return emit_crc32(compiler, node)
    if name.startswith("heapq.") and "heapq" in compiler.modules:
        return emit_heap_operation(compiler, node, name)
    if name == "int.from_bytes":
        return compiler.library_call("int_from_bytes", node.args, node)
    if name in {"min", "max"} and len(node.args) == 1:
        return emit_sequence_extreme(compiler, node, name)
    if name in {"min", "max"} and len(node.args) == 2:
        return emit_scalar_extreme(compiler, node, name)
    if name in {"bytes", "bytearray"}:
        return emit_bytes_constructor(compiler, node, name)
    if name in {"bytes.fromhex", "bytearray.fromhex"} and len(node.args) == 1:
        return emit_hex_constructor(compiler, node, name)
    if name in {"list", "tuple"} and len(node.args) == 1:
        return emit_sequence_constructor(compiler, node, name)
    if name == "set" and len(node.args) == 1:
        return emit_set_constructor(compiler, node)
    if name in {"set", "list", "dict", "tuple"} and not node.args:
        return emit_empty_constructor(compiler, node, name, expected)
    if (
        name in {"ceil", "floor"}
        and name in compiler.imports
        or name in {"math.ceil", "math.floor"}
        and "math" in compiler.modules
    ) and len(node.args) == 1:
        value = compiler.expr(node.args[0])
        if value.type.name == "int":
            return value  # Preserve large integer arguments without an f64 round trip.
    if name in compiler.imports and name in LIBRARY:
        return compiler.library_call(name, node.args, node)
    if name in MODULE_CALLS and name.split(".")[0] in compiler.modules:
        return compiler.library_call(MODULE_CALLS[name], node.args, node)
    if name == "parallel_map" and name in compiler.imports:
        return emit_parallel_map(compiler, node)
    if name in {"web_serve", "web_serve_stream"} and name in compiler.imports:
        return emit_web_server(compiler, node, name)
    if name.startswith("logging.") and "logging" in compiler.modules and name.split(".")[1].upper() in LOG_LEVELS:
        level = ast.Constant(LOG_LEVELS[name.split(".")[1].upper()])
        return compiler.library_call("log", [level, *node.args], node)
    if name in {"http_serve_json", "http_serve_json_timeout"} and name in compiler.imports:
        return emit_http_server(compiler, node, name)
    if name in compiler.functions:
        return emit_function_call(compiler, node, name)
    if name == "ord":
        return emit_ord(compiler, node)
    if name == "len" and len(node.args) == 1:
        return emit_length(compiler, node)
    if name in {"str", "int", "float"} and len(node.args) == 1:
        return emit_conversion(compiler, node, name)
    if name == "abs" and len(node.args) == 1:
        return emit_abs(compiler, node)
    if name == "print":
        return emit_print(compiler, node)
    if isinstance(node.func, ast.Attribute):
        return compiler.method(node)
    compiler.error(f"unsupported or unimported call: {name}", node)
