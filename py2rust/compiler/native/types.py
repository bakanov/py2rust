"""Typed representations shared by native IR traversal and declarations."""

from py2rust.stdlib import Json, json_array, json_int, json_string

from ..rules.types import render_owned_type
from .names import symbol
from .source_types import runtime_handle


def type_name(nodes: list[Json], index: int) -> str:
    name: str = json_string(nodes[index]["name"])
    if name.startswith("builtins."):
        return name[9:]
    if name.startswith("py2rust.stdlib.") and runtime_handle(name[15:]):
        return name[15:]
    if name == "py2rust.stdlib.Json":
        return "Json"
    return name


def rust_type(nodes: list[Json], index: int, definitions: dict[str, int]) -> str:
    name: str = type_name(nodes, index)
    if name in definitions and json_string(nodes[definitions[name]]["kind"]) == "Record":
        return symbol(name)
    assert name in [
        "int",
        "float",
        "bool",
        "str",
        "None",
        "list",
        "dict",
        "set",
        "tuple",
        "bytes",
        "bytearray",
        "Json",
        "TcpListener",
        "TcpStream",
    ], (
        "native emitter type not implemented: " + name
    )
    arguments: list[str] = []
    for argument in json_array(nodes[index]["arguments"]):
        arguments.append(rust_type(nodes, json_int(argument), definitions))
    if name == "tuple" and len(arguments) == 0:
        return "()"
    return render_owned_type(name, arguments)
