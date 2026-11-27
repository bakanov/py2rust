"""Validate module declarations for the transitional AST adapter.

This is host-side source admission, separate from portable representation rules.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..library_contracts import LIBRARY
from .values import Type

if TYPE_CHECKING:
    from ..service import ServiceCompiler


def collect_declarations(compiler: ServiceCompiler, tree: ast.Module) -> tuple[list[ast.FunctionDef], ast.If]:
    functions, mains = [], []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            names = {n.name for n in node.names}
            if any(n.asname for n in node.names) or node.level:
                compiler.error("import aliases and relative imports are unsupported", node)
            if node.module == "py2rust.stdlib" and names <= {
                *LIBRARY,
                "Json",
                "DateTime",
                "Rational",
                "HttpServer",
                "HttpResponse",
                "http_serve_json",
                "http_serve_json_timeout",
                "WebRequest",
                "WebResponse",
                "StreamChunk",
                "FileHandle",
                "GzipReader",
                "GzipWriter",
                "LineReader",
                "HttpReader",
                "TcpListener",
                "TcpStream",
                "UnixListener",
                "UnixStream",
                "UdpSocket",
                "ProcessPool",
                "Sha256",
                "web_serve",
                "web_serve_stream",
                "parallel_map",
            }:
                compiler.imports.update(names)
            elif node.module == "enum" and names == {"Enum"}:
                compiler.imports.add("Enum")
            elif node.module == "dataclasses" and names == {"dataclass"}:
                compiler.imports.add("dataclass")
            else:
                compiler.error("unsupported import; use the service library contract", node)
        elif isinstance(node, ast.Import):
            if any(
                n.asname
                or n.name
                not in {
                    "json",
                    "time",
                    "logging",
                    "pprint",
                    "sys",
                    "hmac",
                    "math",
                    "unicodedata",
                    "heapq",
                    "zlib",
                    "binascii",
                }
                for n in node.names
            ):
                compiler.error("unsupported module import", node)
            compiler.modules.update(n.name for n in node.names)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0]
            compiler.check_name(target.id, target)
            expression = compiler.expr(node.value)
            compiler.constants[target.id] = expression
            compiler.constant_nodes[target.id] = (node.value, expression.type)
        elif (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Tuple)
            and isinstance(node.value, ast.Tuple)
            and len(node.targets[0].elts) == len(node.value.elts)
        ):
            for target, value in zip(node.targets[0].elts, node.value.elts):
                if not isinstance(target, ast.Name):
                    compiler.error("module tuple constants require named targets", target)
                compiler.check_name(target.id, target)
                expression = compiler.expr(value)
                compiler.constants[target.id] = expression
                compiler.constant_nodes[target.id] = (value, expression.type)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            compiler.check_name(node.target.id, node)
            typ = compiler.typ(node.annotation)
            compiler.constant_nodes[node.target.id] = (node.value, typ)
        elif isinstance(node, ast.ClassDef):
            if node.decorator_list:
                compiler.record_definition(node)
                continue
            if (
                "Enum" not in compiler.imports
                or len(node.bases) != 1
                or ast.unparse(node.bases[0]) != "Enum"
                or node.decorator_list
                or node.keywords
            ):
                compiler.error("only simple Enum classes are supported", node)
            compiler.check_name(node.name, node)
            values = {}
            for member in node.body:
                if (
                    not isinstance(member, ast.Assign)
                    or len(member.targets) != 1
                    or not isinstance(member.targets[0], ast.Name)
                    or not isinstance(member.value, ast.Constant)
                    or type(member.value.value) not in {str, int}
                ):
                    compiler.error("enum members need explicit str or int literals", member)
                compiler.check_name(member.targets[0].id, member)
                if member.targets[0].id in values:
                    compiler.error("duplicate enum member name", member)
                if type(member.value.value) is int and not -(2**63) <= member.value.value < 2**63:
                    compiler.error("enum integer must fit signed 64 bits", member)
                values[member.targets[0].id] = member.value.value
            if not values or len(set(values.values())) != len(values) or len({type(v) for v in values.values()}) != 1:
                compiler.error("enum values must be unique and have one type", node)
            compiler.enums[node.name] = values
        elif isinstance(node, ast.FunctionDef):
            if node.name in {"py2rust__stdlib__Random__shuffle", "py__strategy__random__MapRandom__shuffle"}:
                continue  # Calls are emitted as type-specific intrinsic loops.
            compiler.check_name(node.name, node)
            if (
                node.decorator_list
                or node.args.kw_defaults
                or node.args.vararg
                or node.args.kwarg
                or node.args.kwonlyargs
                or node.args.posonlyargs
                or getattr(node, "type_params", [])
            ):
                compiler.error("unsupported function signature", node)
            try:
                signature = (
                    tuple(compiler.typ(a.annotation) for a in node.args.args),
                    compiler.typ(node.returns),
                )
            except Exception as error:
                annotations = [ast.unparse(argument.annotation) for argument in node.args.args]
                compiler.error(
                    f"unsupported signature in {node.name}({', '.join(annotations)}) -> "
                    f"{ast.unparse(node.returns)}: {error}",
                    node,
                )
            post_init_suffix = "escaped_5f5f706f73745f696e69745f5f"
            if node.name.endswith(post_init_suffix):
                record_name = node.name.removesuffix(post_init_suffix).removesuffix("__")
                signature = (signature[0], Type(record_name))
                node.body.append(ast.Return(value=ast.Name(id="self_", ctx=ast.Load())))
            if any(t.name == "HttpServer" for t in (*signature[0], signature[1])):
                compiler.error("HTTP listeners stay in the owning function", node)
            compiler.functions[node.name] = signature
            compiler.function_parameters[node.name] = [argument.arg for argument in node.args.args]
            compiler.function_defaults[node.name] = tuple(node.args.defaults)
            functions.append(node)
        elif (
            isinstance(node, ast.If)
            and ast.unparse(node.test) in {"__name__ == '__main__'", '__name__ == "__main__"'}
            and not node.orelse
        ):
            mains.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue  # Module documentation has no runtime effect.
        else:
            compiler.error(f"unsupported module statement: {ast.unparse(node)}", node)
    if len(mains) != 1:
        compiler.error("exactly one main guard is required", tree)
    return functions, mains[0]
