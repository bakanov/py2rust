"""Independent Decimal scale/geometry checks and parsed SVG/HTML inspection; no app imports."""

from __future__ import annotations

import decimal
import itertools
import math
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from .population_fixture import canonical, digest

__all__ = ["canonical", "chart", "dataset", "digest", "inspect_html", "inspect_results", "inspect_svg"]

D = decimal.Decimal
NS = "{http://www.w3.org/2000/svg}"


def chart(identifier: str, values: list, kind: str = "bar", title: str = "", unit: str = "") -> dict:
    return {
        "id": identifier,
        "title": title or identifier,
        "kind": kind,
        "unit": unit,
        "points": [{"label": "P" + str(i), "value": value} for i, value in enumerate(values)],
    }


def dataset(charts: list | None = None, title: str = "Network metrics") -> dict:
    return {
        "version": 1,
        "title": title,
        "charts": (
            charts
            if charts is not None
            else [
                chart("traffic", [-20, 0, 60, 100], title="Traffic change", unit="MiB"),
                chart("latency", [18, 25, 22, 40, 32, 19], "line", "Request latency", "ms"),
                chart("errors", [-7, -3, -9, -2], title="Rejected requests", unit="requests"),
                chart("steady", [12, 12, 12, 12], "line", "Stable connections", "connections"),
                chart("zero", [0, -0.0, 0], title="Dropped messages", unit="messages"),
                chart("empty", [], "line", "Waiting for samples", "ms"),
            ]
        ),
    }


def requested_domain(values: list[float], kind: str) -> tuple[float, float]:
    low, high = (min(values), max(values)) if values else (0.0, 0.0)
    if kind == "bar":
        low, high = min(0.0, low), max(0.0, high)
    size = max(abs(low), abs(high))
    if not size:
        return -1.0, 1.0
    margin = size * 0.05 if high - low <= size * 1e-12 else (high - low) * 0.05 if kind == "line" else 0.0
    return low - margin, high + margin


def tick_text(value: D) -> str:
    if not value:
        return "0"
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    digits = len(normalized.as_tuple().digits)
    if (exponent >= 0 and digits + exponent <= 12) or (-6 <= exponent < 0 and digits <= 12):
        return format(normalized, "f")
    mantissa, power = format(normalized, "E").split("E")
    return mantissa + "e" + str(int(power))


def pixel_y(value: float, low: float, high: float) -> D:
    with decimal.localcontext() as context:
        context.prec = 60
        result = D(304) - D(200) * (D.from_float(value) - D.from_float(low)) / (D.from_float(high) - D.from_float(low))
        return max(D(104), min(D(304), result))


