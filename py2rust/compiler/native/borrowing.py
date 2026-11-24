"""Conservative shared parameter selection for native emission.

The backend still owns local values and return values. Only parameters that are
never rebound or mutated can borrow their caller's storage. Call-site evaluation
must separately preserve snapshots when later arguments can have effects.
"""

from py2rust.stdlib import Json, json_array, json_int, json_string

from .types import type_name


def expression_writes(nodes: list[Json], index: int, name: str) -> bool:
    node: Json = nodes[index]
    operands: list[Json] = json_array(node["operands"])
    if json_string(node["operation"]) == "method_call" and len(operands) > 0:
        receiver: Json = nodes[json_int(operands[0])]
        if json_string(receiver["operation"]) == "name" and json_string(receiver["value"]["text"]) == name:
            method: str = json_string(node["value"]["text"])
            if method in [
                "append",
                "extend",
                "insert",
                "pop",
                "reverse",
                "clear",
                "add",
                "remove",
                "discard",
                "update",
            ]:
                return True
    for operand in operands:
        if expression_writes(nodes, json_int(operand), name):
            return True
    return False


def block_writes(nodes: list[Json], body: list[Json], name: str) -> bool:
    for reference in body:
        node: Json = nodes[json_int(reference)]
        operation: str = json_string(node["operation"])
        if operation in ["assign", "for"] and json_string(node["target"]) == name:
            return True
        expressions: list[Json] = json_array(node["expressions"])
        if operation in ["store_index", "delete_index"]:
            position: int = 1 if operation == "store_index" else 0
            receiver: Json = nodes[json_int(expressions[position])]
            if json_string(receiver["operation"]) == "name" and json_string(receiver["value"]["text"]) == name:
                return True
        for expression in expressions:
            if expression_writes(nodes, json_int(expression), name):
                return True
        for block in json_array(node["blocks"]):
            if block_writes(nodes, json_array(block), name):
                return True
    return False


def parameter_borrowed(nodes: list[Json], declaration: Json, parameter: Json) -> bool:
    kind: str = type_name(nodes, json_int(parameter["type"]))
    # Resource handles and records need their own alias/ABI policy. Scalar values
    # are cheap to copy. This initial proof covers owned value collections only.
    if kind not in ["str", "bytes", "bytearray", "list", "dict", "set", "tuple", "Json"]:
        return False
    return not block_writes(nodes, json_array(declaration["body"]), json_string(parameter["name"]))
