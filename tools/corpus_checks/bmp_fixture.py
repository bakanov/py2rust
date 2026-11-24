"""Independent struct-packed BMPs and RGB-grid reference rendering (no application imports)."""

from __future__ import annotations

import hashlib
import json
import struct
from fractions import Fraction
from html.parser import HTMLParser

Pixel = tuple[int, int, int]
Grid = list[list[Pixel]]


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pattern(width: int, height: int, seed: int = 0) -> Grid:
    return [
        [((x * 37 + seed) % 256, (y * 53 + seed * 7) % 256, (x * 11 + y * 29) % 256) for x in range(width)]
        for y in range(height)
    ]


def pixels(grid: Grid) -> bytes:
    return b"".join(bytes(reversed(rgb)) for row in grid for rgb in row)


def bitmap(
    grid: Grid,
    dib: int = 40,
    top_down: bool = False,
    pad: int = 0,
    gap: bytes = b"",
    tail: bytes = b"",
    palette: int = 0,
    image_size_zero: bool = False,
    color_space: int = 0,
    profile: bytes = b"",
    profile_before: bool = False,
) -> bytes:
    height, width = len(grid), len(grid[0])
    assert all(len(row) == width for row in grid)
    assert not (dib == 12 and (top_down or palette or profile))
    padding = bytes([pad]) * (-3 * width % 4)
    rows = grid if top_down else grid[::-1]
    body = b"".join(pixels([row]) + padding for row in rows)
    header = bytearray(dib)
    if dib == 12:
        struct.pack_into("<IHHHH", header, 0, dib, width, height, 1, 24)
    else:
        struct.pack_into(
            "<IiiHHIIiiII",
            header,
            0,
            dib,
            width,
            -height if top_down else height,
            1,
            24,
            0,
            0 if image_size_zero else len(body),
            0,
            0,
            palette,
            0,
        )
    if dib >= 108:
        struct.pack_into("<I", header, 56, color_space)
    between = bytes(range(4)) * palette + gap
    if profile_before:
        between += profile
    offset = 14 + dib + len(between)
    if profile:
        assert dib == 124
        position = offset - len(profile) if profile_before else offset + len(body)
        struct.pack_into("<II", header, 112, position - 14, len(profile))
    following = (b"" if profile_before else profile) + tail
    size = offset + len(body) + len(following)
    return struct.pack("<2sIHHI", b"BM", size, 0, 0, offset) + header + between + body + following


def read_bitmap(raw: bytes) -> tuple[Grid, dict]:
    magic, size, first, second, offset = struct.unpack_from("<2sIHHI", raw)
    assert magic == b"BM" and size == len(raw) and first == second == 0
    dib = struct.unpack_from("<I", raw, 14)[0]
    if dib == 12:
        width, signed_height, planes, depth = struct.unpack_from("<HHHH", raw, 18)
        palette = color_space = profile_bytes = 0
    else:
        width, signed_height, planes, depth, compression, image_size = struct.unpack_from("<iiHHII", raw, 18)
        palette = struct.unpack_from("<I", raw, 46)[0]
        color_space = struct.unpack_from("<I", raw, 70)[0] if dib >= 108 else 0
        profile_bytes = (
            struct.unpack_from("<I", raw, 130)[0] if dib == 124 and color_space in [0x4C494E4B, 0x4D424544] else 0
        )
        assert compression == 0 and image_size in [0, ((3 * width + 3) & ~3) * abs(signed_height)]
    assert planes == 1 and depth == 24
    height = abs(signed_height)
    stride = (3 * width + 3) & ~3
    grid = []
    for y in range(height):
        start = offset + stride * y
        row = [tuple(raw[start + x * 3 : start + x * 3 + 3][::-1]) for x in range(width)]
        grid.append(row)
    if signed_height > 0:
        grid.reverse()
    metadata = {
        "width": width,
        "height": height,
        "top_down": signed_height < 0,
        "dib_bytes": dib,
        "pixel_offset": offset,
        "stride": stride,
        "palette_entries": palette,
        "gap_bytes": offset - 14 - dib,
        "trailing_bytes": len(raw) - offset - stride * height,
        "color_space": color_space,
        "profile_bytes": profile_bytes,
        "color_management": False,
        "source_sha256": digest(raw),
        "pixels_sha256": digest(pixels(grid)),
    }
    return grid, metadata


def reference(images: list[dict], settings: dict) -> tuple[list[bytes], bytes, dict]:
    columns = min(settings["columns"], len(images))
    rows = (len(images) + columns - 1) // columns
    bw, bh, margin, gap = (settings[k] for k in ["box_width", "box_height", "margin", "gap"])
    width, height = 2 * margin + columns * bw + (columns - 1) * gap, 2 * margin + rows * bh + (rows - 1) * gap
    sheet = [[tuple(settings["background"]) for _ in range(width)] for _ in range(height)]
    thumbnails, items, source_pixels = [], [], 0
    for index, source in enumerate(images):
        grid, metadata = read_bitmap(bytes.fromhex(source["source_hex"]))
        sw, sh = len(grid[0]), len(grid)
        source_pixels += sw * sh
        scale = min(Fraction(bw, sw), Fraction(bh, sh))
        tw, th = (max(1, int(sw * scale)), max(1, int(sh * scale))) if settings["fit"] == "contain" else (bw, bh)
        xs = [int((Fraction(x) + Fraction(1, 2)) * Fraction(sw, tw)) for x in range(tw)]
        ys = [int((Fraction(y) + Fraction(1, 2)) * Fraction(sh, th)) for y in range(th)]
        thumb = [[grid[y][x] for x in xs] for y in ys]
        left, top = (
            margin + (index % columns) * (bw + gap) + (bw - tw) // 2,
            margin + (index // columns) * (bh + gap) + (bh - th) // 2,
        )
        for y, row in enumerate(thumb):
            sheet[top + y][left : left + tw] = row
        raw = bitmap(thumb)
        thumbnails.append(raw)
        items.append(
            {
                "index": index,
                "name": source["name"],
                "source": metadata,
                "width": tw,
                "height": th,
                "left": left,
                "top": top,
                "thumbnail_sha256": digest(raw),
                "pixels_sha256": digest(pixels(thumb)),
            }
        )
    output = bitmap(sheet)
    return (
        thumbnails,
        output,
        {
            "width": width,
            "height": height,
            "columns": columns,
            "rows": rows,
            "source_pixels": source_pixels,
            "items": items,
            "sheet_sha256": digest(output),
            "pixels_sha256": digest(pixels(sheet)),
        },
    )


class Preview(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.images: list[tuple[str, str]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        assert tag not in {"script", "iframe", "object", "embed"}
        values = dict(attrs)
        assert not any(k.startswith("on") for k in values)
        if tag == "a":
            self.links.append(values["href"])
        if tag == "img":
            self.images.append((values["src"], values["alt"]))
        return  # noqa: PLR1711

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        return  # noqa: PLR1711


def inspect_preview(raw: bytes, images: list[dict]) -> None:
    preview = Preview()
    preview.feed(raw.decode())
    paths = ["sheet.bmp"] + [f"thumbnail-{i}.bmp" for i in range(len(images))]
    assert preview.links == paths
    assert preview.images == list(zip(paths, ["Combined contact sheet"] + [p["name"] for p in images], strict=True))
    assert all(p["name"] in preview.text for p in images)
    return  # noqa: PLR1711
