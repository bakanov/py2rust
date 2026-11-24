"""Portable type construction shared by source checks and runtime contracts."""

from py2rust.stdlib import Json, json_array, json_string


def runtime_handle(name: str) -> bool:
    return name in ["TcpListener", "TcpStream"]


def contains_runtime_handle(typ: Json) -> bool:
    name: str = json_string(typ["name"])
    if name.startswith("py2rust.stdlib.") and runtime_handle(name[15:]):
        return True
    for argument in json_array(typ["arguments"]):
        if contains_runtime_handle(argument):
            return True
    return False


def contract_type(spelling: str) -> Json:
    if runtime_handle(spelling):
        return {"kind": "ValueType", "name": "py2rust.stdlib." + spelling, "arguments": []}
    if spelling == "Json":
        return {"kind": "ValueType", "name": "py2rust.stdlib.Json", "arguments": []}
    if spelling == "None":
        return {"kind": "ValueType", "name": "None", "arguments": []}
    if spelling in ["int", "float", "bool", "str", "bytes", "bytearray"]:
        return {"kind": "ValueType", "name": "builtins." + spelling, "arguments": []}
    opening: int = spelling.find("[")
    assert opening > 0 and spelling.endswith("]"), "native source runtime type unsupported: " + spelling
    container: str = spelling[:opening]
    assert container in ["list", "dict", "set", "tuple"], "native source runtime container unsupported"
    contents: str = spelling[opening + 1 : -1]
    arguments: list[Json] = []
    depth: int = 0
    start: int = 0
    for index in range(len(contents)):
        character: str = contents[index]
        if character == "[":
            depth = depth + 1
        elif character == "]":
            depth = depth - 1
        elif character == "," and depth == 0:
            arguments.append(contract_type(contents[start:index]))
            start = index + 1
    arguments.append(contract_type(contents[start:]))
    return {"kind": "ValueType", "name": "builtins." + container, "arguments": arguments}
