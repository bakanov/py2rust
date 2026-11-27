"""Bounded successful-result caching for closed, deterministic string parsers."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler

BUILTINS = {"int", "float", "bool", "str", "len", "range", "abs", "min", "max", "sorted", "list", "tuple"}
METHODS = {"split", "strip", "lstrip", "rstrip", "lower", "upper", "startswith", "endswith", "append", "pop"}


def copy_result(value: Type) -> bool:
    return value.name in {"int", "float", "bool"} or (
        value.name == "tuple" and bool(value.args) and all(copy_result(item) for item in value.args)
    )


def parser_parameter(compiler: ServiceCompiler, function: ast.FunctionDef) -> str | None:
    types, result = compiler.functions[function.name]
    if not compiler.optimize or types != (Type("str"),) or not copy_result(result):
        return None
    parameter = function.args.args[0].arg
    nodes = [node for statement in function.body for node in ast.walk(statement)]
    if (
        parameter not in compiler.borrowed_str_parameters
        or parameter in compiler.mutable_bindings
        or any(
            isinstance(
                node,
                (
                    ast.Try,
                    ast.With,
                    ast.Raise,
                    ast.Global,
                    ast.Nonlocal,
                    ast.Lambda,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Await,
                    ast.Yield,
                    ast.YieldFrom,
                    ast.Delete,
                ),
            )
            for node in nodes
        )
    ):
        return None
    locals_ = {
        parameter,
        *(node.id for node in nodes if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)),
    }
    parents = {id(child): node for node in nodes for child in ast.iter_child_nodes(node)}
    expensive = False
    for node in nodes:
        if isinstance(node, ast.For):
            expensive = True
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if "__block_" in node.id:
                continue
            if node.id not in locals_ | BUILTINS | {"regex_fullmatch"}:
                return None  # No globals, callbacks, environmental state or unknown callees.
        if isinstance(node, ast.Attribute):
            parent = parents.get(id(node))
            if not (isinstance(parent, ast.Call) and parent.func is node and node.attr in METHODS):
                return None
            if not isinstance(node.value, ast.Name) or node.value.id not in locals_:
                return None
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in locals_ or name in compiler.functions:
                    return None
                if name == "regex_fullmatch" and name in compiler.imports:
                    expensive = True
                elif name not in BUILTINS:
                    return None
            elif not isinstance(node.func, ast.Attribute):
                return None
    return parameter if expensive else None


def wrap_parser(compiler: ServiceCompiler, function: ast.FunctionDef, body: list[str]) -> list[str]:
    parameter = parser_parameter(compiler, function)
    if parameter is None:
        return body
    used = {node.id for node in ast.walk(function) if isinstance(node, ast.Name)} | {parameter}
    name = "PARSER_CACHE"
    while name in used:
        name += "_"
    result = compiler.result.rust()
    key = parameter if parameter in compiler.borrowed_str_parameters else f"&{parameter}"
    compiler.record_decision(function, "deterministic_parser", "bounded_memoization", "closed_string_input_copy_result")
    return [
        f"static {name}: rt::MemoCache<{result}> = rt::MemoCache::new();",
        f"rt::memoized(&{name}, {key}, || -> rt::Result<{result}> {{",
        *body,
        "})",
    ]
