"""Independent regex/struct/RGB-grid P6 decoding, filter oracle and exact CSV/SVG inspection."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from fractions import Fraction

Grid = list[list[tuple[int, int, int]]]


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pattern(width: int, height: int, maximum: int = 255, seed: int = 0) -> Grid:
    return [
        [
            ((x * 37 + seed) % (maximum + 1), (y * 53 + seed * 7) % (maximum + 1), (x * 11 + y * 29) % (maximum + 1))
            for x in range(width)
        ]
        for y in range(height)
    ]


def raster(grid: Grid, maximum: int) -> bytes:
    samples = [value for row in grid for pixel in row for value in pixel]
    return bytes(samples) if maximum < 256 else struct.pack(">" + "H" * len(samples), *samples)


def ppm(grid: Grid, maximum: int = 255, header: bytes | None = None) -> bytes:
    prefix = f"P6\n{len(grid[0])} {len(grid)}\n{maximum}\n".encode() if header is None else header
    return prefix + raster(grid, maximum)


def read_ppm(raw: bytes) -> tuple[Grid, int, int]:
    separator = rb"(?:[ \t\r\n\v\f]|#[^\r\n]*(?=[\r\n]))+"
    match = re.match(
        rb"P6"
        + separator
        + rb"([0-9]+)"
        + separator
        + rb"([0-9]+)"
        + separator
        + rb"([0-9]+)(?:#[^\r\n]*)?[ \t\r\n\v\f]",
        raw,
    )
    assert match is not None
    width, height, maximum = map(int, match.groups())
    body = raw[match.end() :]
    count = width * height * 3
    assert len(body) == count * (1 if maximum < 256 else 2)
    values = list(body) if maximum < 256 else list(struct.unpack(">" + "H" * count, body))
    assert all(0 <= value <= maximum for value in values)
    grid = [[tuple(values[3 * (y * width + x) : 3 * (y * width + x + 1)]) for x in range(width)] for y in range(height)]
    return grid, maximum, match.end()


def histogram(grid: Grid, maximum: int) -> dict[str, list[int]]:
    result = {}
    for channel, name in enumerate(["red", "green", "blue"]):
        counts = Counter(pixel[channel] for row in grid for pixel in row)
        result[name] = [counts[value] for value in range(maximum + 1)]
    assert all(sum(counts) == len(grid) * len(grid[0]) for counts in result.values())
    return result


def describe(grid: Grid, maximum: int, raw: bytes) -> dict:
    body = raster(grid, maximum)
    return {
        "width": len(grid[0]),
        "height": len(grid),
        "maxval": maximum,
        "header_bytes": len(raw) - len(body),
        "raster_sha256": digest(body),
        "file_sha256": digest(raw),
        "histogram": histogram(grid, maximum),
    }


def transform(grid: Grid, maximum: int, operation: dict) -> Grid:
    if operation["op"] == "crop":
        x, y, width, height = (operation[k] for k in ["x", "y", "width", "height"])
        return [row[x : x + width] for row in grid[y : y + height]]
    if operation["op"] == "invert":
        return [[tuple(maximum - v for v in pixel) for pixel in row] for row in grid]
    if operation["mode"] == "channel":
        return [[tuple(maximum if v >= operation["value"] else 0 for v in pixel) for pixel in row] for row in grid]
    return [
        [(maximum,) * 3 if Fraction(sum(pixel), 3) >= operation["value"] else (0, 0, 0) for pixel in row]
        for row in grid
    ]


def reference(source: bytes, pipeline: list[dict]) -> tuple[Grid, Grid, dict]:
    original, maximum, _ = read_ppm(source)
    current, processed, steps = original, len(original) * len(original[0]), []
    for index, operation in enumerate(pipeline):
        processed += len(current) * len(current[0])
        current = transform(current, maximum, operation)
        steps.append(
            {
                "index": index,
                "filter": operation,
                "width": len(current[0]),
                "height": len(current),
                "raster_sha256": digest(raster(current, maximum)),
            }
        )
    return (
        original,
        current,
        {
            "input": describe(original, maximum, source),
            "output": describe(current, maximum, ppm(current, maximum)),
            "steps": steps,
            "processed_pixels": processed,
        },
    )


def inspect_csv(raw: bytes, results: dict) -> None:
    rows = list(csv.reader(io.StringIO(raw.decode())))
    assert rows.pop(0) == [
        "value",
        "red_input",
        "red_output",
        "green_input",
        "green_output",
        "blue_input",
        "blue_output",
    ]
    expected = []
    for value in range(results["input"]["maxval"] + 1):
        counts = [
            results[side]["histogram"][channel][value]
            for channel in ["red", "green", "blue"]
            for side in ["input", "output"]
        ]
        if sum(counts):
            expected.append([str(value), *map(str, counts)])
    assert rows == expected
    assert (
        raw
        == (
            "value,red_input,red_output,green_input,green_output,blue_input,blue_output\n"
            + "".join(",".join(row) + "\n" for row in expected)
        ).encode()
    )
    return  # noqa: PLR1711


def inspect_svg(raw: bytes, before: Grid, after: Grid, maximum: int) -> None:
    tree = ET.fromstring(raw)
    ns = "{http://www.w3.org/2000/svg}"
    assert tree.attrib == {"width": "600", "height": "380", "viewBox": "0 0 600 380"}
    assert all(e.tag in {ns + tag for tag in ["svg", "g", "rect", "text"]} for e in tree.iter())
    panels = tree.findall(".//" + ns + "svg")
    assert len(panels) == 2
    for panel, grid, left in zip(panels, [before, after], [24, 320], strict=True):
        width, height = len(grid[0]), len(grid)
        scale = min(Fraction(1), Fraction(128, width), Fraction(128, height))
        pw, ph = max(1, int(width * scale)), max(1, int(height * scale))
        assert panel.attrib == {
            "x": str(left),
            "y": "80",
            "width": "256",
            "height": "256",
            "viewBox": f"0 0 {pw} {ph}",
            "preserveAspectRatio": "xMidYMid meet",
            "shape-rendering": "crispEdges",
        }
        rectangles = panel.findall(ns + "rect")
        assert len(rectangles) == pw * ph
        for i, rectangle in enumerate(rectangles):
            x, y = i % pw, i // pw
            sx, sy = int((Fraction(x) + Fraction(1, 2)) * width / pw), int((Fraction(y) + Fraction(1, 2)) * height / ph)
            # Round half upward, using exact rational arithmetic rather than the app's integer formula.
            rgb = [int(Fraction(v * 255, maximum) + Fraction(1, 2)) for v in grid[sy][sx]]
            assert rectangle.attrib == {
                "x": str(x),
                "y": str(y),
                "width": "1",
                "height": "1",
                "fill": "#" + bytes(rgb).hex(),
            }
    text = [e.text for e in tree.iter(ns + "text")]
    assert text == [
        "Original",
        f"{len(before[0])} × {len(before)} · Maxval {maximum}",
        "Filtered",
        f"{len(after[0])} × {len(after)} · Maxval {maximum}",
        "Sampled RGB preview · no gamma conversion · full data in PPM/CSV",
    ]
    return  # noqa: PLR1711
