"""Deterministic first-fit shelves with explicit gutters and unchanged RGB samples."""

from dataclasses import dataclass

from model import Image, Sprite, digest, exact, text
from ppm import encode, raster

from py2rust.stdlib import Json, json_array, json_int


@dataclass
class Shelf:
    y: int
    height: int
    used: int


@dataclass
class Placement:
    sprite: Sprite
    x: int
    y: int
    shelf: int


@dataclass
class Atlas:
    image: Image
    placements: list[Placement]
    results: Json


def by_size(sprite: Sprite) -> tuple[int, int, str]:
    return (-sprite.image.height, -sprite.image.width, sprite.name)


def extract(image: Image, placement: Placement) -> Image:
    sprite: Image = placement.sprite.image
    samples: list[int] = []
    for y in range(placement.y, placement.y + sprite.height):
        start: int = (y * image.width + placement.x) * 3
        samples.extend(image.samples[start : start + sprite.width * 3])
    return Image(sprite.width, sprite.height, image.maximum, samples)


def pack(sprites: list[Sprite], settings: Json) -> Atlas:
    exact(settings, ["width", "max_height", "padding", "order", "background"])
    width: int = json_int(settings["width"])
    max_height: int = json_int(settings["max_height"])
    padding: int = json_int(settings["padding"])
    order: str = text(settings["order"])
    assert 1 <= width <= 1024 and 1 <= max_height <= 1024 and 0 <= padding <= 16, "atlas size or padding range"
    assert order in ["height", "input"], "unknown ordering"
    maximum: int = sprites[0].image.maximum
    background: list[Json] = json_array(settings["background"])
    assert len(background) == 3, "background requires RGB triplet"
    color: list[int] = []
    for channel in background:
        value: int = json_int(channel)
        assert 0 <= value <= maximum, "background channel range"
        color.append(value)
    if order == "height":
        sprites = sorted(sprites, key=by_size)
    shelves: list[Shelf] = []
    placements: list[Placement] = []
    height: int = 0
    pixels: int = 0
    for sprite in sprites:
        image: Image = sprite.image
        assert image.maximum == maximum, "sprite Maxval mismatch"
        pixels = pixels + image.width * image.height
        assert pixels <= 1048576, "combined source pixel limit"
        padded_width: int = image.width + 2 * padding
        padded_height: int = image.height + 2 * padding
        assert padded_width <= width, "sprite wider than atlas"
        selected: int = -1
        for index in range(len(shelves)):
            shelf: Shelf = shelves[index]
            if padded_height <= shelf.height and shelf.used + padded_width <= width:
                selected = index
                break
        if selected < 0:
            assert height + padded_height <= max_height, "shelf packing exceeds height"
            selected = len(shelves)
            shelves.append(Shelf(height, padded_height, 0))
            height = height + padded_height
        shelf: Shelf = shelves[selected]
        placements.append(Placement(sprite, shelf.used + padding, shelf.y + padding, selected))
        shelf.used = shelf.used + padded_width
        shelves[selected] = shelf
    canvas: list[int] = []
    for pixel in range(width * height):
        canvas.extend(color)
    items: list[Json] = []
    for placed in placements:
        sprite: Sprite = placed.sprite
        image: Image = sprite.image
        for y in range(image.height):
            for x in range(image.width * 3):
                canvas[((placed.y + y) * width + placed.x) * 3 + x] = image.samples[y * image.width * 3 + x]
        items.append(
            {
                "index": sprite.index,
                "name": sprite.name,
                "x": placed.x,
                "y": placed.y,
                "width": image.width,
                "height": image.height,
                "shelf": placed.shelf,
                "source_sha256": digest(sprite.data),
                "raster_sha256": digest(raster(image)),
                "extracted_sha256": digest(encode(image)),
            }
        )
    shelf_rows: list[Json] = []
    for shelf in shelves:
        shelf_rows.append({"y": shelf.y, "height": shelf.height, "used_width": shelf.used})
    image: Image = Image(width, height, maximum, canvas)
    results: Json = {
        "width": width,
        "height": height,
        "maxval": maximum,
        "source_pixels": pixels,
        "background_pixels": width * height - pixels,
        "items": items,
        "shelves": shelf_rows,
        "atlas_sha256": digest(encode(image)),
        "raster_sha256": digest(raster(image)),
    }
    return Atlas(image, placements, results)
