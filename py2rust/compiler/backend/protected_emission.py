"""Host AST adapters; semantic decisions and Rust templates remain in explicit rules."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..exception_policy import RESOURCE_TYPES
from .exception_emission import render_handler, render_resource
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_resource(compiler: ServiceCompiler, node: ast.With) -> str:
    if len(node.items) != 1 or not isinstance(node.items[0].optional_vars, ast.Name):
        compiler.error("with requires one resource and a named binding", node)
    item = node.items[0]
    name = item.optional_vars.id
    compiler.check_name(name, node)
    if name in compiler.locals:
        compiler.error("resource binding cannot shadow an existing local", node)
    value = compiler.expr(item.context_expr)
    if value.type.name not in RESOURCE_TYPES:
        compiler.error(
            "with supports GzipReader, GzipWriter, FileHandle, LineReader, HttpReader, TcpListener, TcpStream, UdpSocket, UnixListener, UnixStream and ProcessPool resources",
            node,
        )
    before = compiler.locals.copy()
    compiler.locals[name] = value.type
    body = "\n".join(compiler.block(node.body))
    compiler.locals = before
    return render_resource(value=value.code, name=name, resource_type=value.type.rust(), body=body)


def emit_try(compiler: ServiceCompiler, node: ast.Try) -> str:
    if node.finalbody:
        return compiler.try_finally(node)
    if (
        len(node.handlers) != 1
        or not isinstance(node.handlers[0].type, ast.Name)
        or node.handlers[0].type.id != "Exception"
    ):
        compiler.error("try requires at most one except Exception handler and/or finally", node)

    if not hasattr(node, "py2rust_flow"):
        compiler.validate_try_jumps(node.body)
    compiler.try_depth += 1
    body = "\n".join(compiler.block(node.body))
    compiler.try_depth -= 1
    success = "\n".join(compiler.block(node.orelse))
    handler = node.handlers[0]
    before = compiler.locals.copy()
    compiler.error_counter += 1
    active_error = f"__caught_error_{compiler.error_counter}"
    binding = ""
    if handler.name:
        compiler.check_name(handler.name, handler)
        if handler.name in compiler.locals:
            compiler.error("exception binding cannot shadow an existing local", handler)
        compiler.locals[handler.name] = Type("Exception")
        binding = f"let {handler.name}: String = {active_error}.to_string();\n"
    compiler.active_errors.append(active_error)
    failure = binding + "\n".join(compiler.block(handler.body))
    compiler.active_errors.pop()
    compiler.locals = before
    return render_handler(
        body=body,
        success=success,
        failure=failure,
        result_type=compiler.result.rust(),
        active_error=active_error,
        nested_return=bool(compiler.try_depth),
        body_terminates=compiler.always_returns(node.body),
    )