def inspect_results(source: dict, requested_columns: int, results: dict) -> None:
    columns = min(requested_columns, max(1, len(source["charts"])))
    rows = math.ceil(len(source["charts"]) / columns)
    assert results.keys() == {"title", "columns", "rows", "width", "height", "charts"}
    assert results["title"] == source["title"]
    assert {k: results[k] for k in ["columns", "rows", "width", "height"]} == {
        "columns": columns,
        "rows": rows,
        "width": 24 + 664 * columns,
        "height": 96 + 404 * rows if rows else 200,
    }
    assert len(results["charts"]) == len(source["charts"])
    for index, (row, result) in enumerate(zip(source["charts"], results["charts"])):
        assert result.keys() == {
            "id",
            "title",
            "kind",
            "unit",
            "left",
            "top",
            "low",
            "high",
            "step",
            "ticks",
            "zero_y",
            "zero_visible",
            "points",
        }
        assert all(result[k] == row[k] for k in ["id", "title", "kind", "unit"])
        assert result["left"] == 24 + index % columns * 664 and result["top"] == 96 + index // columns * 404
        values = [float(p["value"]) for p in row["points"]]
        low, high, step = [result[k] for k in ["low", "high", "step"]]
        assert all(type(v) is float and math.isfinite(v) for v in [low, high, step])
        requested_low, requested_high = requested_domain(values, row["kind"])
        target = (requested_high - requested_low) / 4
        candidates = sorted(D(factor).scaleb(power) for power in range(-30, 15) for factor in [1, 2, 5])
        actual = next((value for value in candidates if float(value) == step), None)
        assert actual is not None and step > 0
        expected = next(value for value in candidates if float(value) >= target)
        # The implementation compares decade multiples in binary64: allow the adjacent nice step only at an ULP boundary.
        assert actual == expected or abs(float(min(actual, expected)) - target) <= 2 * math.ulp(target)
        assert low <= requested_low <= requested_high <= high and low < high
        assert requested_low - low <= step * 1.000000001 and high - requested_high <= step * 1.000000001
        first = round(low / step)
        ticks = result["ticks"]
        assert 2 <= len(ticks) <= 9 and ticks[0]["value"] == low and ticks[-1]["value"] == high
        assert type(result["zero_visible"]) is bool and result["zero_visible"] == (low <= 0 <= high)
        assert abs(D(result["zero_y"]) - pixel_y(0.0, low, high)) <= D("0.500001")
        for offset, tick in enumerate(ticks):
            assert tick.keys() == {"value", "label", "y"}
            assert type(tick["value"]) is float and tick["value"] == (first + offset) * step
            assert tick["label"] == tick_text(actual * (first + offset))
            assert abs(D(tick["y"]) - pixel_y(tick["value"], low, high)) <= D("0.500001")
        assert all(a["value"] < b["value"] and a["y"] > b["y"] for a, b in itertools.pairwise(ticks))
        points = result["points"]
        assert len(points) == len(values)
        count = len(values)
        width = max(1, math.floor(434 * 0.68 / max(1, count)))
        for position, (original, point) in enumerate(zip(row["points"], points)):
            assert point.keys() == {
                "label",
                "value",
                "x",
                "y",
                "label_visible",
                "bar_x",
                "bar_y",
                "bar_width",
                "bar_height",
            }
            assert point["label"] == original["label"] and type(point["value"]) is float
            assert canonical(point["value"]) == canonical(float(original["value"]))
            assert low <= point["value"] <= high
            ideal_x = D(174) + (D(position) + D("0.5")) * D(434) / D(count)
            if row["kind"] == "line":
                ideal_x = D(391) if count == 1 else D(174) + D(position) * D(434) / D(count - 1)
            assert abs(D(point["x"]) - ideal_x) <= D("0.500001")
            assert abs(D(point["y"]) - pixel_y(point["value"], low, high)) <= D("0.500001")
            assert point["label_visible"] == (position % max(1, math.ceil(count / 6)) == 0)
            assert point["bar_width"] == width and point["bar_x"] == point["x"] - width // 2
            assert point["bar_y"] == min(point["y"], result["zero_y"])
            assert point["bar_height"] == abs(point["y"] - result["zero_y"])
    return  # noqa: PLR1711


