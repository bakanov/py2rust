"""Bounded binary64 domains, decimal nice steps and exact integer-derived tick labels."""

from dataclasses import dataclass

from py2rust.stdlib import Json, ceil, floor


@dataclass
class Scale:
    low: float
    high: float
    step: float
    first: int
    last: int
    factor: int
    exponent: int


def tick_label(units: int, exponent: int) -> str:
    if units == 0:
        return "0"
    sign: str = "-" if units < 0 else ""
    units = abs(units)
    while units % 10 == 0:
        units = units // 10
        exponent = exponent + 1
    zeros: str = ""
    for zero in range(abs(exponent)):
        zeros = zeros + "0"
    digits: str = str(units)
    if exponent >= 0 and len(digits) + exponent <= 12:
        return sign + digits + zeros
    if -6 <= exponent < 0 and len(digits) <= 12:
        point: int = len(digits) + exponent
        return sign + (digits[:point] + "." + digits[point:] if point > 0 else "0." + zeros[:-point] + digits)
    mantissa: str = digits[:1] + ("." + digits[1:] if len(digits) > 1 else "")
    return sign + mantissa + "e" + str(exponent + len(digits) - 1)


def scale(values: list[float], kind: str) -> Scale:
    low: float = min(values) if len(values) > 0 else 0.0
    high: float = max(values) if len(values) > 0 else 0.0
    if kind == "bar":
        low = min(low, 0.0)
        high = max(high, 0.0)
    magnitude: float = max(abs(low), abs(high))
    if magnitude == 0.0:
        low = -1.0
        high = 1.0
    elif high - low <= magnitude * 1e-12:
        radius: float = magnitude * 0.05
        low = low - radius
        high = high + radius
    elif kind == "line":
        padding: float = (high - low) * 0.05
        low = low - padding
        high = high + padding
    target: float = (high - low) / 4.0
    exponent: int = 0
    power: float = 1.0
    while power > target:
        exponent = exponent - 1
        power = float("1e" + str(exponent))
    while power * 10.0 <= target:
        exponent = exponent + 1
        power = float("1e" + str(exponent))
    factor: int = 1 if target <= power else (2 if target <= power * 2.0 else (5 if target <= power * 5.0 else 10))
    if factor == 10:
        factor = 1
        exponent = exponent + 1
    step: float = float(str(factor) + "e" + str(exponent))
    first: int = floor(low / step)
    last: int = ceil(high / step)
    while float(first) * step > low:
        first = first - 1
    while float(last) * step < high:
        last = last + 1
    return Scale(float(first) * step, float(last) * step, step, first, last, factor, exponent)


def ordinate(value: float, axis: Scale) -> int:
    return max(104, min(304, floor(304.0 - 200.0 * ((value - axis.low) / (axis.high - axis.low)) + 0.5)))


def ticks(axis: Scale) -> list[Json]:
    result: list[Json] = []
    for index in range(axis.first, axis.last + 1):
        value: float = float(index) * axis.step
        result.append(
            {"value": value, "label": tick_label(index * axis.factor, axis.exponent), "y": ordinate(value, axis)}
        )
    return result
