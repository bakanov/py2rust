"""Fit or stretch thumbnails, then place them in a deterministic bounded grid."""

from dataclasses import dataclass

from bitmap import Bitmap, decode, encode, resize
from model import Source, digest, exact, text

from py2rust.stdlib import Json, json_array, json_int


@dataclass
class Sheet:
    thumbnails: list[bytes]
    bitmap: bytes
    results: Json


def compose(sources: list[Source], settings: Json) -> Sheet:
    exact(settings, ["box_width", "box_height", "columns", "margin", "gap", "fit", "background"])
    box_width: int = json_int(settings["box_width"])
    box_height: int = json_int(settings["box_height"])
    columns: int = json_int(settings["columns"])
    margin: int = json_int(settings["margin"])
    gap: int = json_int(settings["gap"])
    fit: str = text(settings["fit"])
    assert 1 <= box_width <= 256 and 1 <= box_height <= 256 and 1 <= columns <= 8, "box or column range"
    assert 0 <= margin <= 32 and 0 <= gap <= 32 and fit in ["contain", "stretch"], "spacing or fit mode"
    background: list[Json] = json_array(settings["background"])
    assert len(background) == 3, "background requires RGB triplet"
    color: bytearray = bytearray()
    for channel in range(2, -1, -1):
        value: int = json_int(background[channel])
        assert 0 <= value <= 255, "background channel range"
        color.append(value)
    columns = min(columns, len(sources))
    rows: int = (len(sources) + columns - 1) // columns
    width: int = 2 * margin + columns * box_width + (columns - 1) * gap
    height: int = 2 * margin + rows * box_height + (rows - 1) * gap
    assert width <= 4096 and height <= 4096 and width * height <= 2097152, "sheet dimension or pixel limit"
    canvas: bytearray = bytearray()
    for pixel in range(width * height):
        canvas.extend(color)
    thumbnails: list[bytes] = []
    items: list[Json] = []
    total_pixels: int = 0
    for index in range(len(sources)):
        source: Source = sources[index]
        original: Bitmap = decode(source.data)
        total_pixels = total_pixels + original.width * original.height
        assert total_pixels <= 1048576, "combined source pixel limit"
        thumb_width: int = box_width
        thumb_height: int = box_height
        if fit == "contain":
            if original.width * box_height >= original.height * box_width:
                thumb_height = max(1, original.height * box_width // original.width)
            else:
                thumb_width = max(1, original.width * box_height // original.height)
        thumbnail: Bitmap = resize(original, thumb_width, thumb_height)
        left: int = margin + (index % columns) * (box_width + gap) + (box_width - thumb_width) // 2
        top: int = margin + (index // columns) * (box_height + gap) + (box_height - thumb_height) // 2
        for y in range(thumb_height):
            for x in range(thumb_width * 3):
                canvas[((top + y) * width + left) * 3 + x] = thumbnail.pixels[y * thumb_width * 3 + x]
        thumbnail_data: bytes = encode(thumbnail)
        thumbnails.append(thumbnail_data)
        items.append(
            {
                "index": index,
                "name": source.name,
                "source": original.metadata,
                "width": thumb_width,
                "height": thumb_height,
                "left": left,
                "top": top,
                "thumbnail_sha256": digest(thumbnail_data),
                "pixels_sha256": digest(thumbnail.pixels),
            }
        )
    sheet: bytes = encode(Bitmap(width, height, bytes(canvas), None))
    results: Json = {
        "width": width,
        "height": height,
        "columns": columns,
        "rows": rows,
        "source_pixels": total_pixels,
        "items": items,
        "sheet_sha256": digest(sheet),
        "pixels_sha256": digest(bytes(canvas)),
    }
    return Sheet(thumbnails, sheet, results)
