"""Independent exact-rational population statistics and high-precision outlier oracle."""

from __future__ import annotations

import datetime as dt
import decimal
import hashlib
import json
import math
from fractions import Fraction
from functools import lru_cache
from typing import Any

EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
START = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


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


def series(name: str, values: list, ticks: list[int] | None = None) -> dict:
    ticks = list(range(len(values))) if ticks is None else ticks
    return {
        "id": name,
        "samples": [
            {"at": (START + dt.timedelta(seconds=t)).isoformat(), "value": value} for value, t in zip(values, ticks)
        ],
    }


def document(rows: list | None = None, **settings: object) -> dict:
    return {
        "version": 1,
        "settings": {"window": 4, "warmup": 3, "gap_us": 3000000, "sigma": "3", **settings},
        "series": fixtures() if rows is None else rows,
    }


def fixtures() -> list[dict]:
    offsets = {
        "id": "offsets",
        "samples": [
            {"at": "1969-12-31T19:00:00-05:00", "value": -1.0},
            {"at": "1970-01-01T05:00:00.000001+05:00", "value": 0},
            {"at": "1970-01-01T00:00:03.000001Z", "value": 1},
            {"at": "1970-01-01T00:00:06.000003Z", "value": "+2_0.0"},
        ],
    }
    return [
        series("latency", [10, 11, 9, 10, 50, 10, 10, 10], [0, 1, 2, 3, 4, 5, 12, 13]),
        series("constant", [5, 5, 5, 5, 6, 5, 5, 5]),
        series("empty", []),
        series("single", [1.25]),
        series("large_offset", [1e16, 1e16 + 2, 1e16, 1e16 + 2, 1e16 + 8]),
        series("cancellation", [1e100, 1, -1e100, 2, -2, 0]),
        series("tiny", [1e-100, 2e-100, 1e-100, 2e-100, 9e-100]),
        offsets,
    ]


def reading(row: dict) -> tuple[int, str, float]:
    time = dt.datetime.fromisoformat(row["at"]).astimezone(dt.timezone.utc)
    delta = time - EPOCH
    micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    value = float(row["value"])
    return micros, time.isoformat(timespec="microseconds"), 0.0 if value == 0.0 else value


def dec(value: Fraction) -> decimal.Decimal:
    return decimal.Decimal(value.numerator) / decimal.Decimal(value.denominator)


@lru_cache(maxsize=8192)
def truth(values: tuple[float, ...]) -> tuple[Fraction, Fraction, decimal.Decimal]:
    numbers = [Fraction.from_float(value) for value in values]
    mean = sum(numbers) / len(numbers)
    variance = sum((value - mean) ** 2 for value in numbers) / len(numbers)
    with decimal.localcontext() as context:
        context.prec = 80
        deviation = dec(variance).sqrt()
    return mean, variance, deviation


def near(actual: Any, expected: float, tolerance: float) -> None:
    assert type(actual) is float and math.isfinite(actual)
    assert abs(actual - expected) <= tolerance, (actual, expected, tolerance)
    return  # noqa: PLR1711


def inspect_statistics(actual: dict, values: list[float]) -> None:
    assert actual.keys() == {
        "count",
        "minimum",
        "maximum",
        "mean",
        "population_variance",
        "standard_deviation",
        "center",
    }
    assert type(actual["count"]) is int and actual["count"] == len(values)
    if not values:
        assert all(value is None for name, value in actual.items() if name != "count")
        return
    mean, variance, deviation = truth(tuple(values))
    magnitude = max(abs(value) for value in values)
    span = max(values) - min(values)
    for name, target in [("minimum", min(values)), ("maximum", max(values))]:
        assert type(actual[name]) is float and actual[name].hex() == target.hex()
    near(actual["mean"], float(mean), max(magnitude * 5e-15, 8 * math.ulp(float(mean))))
    near(actual["population_variance"], float(variance), float(variance) * 2e-12)
    near(actual["standard_deviation"], float(deviation), float(deviation) * 2e-12)
    center = actual["center"]
    assert center.keys() == {"origin", "mean_offset"}
    assert all(type(value) is float and math.isfinite(value) for value in center.values())
    reconstructed = Fraction.from_float(center["origin"]) + Fraction.from_float(center["mean_offset"])
    assert abs(float(reconstructed - mean)) <= span * 2e-14, (center, mean, span)
    if variance == 0:
        assert actual["population_variance"] == actual["standard_deviation"] == 0.0
    return


