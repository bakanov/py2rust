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
    defaults = compiler.function_defaults.get(name, ())
    required = len(params) - len(defaults)
    starred = [index for index, argument in enumerate(node.args) if isinstance(argument, ast.Starred)]
    supplied = len(node.args) + len(node.keywords)
    if starred and (len(starred) != 1 or starred[0] != len(node.args) - 1 or node.keywords):
        compiler.error("one trailing positional list unpack is supported", node)
    if not starred and not required <= supplied <= len(params):
        compiler.error(f"wrong function argument count for {name}: {ast.unparse(node)}", node)
    if starred and starred[0] > required:
        compiler.error("required arguments cannot follow an unpacked list", node)
    decisions = list(compiler.parameter_uses.get(name, {}).values())

    def argument_code(arg: ast.expr, sources: list[ast.expr], index: int, target: int) -> str:
        typ = params[target]
        if typ.name == "callable" and isinstance(arg, ast.Name) and arg.id in compiler.functions:
            callback_params, callback_result = compiler.functions[arg.id]
            supplied = len(typ.args) - 1
            if callback_result == typ.args[-1] and len(callback_params) >= supplied:
                captures = compiler.function_parameters[arg.id][: len(callback_params) - supplied]
                names = [f"__arg{position}" for position in range(supplied)]
                arguments = [*(f"{capture}.clone()" for capture in captures), *names]
                return f"|{', '.join(names)}| {arg.id}({', '.join(arguments)})"
        stateful_turn_controller = (
            name.startswith("py__openciv3__turn_controller__TurnController__")
            and name.rsplit("__", 1)[-1] in {"advance", "autoplay_human_turn", "respond_to_trade"}
            and target == 0
        ) or (
            name.startswith("py__civ3_ai__civilization_ai__CivilizationAI__")
            and not name.endswith("__pending_trade")
            and target == 0
        )
        if stateful_turn_controller:
            place = compiler.local_read(arg)
            value = place if place is not None and place.type == typ else compiler.expr(arg, typ)
            code = value.code[1:] if value.code.startswith("&(") else value.code
            return f"&mut {code}"
        if (
            name in compiler.mutable_parameter_functions
            and compiler.function_parameters[name][target] in compiler.mutable_parameter_functions[name]
        ):
            place = compiler.local_read(arg)
            value = place if place is not None and place.type == typ else compiler.expr(arg, typ)
            code = value.code
            if code.startswith("&(") and code.endswith(")"):
                code = code[2:-1]
            elif code.startswith("&"):
                code = code[1:]
            return f"&mut {code}"
        if decisions and decisions[target].mode == "borrow":
            use = runtime_argument_use(RuntimeParameter(str(typ), "shared"), sources, index)
            place = compiler.argument_place(arg, allow_place=use.mode == "borrow")
            value = place if place is not None and place.type == typ else compiler.expr(arg, typ)
            if (
                (
                    name.startswith("py__strategy__random__MapRandom__")
                    or name.startswith("py__openciv3__world_resources__escaped_5f506c6163656d656e74__")
                    and name.rsplit("__", 1)[-1] in {"generate", "appearance", "place_rare", "place_bonus"}
                    or name.startswith("py__openciv3__world_rivers__escaped_5f526976657247726f777468__")
                    and name.rsplit("__", 1)[-1] in {"generate", "flow"}
                    or name.startswith("py__openciv3__turn_controller__TurnController__")
                    and name.rsplit("__", 1)[-1] in {"advance", "autoplay_human_turn", "respond_to_trade"}
                )
                and target == 0
                or typ.name == "py__strategy__random__MapRandom"
            ):
                return f"&mut {value.code}"
            return compiler.reference(value)
        return compiler.expr(arg, typ).code

    if starred:
        start = starred[0]
        item_type = params[start]
        if any(typ != item_type for typ in params[start:]):
            compiler.error(f"unpacked arguments must have one common type: {ast.unparse(node)}", node)
        sequence = compiler.expr(node.args[start].value, Type("list", (item_type,)))
        args = [argument_code(arg, node.args, index, index) for index, arg in enumerate(node.args[:start])]
        compiler.call_counter += 1
        temporary = f"__star_args_{compiler.call_counter}"
        setup = [
            f"let {temporary}: {Type('list', (item_type,)).rust()} = {sequence.code};",
            f"if !({required - start}..={len(params) - start}).contains(&{temporary}.len()) "
            '{ return Err("wrong function argument count".into()); }',
        ]
        for target in range(start, len(params)):
            value = f"rt::at(&{temporary}, {target - start} as i64)?"
            if target < required:
                args.append(value)
                continue
            default = argument_code(defaults[target - required], [node.args[start].value], 0, target)
            args.append(f"if {target - start} < {temporary}.len() {{ {value} }} else {{ {default} }}")
        call = f"{name}({', '.join(args)})"
        return Expr("{ " + " ".join(setup) + " " + call + "? }", result)

    if not node.keywords:
        mutable = compiler.mutable_parameter_functions.get(name, set())
        if mutable:
            compiler.call_counter += 1
            setup = []
            args = [""] * len(node.args)
            for index, arg in enumerate(node.args):
                if compiler.function_parameters[name][index] in mutable:
                    continue
                temporary = f"__call_{compiler.call_counter}_{index}"
                setup.append(f"let {temporary} = {argument_code(arg, node.args, index, index)};")
                args[index] = temporary
            for index, arg in enumerate(node.args):
                if compiler.function_parameters[name][index] not in mutable:
                    continue
                temporary = f"__call_{compiler.call_counter}_{index}"
                setup.append(f"let {temporary} = {argument_code(arg, node.args, index, index)};")
                args[index] = temporary
            sources = [*node.args, *defaults]
            for index in range(len(node.args), len(params)):
                args.append(argument_code(defaults[index - required], sources, index, index))
            call = f"{name}({', '.join(args)})"
            wrapped = "{ " + " ".join(setup) + " " + call + " }"
            return Expr(wrapped + "?", result)
        args = [argument_code(arg, node.args, index, index) for index, arg in enumerate(node.args)]
        sources = [*node.args, *defaults]
        for index in range(len(node.args), len(params)):
            args.append(argument_code(defaults[index - required], sources, index, index))
        call = f"{name}({', '.join(args)})"
        return Expr(call + "?", result, result_call=call if name in compiler.parameter_uses else None)

    names = compiler.function_parameters.get(name, [])
    entries = [(arg, index) for index, arg in enumerate(node.args)]
    selected = {index for _, index in entries}
    for keyword in node.keywords:
        if keyword.arg is None or keyword.arg not in names:
            compiler.error("unknown or unpacked keyword argument", keyword)
        target = names.index(keyword.arg)
        if target in selected:
            compiler.error("duplicate function argument", keyword)
        selected.add(target)
        entries.append((keyword.value, target))
    if any(index not in selected for index in range(required)):
        compiler.error("missing function argument", node)
    sources = [*node.args, *(keyword.value for keyword in node.keywords)]
    compiler.call_counter += 1
    temporary = f"__call_{compiler.call_counter}"
    arguments = {}
    setup = []
    mutable = compiler.mutable_parameter_functions.get(name, set())
    for index, (arg, target) in enumerate(entries):
        if compiler.function_parameters[name][target] in mutable:
            continue
        arguments[target] = f"{temporary}_{index}"
        setup.append(f"let {arguments[target]} = {argument_code(arg, sources, index, target)};")
    for index, (arg, target) in enumerate(entries):
        if compiler.function_parameters[name][target] not in mutable:
            continue
        arguments[target] = f"{temporary}_{index}"
        setup.append(f"let {arguments[target]} = {argument_code(arg, sources, index, target)};")
    for target in range(required, len(params)):
        if target not in arguments:
            arguments[target] = f"{temporary}_default_{target}"
            default = defaults[target - required]
            setup.append(
                f"let {arguments[target]} = {argument_code(default, [*sources, default], len(sources), target)};"
            )
    call = f"{name}({', '.join(arguments[index] for index in range(len(params)))})"
    wrapped = "{ " + " ".join(setup) + " " + call + " }"
    return Expr(wrapped + "?", result)
