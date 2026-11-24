"""Evaluate AST expressions with checked signed 64-bit arithmetic and lexical lookup."""

# ruff: noqa: BLE001 - normalize arithmetic failures at their source locations
from syntax import Node

from py2rust.stdlib import Json, int_from_decimal, json_int, json_keys


def scope_index(frames: list[Json], name: str, location: str) -> int:
    index: int = len(frames) - 1
    while index >= 0:
        if name in json_keys(frames[index]):
            return index
        index = index - 1
    assert False, location + "undefined variable: " + name
    return 0


def evaluate(node: Node, frames: list[Json]) -> int:
    if node.kind == "name":
        return json_int(frames[scope_index(frames, node.value, node.location)][node.value])
    left: int = 0
    right: int = 0
    if node.kind in ["unary", "binary"]:
        left = evaluate(node.children[0], frames)
    if node.kind == "binary":
        right = evaluate(node.children[1], frames)
    operator: str = node.value
    assert node.kind != "binary" or operator not in ["//", "%"] or right != 0, node.location + "division by zero"
    try:
        result: int = 0
        if node.kind == "number":
            result = int_from_decimal(node.value)
        elif node.kind == "unary":
            result = left if operator == "+" else -left
        elif operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        elif operator == "*":
            result = left * right
        elif operator == "//":
            result = left // right
        elif operator == "%":
            result = left % right
        elif operator == "==":
            result = 1 if left == right else 0
        elif operator == "!=":
            result = 1 if left != right else 0
        elif operator == "<":
            result = 1 if left < right else 0
        elif operator == "<=":
            result = 1 if left <= right else 0
        elif operator == ">":
            result = 1 if left > right else 0
        elif operator == ">=":
            result = 1 if left >= right else 0
        return int_from_decimal(str(result))
    except Exception:
        assert False, node.location + "integer outside signed 64-bit range"
    return 0
