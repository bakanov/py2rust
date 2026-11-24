"""Checked signed integer and finite binary64 arithmetic with stable expression errors."""

# ruff: noqa: BLE001 - normalize backend arithmetic errors at the operator location
from lexing import location

from py2rust.stdlib import (
    Json,
    json_canonical,
    json_float,
    json_int,
    json_kind,
    json_loads,
)


def integer(value: Json) -> bool:
    """Canonical JSON marks every floating value with an exponent, including 1.0."""
    return "e" not in json_canonical(value)


def literal(text: str, column: int) -> Json:
    try:
        value: Json = json_loads(text)
        assert json_kind(value) == "number", "expected number"
        return value
    except Exception:
        assert False, location(column) + "invalid or out-of-range number"
    return None


def unary(operator: str, value: Json, column: int) -> Json:
    if operator == "+":
        return value
    try:
        result: Json = None
        if integer(value):
            whole: int = json_int(value)
            result = -whole
        else:
            real: float = json_float(value)
            result = -real
        json_canonical(result)
        return result
    except Exception:
        assert False, location(column) + "arithmetic result outside numeric range"
    return None


def combine(operator: str, left: Json, right: Json, column: int) -> Json:
    both: bool = integer(left) and integer(right)
    assert operator not in ["//", "%"] or both, location(column) + "floor division and remainder require integers"
    assert operator not in ["/", "//", "%"] or json_float(right) != 0.0, location(column) + "division by zero"
    try:
        result: Json = None
        if both:
            a: int = json_int(left)
            b: int = json_int(right)
            if operator == "+":
                result = a + b
            elif operator == "-":
                result = a - b
            elif operator == "*":
                result = a * b
            elif operator == "/":
                result = a / b
            elif operator == "//":
                result = a // b
            else:
                result = a % b
        else:
            x: float = json_float(left)
            y: float = json_float(right)
            if operator == "+":
                result = x + y
            elif operator == "-":
                result = x - y
            elif operator == "*":
                result = x * y
            else:
                result = x / y
        json_canonical(result)
        return result
    except Exception:
        assert False, location(column) + "arithmetic result outside numeric range"
    return None