def inspect_svg(raw: bytes, results: dict) -> None:
    svg = ET.fromstring(raw)
    assert svg.tag == NS + "svg" and svg.attrib == {
        "width": str(results["width"]),
        "height": str(results["height"]),
        "viewBox": f'0 0 {results["width"]} {results["height"]}',
    }
    allowed = {NS + name for name in ["svg", "title", "rect", "g", "text", "path", "polyline", "circle"]}
    assert all(node.tag in allowed for node in svg.iter())
    assert all(not key.startswith("on") and "href" not in key for node in svg.iter() for key in node.attrib)
    panels = svg.findall(".//" + NS + 'svg[@class="chart"]')
    assert len(panels) == len(results["charts"])
    for node in svg.findall(".//" + NS + 'svg[@class="label"]'):
        text = node.find(NS + "text")
        assert len(node) == 1 and text is not None and len(text) == 1
        assert text[0].tag == NS + "title" and int(node.attrib["height"]) == int(text.attrib["font-size"]) + 8
        assert int(node.attrib["width"]) > 0
    for index, (panel, chart_row) in enumerate(zip(panels, results["charts"])):
        assert panel.attrib == {
            "class": "chart",
            "id": "chart-" + str(index),
            "x": str(chart_row["left"]),
            "y": str(chart_row["top"]),
            "width": "640",
            "height": "380",
            "viewBox": "0 0 640 380",
        }
        labels = panel.findall(NS + 'svg[@class="label"]')
        full_labels = [node.find(NS + "text").find(NS + "title").text or "" for node in labels]
        assert full_labels[:3] == [
            chart_row["title"],
            "Bar · zero baseline" if chart_row["kind"] == "bar" else "Line · data range",
            chart_row["unit"],
        ]
        tick_count = len(chart_row["ticks"])
        assert full_labels[3 : 3 + tick_count] == [tick["label"] for tick in chart_row["ticks"]]
        expected_labels = [p["label"] for p in chart_row["points"] if p["label_visible"]]
        assert full_labels[3 + tick_count : -1] == (expected_labels if chart_row["points"] else ["No data"])
        for tick, node in zip(chart_row["ticks"], panel.findall(NS + 'path[@class="grid"]')):
            assert node.attrib["d"] == f'M174 {tick["y"]} H608'
        assert len(panel.findall(NS + 'path[@class="grid"]')) == tick_count
        zero = panel.findall(NS + 'path[@class="zero"]')
        assert len(zero) == int(chart_row["zero_visible"])
        if zero:
            assert zero[0].attrib["d"] == f'M174 {chart_row["zero_y"]} H608'
        points = chart_row["points"]
        bars = panel.findall(NS + 'rect[@class="bar"]')
        dots = panel.findall(NS + "circle")
        lines = panel.findall(NS + "polyline")
        assert len(bars) == (len(points) if chart_row["kind"] == "bar" else 0)
        assert len(lines) == int(chart_row["kind"] == "line" and len(points) > 1)
        if lines:
            assert lines[0].attrib["points"] == " ".join(f'{p["x"]},{p["y"]}' for p in points)
        for point, bar in zip(points, bars):
            assert bar.attrib == {
                "class": "bar",
                "x": str(point["bar_x"]),
                "y": str(point["bar_y"]),
                "width": str(point["bar_width"]),
                "height": str(point["bar_height"]),
                "fill": "#2f8fce" if point["value"] >= 0 else "#e36572",
            }
            assert bar.find(NS + "title").text == point["label"] + ": " + canonical(point["value"]).decode().strip()
        marked = points if chart_row["kind"] == "line" else [p for p in points if p["bar_height"] == 0]
        assert len(dots) == len(marked)
        for point, dot in zip(marked, dots):
            assert dot.attrib["cx"] == str(point["x"]) and dot.attrib["cy"] == str(point["y"])
            assert dot.attrib["class"] == ("point" if chart_row["kind"] == "line" else "zero-point")
            assert dot.find(NS + "title").text == point["label"] + ": " + canonical(point["value"]).decode().strip()
    return  # noqa: PLR1711


class Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self.tags.append(tag)
        self.attributes.extend(attrs)
        return  # noqa: PLR1711


def inspect_html(raw: bytes, svg: bytes) -> None:
    parser = Markup()
    parser.feed(raw.decode())
    assert parser.tags.count("main") == 1 and parser.tags.count("html") == 1
    assert set(parser.tags) <= {
        "html",
        "meta",
        "title",
        "style",
        "main",
        "svg",
        "rect",
        "g",
        "text",
        "path",
        "polyline",
        "circle",
    }
    assert all(not key.startswith("on") and key not in ["href", "src"] for key, _ in parser.attributes)
    assert raw.count(svg) == 1 and b"overflow:auto" in raw
    return  # noqa: PLR1711
