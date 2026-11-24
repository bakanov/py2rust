"""Independent RGB-grid atlas oracle, rectangle invariants and SVG geometry inspection."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction

from .ppm_fixture import (  # noqa: F401 - shared fixture exports
    canonical,
    digest,
    pattern,
    ppm,
    raster,
    read_ppm,
)


def reference(sprites: list[dict], settings: dict) -> tuple[bytes, dict, list[bytes]]:
    decoded = [read_ppm(bytes.fromhex(row["source_hex"])) for row in sprites]
    maximum = decoded[0][1]
    order = list(range(len(sprites)))
    if settings["order"] == "height":
        order.sort(key=lambda i: (-len(decoded[i][0]), -len(decoded[i][0][0]), sprites[i]["name"]))
    width, padding = settings["width"], settings["padding"]
    shelves, placements = [], []
    for index in order:
        grid, depth, _ = decoded[index]
        assert depth == maximum
        sw, sh = len(grid[0]), len(grid)
        box = (sw + 2 * padding, sh + 2 * padding)
        candidates = [
            i for i, shelf in enumerate(shelves) if shelf["height"] >= box[1] and width - shelf["used_width"] >= box[0]
        ]
        if not candidates:
            shelves.append({"y": sum(s["height"] for s in shelves), "height": box[1], "used_width": 0})
            candidates = [len(shelves) - 1]
        selected = candidates[0]
        x, y = shelves[selected]["used_width"] + padding, shelves[selected]["y"] + padding
        shelves[selected]["used_width"] += box[0]
        placements.append(
            {
                "index": index,
                "name": sprites[index]["name"],
                "x": x,
                "y": y,
                "width": sw,
                "height": sh,
                "shelf": selected,
                "source_sha256": digest(bytes.fromhex(sprites[index]["source_hex"])),
                "raster_sha256": digest(raster(grid, maximum)),
                "extracted_sha256": digest(ppm(grid, maximum)),
            }
        )
    height = sum(s["height"] for s in shelves)
    assert height <= settings["max_height"]
    canvas = [[tuple(settings["background"]) for _ in range(width)] for _ in range(height)]
    rectangles = []
    for placed in placements:
        x, y, sw, sh = (placed[k] for k in ["x", "y", "width", "height"])
        box = (x - padding, y - padding, x + sw + padding, y + sh + padding)
        assert 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height
        for previous in rectangles:
            assert box[2] <= previous[0] or previous[2] <= box[0] or box[3] <= previous[1] or previous[3] <= box[1]
        rectangles.append(box)
        for row, values in enumerate(decoded[placed["index"]][0]):
            canvas[y + row][x : x + sw] = values
    output = ppm(canvas, maximum)
    source_pixels = sum(len(grid) * len(grid[0]) for grid, _, _ in decoded)
    results = {
        "width": width,
        "height": height,
        "maxval": maximum,
        "source_pixels": source_pixels,
        "background_pixels": width * height - source_pixels,
        "items": placements,
        "shelves": shelves,
        "atlas_sha256": digest(output),
        "raster_sha256": digest(raster(canvas, maximum)),
    }
    return output, results, [ppm(grid, maximum) for grid, _, _ in decoded]


def inspect_extraction(atlas: bytes, sprites: list[dict], results: dict, extracted: list[bytes]) -> None:
    grid, maximum, _ = read_ppm(atlas)
    for placed in results["items"]:
        x, y, width, height = (placed[k] for k in ["x", "y", "width", "height"])
        actual = [row[x : x + width] for row in grid[y : y + height]]
        original, depth, _ = read_ppm(bytes.fromhex(sprites[placed["index"]]["source_hex"]))
        assert maximum == depth and actual == original
        assert extracted[placed["index"]] == ppm(actual, maximum)
    return  # noqa: PLR1711


def inspect_svg(raw: bytes, atlas: bytes, results: dict) -> None:
    tree = ET.fromstring(raw)
    ns = "{http://www.w3.org/2000/svg}"
    assert tree.attrib == {"width": "640", "height": "480", "viewBox": "0 0 640 480"}
    assert all(e.tag in {ns + t for t in ["svg", "g", "text", "rect", "title"]} for e in tree.iter())
    grid, maximum, _ = read_ppm(atlas)
    width, height = len(grid[0]), len(grid)
    panel = tree.find(".//" + ns + "svg")
    assert panel.attrib == {
        "x": "24",
        "y": "80",
        "width": "592",
        "height": "350",
        "viewBox": f"0 0 {width} {height}",
        "preserveAspectRatio": "xMidYMid meet",
        "shape-rendering": "crispEdges",
    }
    columns, rows = min(128, width), min(128, height)
    boxes = panel.findall(ns + "rect")
    assert len(boxes) == columns * rows + len(results["items"])
    for i, rect in enumerate(boxes[: columns * rows]):
        x, y = i % columns, i // columns
        left, right = int(Fraction(x * width, columns)), int(Fraction((x + 1) * width, columns))
        top, bottom = int(Fraction(y * height, rows)), int(Fraction((y + 1) * height, rows))
        values = grid[(top + bottom) // 2][(left + right) // 2]
        color = bytes(int(Fraction(v * 255, maximum) + Fraction(1, 2)) for v in values).hex()
        assert rect.attrib == {
            "x": str(left),
            "y": str(top),
            "width": str(right - left),
            "height": str(bottom - top),
            "fill": "#" + color,
        }
    for rect, placed in zip(boxes[columns * rows :], results["items"], strict=True):
        assert rect.attrib == {
            **{k: str(placed[k]) for k in ["x", "y", "width", "height"]},
            "fill": "none",
            "stroke": "#ffffff",
            "stroke-width": str(max(1, min(width, height) // 256)),
        }
        assert [e.tag for e in rect] == [ns + "title"] and rect.find(ns + "title").text == placed["name"]
    assert [e.text for e in tree.iter(ns + "text")] == [
        "Sprite atlas",
        f'{len(results["items"])} sprites · {width} × {height} · Maxval {maximum}',
        "Sampled preview · outlines use exact coordinates · full pixels in atlas.ppm",
    ]
    return  # noqa: PLR1711
