"""Compensated sums and centered two-pass population variance for bounded telemetry windows."""

import math
from dataclasses import dataclass

from py2rust.stdlib import Json


@dataclass
class Moments:
    count: int
    minimum: float
    maximum: float
    mean: float
    origin: float
    offset: float
    variance: float
    deviation: float


def summed(values: list[float]) -> float:
    total: float = 0.0
    correction: float = 0.0
    for value in values:
        updated: float = total + value
        if abs(total) >= abs(value):
            correction = correction + ((total - updated) + value)
        else:
            correction = correction + ((value - updated) + total)
        total = updated
    return total + correction


def calculate(values: list[float]) -> Moments:
    count: int = len(values)
    if count == 0:
        return Moments(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    minimum: float = min(values)
    maximum: float = max(values)
    origin: float = minimum / 2.0 + maximum / 2.0
    deltas: list[float] = []
    for value in values:
        deltas.append(value - origin)
    offset: float = summed(deltas) / float(count)
    squares: list[float] = []
    for delta in deltas:
        residual: float = delta - offset
        squares.append(residual * residual)
    variance: float = summed(squares) / float(count)
    mean: float = summed(values) / float(count)
    return Moments(count, minimum, maximum, 0.0 if mean == 0.0 else mean, origin, offset, variance, math.sqrt(variance))


def describe(value: Moments) -> Json:
    if value.count == 0:
        return {
            "count": 0,
            "minimum": None,
            "maximum": None,
            "mean": None,
            "population_variance": None,
            "standard_deviation": None,
            "center": None,
        }
    return {
        "count": value.count,
        "minimum": value.minimum,
        "maximum": value.maximum,
        "mean": value.mean,
        "population_variance": value.variance,
        "standard_deviation": value.deviation,
        "center": {"origin": value.origin, "mean_offset": value.offset},
    }


def classify(value: float, baseline: Moments, warmup: int, sigma: float) -> Json:
    if baseline.count < warmup:
        return {"status": "warming", "deviation": None, "threshold": None, "z_score": None}
    difference: float = (value - baseline.origin) - baseline.offset
    difference = 0.0 if difference == 0.0 else difference
    if baseline.deviation == 0.0:
        return {
            "status": "within" if difference == 0.0 else "constant_shift",
            "deviation": difference,
            "threshold": 0.0,
            "z_score": None,
        }
    threshold: float = sigma * baseline.deviation
    return {
        "status": "outlier" if abs(difference) > threshold else "within",
        "deviation": difference,
        "threshold": threshold,
        "z_score": difference / baseline.deviation,
    }
