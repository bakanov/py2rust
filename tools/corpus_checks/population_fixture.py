"""Closed-form Decimal oracles and structural inspection of population exports; no application imports."""

from __future__ import annotations

import csv
import decimal
import hashlib
import io
import itertools
import json
import math
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if type(item) is float:
            assert math.isfinite(item)
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


def display(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def case(
    identifier: str, initial: float = 100.0, rate: float = 0.25, capacity: float | None = None, name: str = ""
) -> dict:
    return {
        "id": identifier,
        "name": name or identifier,
        "model": "exponential" if capacity is None else "logistic",
        "initial": initial,
        "rate": rate,
        "capacity": capacity,
    }


def document(
    rows: list | None = None, timestep: float = 0.125, steps: int = 160, title: str = "Population comparison"
) -> dict:
    return {
        "version": 1,
        "title": title,
        "timestep": timestep,
        "steps": steps,
        "cases": (
            rows
            if rows is not None
            else [
                case("growth", 100.0, 0.08, name="Exponential growth"),
                case("limited", 100.0, 0.25, 1000.0, "Growth toward capacity"),
                case("decay", 1000.0, -0.15, name="Exponential decay"),
                case("above", 1500.0, 0.2, 1000.0, "Starting above capacity"),
            ]
        ),
    }


def analytic(row: dict, timestep: float, index: int) -> float:
    with decimal.localcontext() as context:
        context.prec = 70
        initial, rate, step = [decimal.Decimal.from_float(float(v)) for v in [row["initial"], row["rate"], timestep]]
        if not initial:
            return 0.0
        exponent = rate * step * index
        if row["model"] == "exponential":
            return float(initial * exponent.exp())
        capacity = decimal.Decimal.from_float(float(row["capacity"]))
        denominator = 1 + (capacity / initial - 1) * (-exponent).exp()
        assert denominator > 0, "analytic solution passed a finite-time singularity"
        return float(capacity / denominator)


def inspect_results(source: dict, results: dict) -> None:
    assert results.keys() == {"method", "times", "series", "summary"} and results["method"] == "rk4"
    times = results["times"]
    rows = results["series"]
    steps = source["steps"]
    h = float(source["timestep"])
    assert len(times) == steps + 1 and len(rows) == len(source["cases"])
    assert all(type(t) is float and t == float(i) * h for i, t in enumerate(times))
    assert canonical(results["summary"]) == canonical(
        {"cases": len(rows), "steps": steps, "points": len(rows) * len(times), "horizon": times[-1]}
    )
    for params, row in zip(source["cases"], rows):
        assert row.keys() == {
            "id",
            "name",
            "model",
            "values",
            "initial",
            "final",
            "minimum",
            "maximum",
            "change",
            "difference_from_first",
        }
        assert all(row[k] == params[k] for k in ["id", "name", "model"])
        values = row["values"]
        assert len(values) == len(times)
        assert all(type(v) is float and math.isfinite(v) and 0 <= v <= 1e100 for v in values)
        expected = {
            "initial": float(params["initial"]),
            "final": values[-1],
            "minimum": min(values),
            "maximum": max(values),
            "change": values[-1] - float(params["initial"]),
            "difference_from_first": values[-1] - rows[0]["values"][-1],
        }
        assert canonical({k: row[k] for k in expected}) == canonical(expected)
        assert values[0] == float(params["initial"])
        for index, value in enumerate(values):
            truth = analytic(params, h, index)
            tolerance = abs(truth) * 2e-5 + abs(float(params["initial"])) * 1e-13 + 1e-110
            assert abs(value - truth) <= tolerance, (params, index, value, truth, tolerance)
        rate = float(params["rate"])
        initial = float(params["initial"])
        derivative = rate * initial * (1 - initial / float(params["capacity"]) if params["model"] == "logistic" else 1)
        if derivative == 0:
            assert all(value == initial for value in values)
        elif derivative > 0:
            assert all(left <= right for left, right in itertools.pairwise(values))
        else:
            assert all(left >= right for left, right in itertools.pairwise(values))
        if params["model"] == "logistic" and rate >= 0:
            assert all(
                min(initial, params["capacity"]) <= value <= max(initial, params["capacity"]) for value in values
            )
    return  # noqa: PLR1711


def inspect_csv(raw: bytes, results: dict) -> None:
    rows = list(csv.reader(io.StringIO(raw.decode())))
    assert rows.pop(0) == ["id", "step", "time", "population"]
    expected = [
        (row["id"], i, t, row["values"][i]) for row in results["series"] for i, t in enumerate(results["times"])
    ]
    assert len(rows) == len(expected)
    for row, (identifier, index, time, population) in zip(rows, expected):
        assert len(row) == 4 and row[:2] == [identifier, str(index)]
        assert row[2:] == [canonical(time).decode().strip(), canonical(population).decode().strip()]
        assert float(row[2]) == time and float(row[3]) == population
    return  # noqa: PLR1711


def inspect_svg(raw: bytes, source: dict, results: dict) -> None:
    svg = ET.fromstring(raw)
    ns = "{http://www.w3.org/2000/svg}"
    assert svg.tag == ns + "svg" and svg.attrib == {
        "width": "1000",
        "height": str(460 + 22 * len(source["cases"])),
        "viewBox": "0 0 1000 " + str(460 + 22 * len(source["cases"])),
    }
    assert svg.find(ns + "title").text == display(source["title"])
    assert all(
        node.tag in {ns + n for n in ["svg", "title", "desc", "rect", "g", "text", "path", "polyline", "circle"]}
        for node in svg.iter()
    )
    assert all(not key.startswith("on") and "href" not in key for node in svg.iter() for key in node.attrib)
    lines = svg.findall(".//" + ns + "polyline")
    dots = svg.findall(".//" + ns + "circle")
    assert len(lines) == len(dots) == len(source["cases"])
    ceiling = max(row["maximum"] for row in results["series"])
    scale = ceiling or 1.0
    horizon = results["times"][-1]
    duration = horizon or 1.0
    colors = []
    for params, row, line, dot in zip(source["cases"], results["series"], lines, dots):
        assert line.attrib["id"] == "series-" + params["id"] and line.attrib["fill"] == "none"
        assert line.find(ns + "title").text == display(params["name"])
        points = [tuple(map(int, p.split(","))) for p in line.attrib["points"].split()]
        assert len(points) == source["steps"] + 1
        for (x, y), time, value in zip(points, results["times"], row["values"]):
            assert 80 <= x <= 960 and 80 <= y <= 380
            assert abs(x - (80 + 880 * time / duration)) <= 0.50000001
            assert abs(y - (380 - 300 * value / scale)) <= 0.50000001
        assert dot.attrib == {
            "id": "start-" + params["id"],
            "cx": "80",
            "cy": str(points[0][1]),
            "r": "3",
            "fill": line.attrib["stroke"],
        }
        colors.append(line.attrib["stroke"])
    assert len(set(colors)) == len(colors)
    legends = [node for node in svg.findall(".//" + ns + "text") if node.find(ns + "title") is not None]
    assert len(legends) == len(source["cases"])
    for node, row in zip(legends, source["cases"]):
        shown = row["id"] + " — " + display(row["name"])
        assert node.find(ns + "title").text == shown
        assert node.find(ns + "title").tail == (shown if len(shown) <= 44 else shown[:41] + "...")
    return  # noqa: PLR1711