def inspect_decision(actual: dict, value: float, baseline: list[float], settings: dict) -> None:
    assert actual.keys() == {"status", "deviation", "threshold", "z_score"}
    if len(baseline) < settings["warmup"]:
        assert actual == {"status": "warming", "deviation": None, "threshold": None, "z_score": None}
        return
    mean, variance, deviation = truth(tuple(baseline))
    distance = Fraction.from_float(value) - mean
    span = max([value, *baseline]) - min([value, *baseline])
    near(actual["deviation"], float(distance), span * 2e-14)
    if variance == 0:
        assert actual["status"] == ("within" if distance == 0 else "constant_shift")
        assert type(actual["threshold"]) is float and actual["threshold"] == 0.0 and actual["z_score"] is None
        return
    with decimal.localcontext() as context:
        context.prec = 80
        threshold = decimal.Decimal.from_float(float(settings["sigma"])) * deviation
        score = dec(distance) / deviation
        margin = abs(dec(distance)) - threshold
    near(actual["threshold"], float(threshold), float(threshold) * 2e-12)
    near(actual["z_score"], float(score), max(1.0, abs(float(score))) * 2e-12)
    # The contract uses the reported binary64 deviation and threshold. An exact
    # classification is additionally required when the margin exceeds rounding tolerance.
    expected = "outlier" if abs(actual["deviation"]) > actual["threshold"] else "within"
    assert actual["status"] == expected
    if abs(float(margin)) > max(float(threshold), span) * 2e-12:
        assert expected == ("outlier" if margin > 0 else "within")
    return


def inspect_series(source: dict, actual: dict, settings: dict) -> int:
    assert actual.keys() == {
        "id",
        "status",
        "samples",
        "segments",
        "outliers",
        "first_utc",
        "last_utc",
        "statistics",
        "gaps",
        "points",
    }
    readings = [reading(row) for row in source["samples"]]
    assert actual["id"] == source["id"] and actual["status"] == "analyzed"
    assert type(actual["samples"]) is int and actual["samples"] == len(readings) == len(actual["points"])
    assert actual["first_utc"] == (readings[0][1] if readings else None)
    assert actual["last_utc"] == (readings[-1][1] if readings else None)
    inspect_statistics(actual["statistics"], [row[2] for row in readings])
    window, gaps, outliers, segment = [], [], 0, 0
    for index, (sample, point) in enumerate(zip(readings, actual["points"])):
        micros, utc, value = sample
        elapsed = None if index == 0 else micros - readings[index - 1][0]
        gap = elapsed is not None and elapsed > settings["gap_us"]
        if gap:
            gaps.append(
                {
                    "before_index": index - 1,
                    "after_index": index,
                    "elapsed_us": elapsed,
                    "from": readings[index - 1][1],
                    "to": utc,
                }
            )
            window = []
            segment += 1
        assert point.keys() == {
            "index",
            "utc",
            "timestamp_us",
            "value",
            "segment",
            "elapsed_us",
            "gap",
            "baseline",
            "decision",
            "window",
        }
        header = {
            "index": index,
            "utc": utc,
            "timestamp_us": micros,
            "value": value,
            "segment": segment,
            "elapsed_us": elapsed,
            "gap": gap,
        }
        assert canonical({key: point[key] for key in header}) == canonical(header)
        before = point["baseline"]
        assert before.keys() == {"start_index", "end_index", "statistics"}
        assert before["start_index"] == (index - len(window) if window else None)
        assert before["end_index"] == (index - 1 if window else None)
        inspect_statistics(before["statistics"], window)
        inspect_decision(point["decision"], value, window, settings)
        outliers += point["decision"]["status"] in ["outlier", "constant_shift"]
        window = [*window, value][-settings["window"] :]
        after = point["window"]
        assert after.keys() == {"start_index", "end_index", "statistics"}
        assert type(after["start_index"]) is int and type(after["end_index"]) is int
        assert after["start_index"] == index + 1 - len(window) and after["end_index"] == index
        inspect_statistics(after["statistics"], window)
    assert canonical(actual["gaps"]) == canonical(gaps)
    assert type(actual["segments"]) is int and actual["segments"] == (segment + 1 if readings else 0)
    assert type(actual["outliers"]) is int and actual["outliers"] == outliers
    return len(readings)
