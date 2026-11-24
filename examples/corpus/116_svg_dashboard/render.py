"""Standalone SVG with clipped labels, full tooltips and shared chart geometry."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from model import escaped, text

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_canonical,
    json_float,
    json_int,
)


def element(name: str, attributes: dict[str, str], content: str) -> str:
    opening: str = "<" + name
    for key in attributes:
        opening = opening + " " + key + '="' + escaped(attributes[key]) + '"'
    return opening + ">" + content + "</" + name + ">"


def field(row: Json, name: str) -> str:
    return str(json_int(row[name]))


def label_box(left: int, top: int, width: int, value: str, size: int, anchor: str, limit: int) -> str:
    x: int = 0 if anchor == "start" else (width if anchor == "end" else width // 2)
    shown: str = value if len(value) <= limit else value[: limit - 1] + "…"
    content: str = element("title", {}, escaped(value)) + escaped(shown)
    content = element("text", {"x": str(x), "y": str(size), "font-size": str(size), "text-anchor": anchor}, content)
    return element(
        "svg", {"class": "label", "x": str(left), "y": str(top), "width": str(width), "height": str(size + 8)}, content
    )


def panel(chart: Json, index: int) -> str:
    points: list[Json] = json_array(chart["points"])
    kind: str = text(chart["kind"])
    lines: list[str] = [
        element("rect", {"x": "0", "y": "0", "width": "640", "height": "380", "rx": "12", "fill": "#ffffff"}, ""),
        label_box(24, 16, 592, text(chart["title"]), 18, "start", 28),
        label_box(24, 64, 140, "Bar · zero baseline" if kind == "bar" else "Line · data range", 11, "start", 20),
        label_box(174, 64, 434, text(chart["unit"]), 12, "start", 28),
    ]
    for tick in json_array(chart["ticks"]):
        lines.append(
            element("path", {"class": "grid", "d": "M174 " + field(tick, "y") + " H608", "stroke": "#e2e8f0"}, "")
        )
        lines.append(label_box(16, json_int(tick["y"]) - 6, 146, text(tick["label"]), 10, "end", 32))
    lines.append(element("path", {"d": "M174 104 V304 H608", "fill": "none", "stroke": "#94a3b8"}, ""))
    if json_bool(chart["zero_visible"]):
        lines.append(
            element("path", {"class": "zero", "d": "M174 " + field(chart, "zero_y") + " H608", "stroke": "#64748b"}, "")
        )
    positions: list[str] = []
    for point in points:
        positions.append(field(point, "x") + "," + field(point, "y"))
    if kind == "line" and len(points) > 1:
        line_style: dict[str, str] = {
            "class": "series",
            "points": " ".join(positions),
            "fill": "none",
            "stroke": "#6459cf",
            "stroke-width": "2",
        }
        lines.append(element("polyline", line_style, ""))
    for point in points:
        tooltip: str = element("title", {}, escaped(text(point["label"]) + ": " + json_canonical(point["value"])))
        if kind == "bar":
            color: str = "#2f8fce" if json_float(point["value"]) >= 0.0 else "#e36572"
            bar: dict[str, str] = {
                "class": "bar",
                "x": field(point, "bar_x"),
                "y": field(point, "bar_y"),
                "width": field(point, "bar_width"),
                "height": field(point, "bar_height"),
                "fill": color,
            }
            lines.append(element("rect", bar, tooltip))
        if kind == "line" or json_int(point["bar_height"]) == 0:
            marker: dict[str, str] = {
                "class": "point" if kind == "line" else "zero-point",
                "cx": field(point, "x"),
                "cy": field(point, "y"),
                "r": "3" if kind == "line" else "2",
                "fill": "#6459cf" if kind == "line" else "#2f8fce",
            }
            lines.append(element("circle", marker, tooltip))
        if json_bool(point["label_visible"]):
            lines.append(label_box(json_int(point["x"]) - 35, 318, 70, text(point["label"]), 11, "middle", 6))
    if len(points) == 0:
        lines.append(label_box(220, 185, 344, "No data", 16, "middle", 20))
    lines.append(
        label_box(174, 350, 434, str(len(points)) + " points · hover for full labels and values", 11, "start", 60)
    )
    return element(
        "svg",
        {
            "class": "chart",
            "x": field(chart, "left"),
            "y": field(chart, "top"),
            "width": "640",
            "height": "380",
            "viewBox": "0 0 640 380",
            "id": "chart-" + str(index),
        },
        "\n".join(lines),
    )


def render(results: Json) -> bytes:
    width: int = json_int(results["width"])
    height: int = json_int(results["height"])
    charts: list[Json] = json_array(results["charts"])
    lines: list[str] = [
        label_box(24, 16, width - 48, text(results["title"]), 26, "start", 80),
        label_box(24, 56, width - 48, "Metrics dashboard · linear scales · categorical X positions", 12, "start", 80),
    ]
    for index in range(len(charts)):
        lines.append(panel(charts[index], index))
    if len(charts) == 0:
        lines.append(label_box(24, 126, width - 48, "No charts", 18, "middle", 20))
    content: str = element("rect", {"width": "100%", "height": "100%", "fill": "#f1f5f9"}, "")
    content = content + element("g", {"font-family": "DejaVu Sans, sans-serif", "fill": "#0f172a"}, "\n".join(lines))
    return (
        element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "width": str(width),
                "height": str(height),
                "viewBox": "0 0 " + str(width) + " " + str(height),
            },
            content,
        )
        + "\n"
    ).encode()
