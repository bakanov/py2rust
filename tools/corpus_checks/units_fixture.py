"""Independent exact-rational SI catalog and AST-based dimensional oracle for application 103."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

BASES = ("m", "kg", "s", "A", "K", "mol", "cd")


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if type(item) is float:
            mantissa, exponent = format(item, ".16e").split("e")
            return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        return json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    return (encode(value) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Measure:
    factor: Fraction
    powers: tuple[int, ...]
    offset: Fraction = Fraction(0)

    def multiply(self, other: Measure) -> Measure:
        assert self.offset == other.offset == 0
        return Measure(self.factor * other.factor, tuple(a + b for a, b in zip(self.powers, other.powers)))

    def power(self, exponent: int) -> Measure:
        assert self.offset == 0
        return Measure(self.factor**exponent, tuple(value * exponent for value in self.powers))


def definitions() -> dict[str, Measure]:
    values = {"1": Measure(Fraction(1), (0,) * 7)}
    for index, name in enumerate(BASES):
        values[name] = Measure(Fraction(1), tuple(int(slot == index) for slot in range(7)))
    for name, base, factor in [
        ("km", "m", "1000"),
        ("cm", "m", "0.01"),
        ("mm", "m", "0.001"),
        ("um", "m", "0.000001"),
        ("nm", "m", "0.000000001"),
        ("in", "m", "0.0254"),
        ("ft", "m", "0.3048"),
        ("yd", "m", "0.9144"),
        ("mi", "m", "1609.344"),
        ("ms", "s", "0.001"),
        ("us", "s", "0.000001"),
        ("min", "s", "60"),
        ("h", "s", "3600"),
        ("d", "s", "86400"),
        ("g", "kg", "0.001"),
        ("mg", "kg", "0.000001"),
        ("lb", "kg", "0.45359237"),
        ("mA", "A", "0.001"),
        ("delta_degC", "K", "1"),
        ("delta_degF", "K", "5/9"),
    ]:
        values[name] = Measure(Fraction(factor), values[base].powers)
    for name, expression in [
        ("Hz", "1/s"),
        ("N", "kg*m/s^2"),
        ("Pa", "N/m^2"),
        ("J", "N*m"),
        ("W", "J/s"),
        ("C", "A*s"),
        ("V", "W/A"),
        ("ohm", "V/A"),
    ]:
        values[name] = parse(expression, values)
    for name, base, factor in [
        ("kPa", "Pa", "1000"),
        ("bar", "Pa", "100000"),
        ("atm", "Pa", "101325"),
        ("kJ", "J", "1000"),
        ("kW", "W", "1000"),
    ]:
        values[name] = Measure(Fraction(factor), values[base].powers)
    volume = values["m"].power(3)
    values["L"] = Measure(Fraction(1, 1000), volume.powers)
    values["mL"] = Measure(Fraction(1, 10**6), volume.powers)
    values["degC"] = Measure(Fraction(1), values["K"].powers, Fraction(27315, 100))
    values["degF"] = Measure(Fraction(5, 9), values["K"].powers, Fraction(45967, 180))
    return values


def parse(expression: str, available: dict[str, Measure] | None = None) -> Measure:
    available = definitions() if available is None else available
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[*/()^+-]", expression)
    assert "".join(tokens) == expression.replace(" ", "").replace("\t", "")
    if expression.strip() in {"degC", "degF"}:
        return available[expression.strip()]
    rewritten = " ".join(
        "**" if token == "^" else "inch" if token == "in" else str(int(token)) if token.isdigit() else token
        for token in tokens
    )

    def evaluate(node: ast.AST) -> Measure:
        if isinstance(node, ast.Name):
            value = available["in" if node.id == "inch" else node.id]
            assert value.offset == 0
            return value
        if isinstance(node, ast.Constant):
            assert type(node.value) is int and node.value == 1
            return available["1"]
        assert isinstance(node, ast.BinOp)
        left = evaluate(node.left)
        if isinstance(node.op, ast.Pow):
            exponent = ast.literal_eval(node.right)
            assert type(exponent) is int and -8 <= exponent <= 8
            return left.power(exponent)
        right = evaluate(node.right)
        assert isinstance(node.op, (ast.Mult, ast.Div))
        return left.multiply(right if isinstance(node.op, ast.Mult) else right.power(-1))

    return evaluate(ast.parse(rewritten, mode="eval").body)


def dimension_name(powers: tuple[int, ...]) -> str:
    return (
        "*".join(name if power == 1 else name + "^" + str(power) for name, power in zip(BASES, powers) if power) or "1"
    )


def close(actual: float, expected: Fraction, absolute: float = 0.0) -> None:
    assert type(actual) is float and math.isfinite(actual)
    assert math.isclose(actual, float(expected), rel_tol=2e-12, abs_tol=absolute), (actual, expected)
    return  # noqa: PLR1711


def inspect_unit(actual: dict, expected: Measure) -> None:
    assert actual.keys() == {"factor", "offset", "dimensions", "base_unit"}
    close(actual["factor"], expected.factor)
    close(actual["offset"], expected.offset)
    assert all(type(power) is int for power in actual["dimensions"])
    assert tuple(actual["dimensions"]) == expected.powers
    assert actual["base_unit"] == dimension_name(expected.powers)
    return  # noqa: PLR1711


def inspect_entry(entry: dict) -> Fraction:
    assert entry.keys() == {"request", "result"}
    request, result = entry["request"], entry["result"]
    assert request.keys() == {"id", "quantity", "to"}
    match = re.fullmatch(r"([^ \t]+)[ \t]+(.+)", request["quantity"].strip(" \t"))
    assert match
    quantity = Fraction(match[1].replace("_", ""))
    source, target = parse(match[2]), parse(request["to"])
    assert source.powers == target.powers
    assert result.keys() == {
        "value",
        "source_unit",
        "target_unit",
        "source",
        "target",
        "base_value",
        "converted",
        "round_trip",
    }
    assert (
        result["value"] == float(match[1])
        and result["source_unit"] == match[2]
        and result["target_unit"] == request["to"]
    )
    inspect_unit(result["source"], source)
    inspect_unit(result["target"], target)
    physical = quantity * source.factor + source.offset
    expected = (physical - target.offset) / target.factor
    close(result["base_value"], physical, 1e-12 if source.offset else 0.0)
    close(result["converted"], expected, 1e-12 if source.offset or target.offset else 0.0)
    round_trip = result["round_trip"]
    assert round_trip.keys() == {"value", "error", "tolerance"}
    assert all(type(value) is float and math.isfinite(value) for value in round_trip.values())
    assert round_trip["error"] == abs(round_trip["value"] - result["value"])
    assert round_trip["tolerance"] == max(1e-12, abs(result["value"]) * 1e-12)
    assert 0 <= round_trip["error"] <= round_trip["tolerance"]
    return expected


def conversion(name: str, quantity: str, destination: str) -> dict:
    return {"id": name, "quantity": quantity, "to": destination}


def fixtures() -> list[dict]:
    return [
        conversion("length", "12 in", "ft"),
        conversion("speed", "90 km/h", "m/s"),
        conversion("area", "1 mi^2", "km^2"),
        conversion("volume", "2 L", "cm^3"),
        conversion("mass", "10 lb", "kg"),
        conversion("force", "12 kg*m/s^2", "N"),
        conversion("pressure", "1 atm", "kPa"),
        conversion("energy", "2 kW*h", "kJ"),
        conversion("electric", "3 V/A", "ohm"),
        conversion("charge", "4 A*h", "C"),
        conversion("molar", "2 mol/L", "mol/m^3"),
        conversion("light", "6 cd", "cd"),
        conversion("celsius", "0 degC", "K"),
        conversion("fahrenheit", "32 degF", "degC"),
        conversion("cold", "-40 degF", "degC"),
        conversion("kelvin", "273.15 K", "degF"),
        conversion("difference", "18 delta_degF/min", "K/s"),
        conversion("reciprocal", "2 s^-1", "Hz"),
        conversion("nested", "1 (kg*(m/s)^2)/s", "W"),
        conversion("inverse_power", "2 (m/s)^-2", "s^2/m^2"),
        conversion("zero_power", "1 (m/s)^0", "1"),
        conversion("dimensionless", "2 (km/m)^2", "1"),
        conversion("decimal", "\t+.5_0e+2\tcm\t", "m"),
        conversion("left_assoc", "1 m/s/s", "m/s^2"),
        conversion("parentheses", "1 m/(s/s)", "m"),
        conversion("zero", "-0e9999 m", "km"),
        conversion("tiny", "1e-100 m", "m"),
        conversion("huge", "1e100 m", "m"),
    ]
