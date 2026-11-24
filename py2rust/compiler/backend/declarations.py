"""Validate module declarations for the transitional AST adapter.

This is host-side source admission, separate from portable representation rules.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from ..library_contracts import LIBRARY

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
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            compiler.check_name(node.target.id, node)
            if not isinstance(node.value, ast.Constant) and not (
                isinstance(node.value, ast.UnaryOp)
                and isinstance(node.value.op, ast.USub)
                and isinstance(node.value.operand, ast.Constant)
            ):
                compiler.error("module constants require scalar literals", node)
            typ = compiler.typ(node.annotation)
            if typ.name not in {"str", "bytes", "int", "float", "bool"}:
                compiler.error("module constants require scalar types", node)
            compiler.constants[node.target.id] = compiler.expr(node.value, typ)
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
            compiler.check_name(node.name, node)
            if (
                node.decorator_list
                or node.args.defaults
                or node.args.kw_defaults
                or node.args.vararg
                or node.args.kwarg
                or node.args.kwonlyargs
                or node.args.posonlyargs
                or getattr(node, "type_params", [])
            ):
                compiler.error("unsupported function signature", node)
            signature = (
                tuple(compiler.typ(a.annotation) for a in node.args.args),
                compiler.typ(node.returns),
            )
            if any(t.name == "HttpServer" for t in (*signature[0], signature[1])):
                compiler.error("HTTP listeners stay in the owning function", node)
            compiler.functions[node.name] = signature
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
            compiler.error("unsupported module statement", node)
    if len(mains) != 1:
        compiler.error("exactly one main guard is required", tree)
    return functions, mains[0]
