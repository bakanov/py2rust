"""Validate categorical bar/line data and calculate complete, replayable chart geometry."""

from model import exact, label, number, text
from scales import Scale, ordinate, scale, ticks

from py2rust.stdlib import Json, floor, json_array, json_int


def calculate(dataset: Json, columns: int) -> Json:
    exact(dataset, ["version", "title", "charts"])
    assert json_int(dataset["version"]) == 1 and 1 <= columns <= 3, "dataset version or columns"
    title: str = label(dataset["title"], 120, False)
    sources: list[Json] = json_array(dataset["charts"])
    assert len(sources) <= 12, "chart count limit"
    columns = min(columns, max(1, len(sources)))
    rows: int = (len(sources) + columns - 1) // columns
    names: set[str] = set()
    charts: list[Json] = []
    for index in range(len(sources)):
        source: Json = sources[index]
        exact(source, ["id", "title", "kind", "unit", "points"])
        identifier: str = label(source["id"], 32, False)
        assert identifier not in names, "duplicate chart id"
        names.add(identifier)
        heading: str = label(source["title"], 120, False)
        kind: str = text(source["kind"])
        assert kind in ["bar", "line"], "unknown chart kind"
        unit: str = label(source["unit"], 32, True)
        source_points: list[Json] = json_array(source["points"])
        assert len(source_points) <= 128, "point count limit"
        values: list[float] = []
        labels: list[str] = []
        for point in source_points:
            exact(point, ["label", "value"])
            labels.append(label(point["label"], 120, True))
            values.append(number(point["value"]))
        axis: Scale = scale(values, kind)
        zero: int = ordinate(0.0, axis)
        count: int = len(values)
        stride: int = max(1, (count + 5) // 6)
        bar_width: int = max(1, floor(434.0 * 0.68 / float(max(1, count))))
        points: list[Json] = []
        for position in range(count):
            x: int = floor(174.0 + (float(position) + 0.5) * 434.0 / float(count) + 0.5)
            if kind == "line":
                x = 391 if count == 1 else floor(174.0 + float(position) * 434.0 / float(count - 1) + 0.5)
            y: int = ordinate(values[position], axis)
            points.append(
                {
                    "label": labels[position],
                    "value": values[position],
                    "x": x,
                    "y": y,
                    "label_visible": position % stride == 0,
                    "bar_x": x - bar_width // 2,
                    "bar_y": min(y, zero),
                    "bar_width": bar_width,
                    "bar_height": abs(y - zero),
                }
            )
        charts.append(
            {
                "id": identifier,
                "title": heading,
                "kind": kind,
                "unit": unit,
                "left": 24 + (index % columns) * 664,
                "top": 96 + (index // columns) * 404,
                "low": axis.low,
                "high": axis.high,
                "step": axis.step,
                "ticks": ticks(axis),
                "zero_y": zero,
                "zero_visible": axis.low <= 0.0 <= axis.high,
                "points": points,
            }
        )
    return {
        "title": title,
        "columns": columns,
        "rows": rows,
        "width": 24 + columns * 664,
        "height": 200 if rows == 0 else 96 + rows * 404,
        "charts": charts,
    }
