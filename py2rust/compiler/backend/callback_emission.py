"""Typed call validation and emission for callback operations."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..memory import RuntimeParameter, runtime_argument_use
from .values import Expr, Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def emit_parallel_map(compiler: ServiceCompiler, node: ast.Call) -> Expr:
    if len(node.args) != 3 or not isinstance(node.args[0], ast.Name):
        compiler.error("parallel_map requires a named callback, items and worker limit", node)
    callback = node.args[0].id
    if compiler.functions.get(callback) != ((Type("Json"),), Type("Json")):
        compiler.error("parallel callback must be (Json) -> Json", node)
    items = compiler.expr(node.args[1], compiler.named_type("list[Json]"))
    workers = compiler.expr(node.args[2], Type("int"))
    return Expr(f"rt::parallel_map({callback}, &({items.code}), {workers.code})?", compiler.named_type("list[Json]"))


def emit_web_server(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    count = 4 if name == "web_serve_stream" else 3
    if len(node.args) != count or not isinstance(node.args[2], ast.Name):
        compiler.error(f"{name} requires host, port, handler" + (", poll" if count == 4 else ""), node)
    callback = node.args[2].id
    if compiler.functions.get(callback) != ((Type("WebRequest"),), Type("WebResponse")):
        compiler.error("web handler must be (WebRequest) -> WebResponse", node)
    host = compiler.expr(node.args[0], Type("str"))
    port = compiler.expr(node.args[1], Type("int"))
    callbacks = callback
    if count == 4:
        if not isinstance(node.args[3], ast.Name) or compiler.functions.get(node.args[3].id) != (
            (Type("Json"),),
            Type("StreamChunk"),
        ):
            compiler.error("stream poll callback must be (Json) -> StreamChunk", node)
        callbacks += f", {node.args[3].id}"
    return Expr(f"rt::{name}(&({host.code}), {port.code}, {callbacks})?", Type("None"))


def emit_http_server(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    expected_args = 4 if name == "http_serve_json" else 6
    if len(node.args) != expected_args or not isinstance(node.args[1], ast.Name):
        compiler.error(
            f"{name} requires {expected_args} arguments: server, handler, count, max_body[, accept_timeout_ms, connection_timeout_ms]",
            node,
        )
    callback = node.args[1].id
    if compiler.functions.get(callback) != (
        (Type("str"), Type("str"), Type("Json")),
        Type("Json"),
    ):
        compiler.error("HTTP handler must be (str, str, Json) -> Json", node)
    server = compiler.expr(node.args[0], Type("HttpServer"))
    arguments = [compiler.expr(a, Type("int")).code for a in node.args[2:]]
    return Expr(
        f"rt::{name}(&({server.code}), {callback}, {', '.join(arguments)})?",
        Type("None"),
    )


def emit_function_call(compiler: ServiceCompiler, node: ast.Call, name: str) -> Expr:
    params, result = compiler.functions[name]
    if len(params) != len(node.args):
        compiler.error("wrong function argument count", node)
    args = []
    decisions = list(compiler.parameter_uses.get(name, {}).values())
    for index, (arg, typ) in enumerate(zip(node.args, params)):
        if decisions and decisions[index].mode == "borrow":
            use = runtime_argument_use(RuntimeParameter(str(typ), "shared"), node.args, index)
            place = compiler.argument_place(arg, allow_place=use.mode == "borrow")
            value = place if place is not None and place.type == typ else compiler.expr(arg, typ)
            args.append(compiler.reference(value))
        else:
            args.append(compiler.expr(arg, typ).code)
    call = f"{name}({', '.join(args)})"
    return Expr(call + "?", result, result_call=call if name in compiler.parameter_uses else None)
