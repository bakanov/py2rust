"""Ordered exact-sample filters and full-resolution channel histograms."""

from dataclasses import dataclass

from model import Image, digest, exact, text
from ppm import decode, encode, raster

from py2rust.stdlib import Json, json_array, json_int


@dataclass
class Result:
    original: Image
    filtered: Image
    summary: Json


def histogram(image: Image) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    channels: list[str] = ["red", "green", "blue"]
    for channel in range(3):
        counts: list[int] = []
        for value in range(image.maximum + 1):
            counts.append(0)
        for offset in range(channel, len(image.samples), 3):
            value: int = image.samples[offset]
            counts[value] = counts[value] + 1
        result[channels[channel]] = counts
    return result


def describe(image: Image, data: bytes) -> Json:
    samples: bytes = raster(image)
    return {
        "width": image.width,
        "height": image.height,
        "maxval": image.maximum,
        "header_bytes": len(data) - len(samples),
        "raster_sha256": digest(samples),
        "file_sha256": digest(data),
        "histogram": histogram(image),
    }


def apply(image: Image, operation: Json) -> Image:
    kind: str = text(operation["op"])
    samples: list[int] = []
    if kind == "crop":
        exact(operation, ["op", "x", "y", "width", "height"])
        x: int = json_int(operation["x"])
        y: int = json_int(operation["y"])
        width: int = json_int(operation["width"])
        height: int = json_int(operation["height"])
        assert x >= 0 and y >= 0 and width > 0 and height > 0, "crop range"
        assert x + width <= image.width and y + height <= image.height, "crop outside image"
        for row in range(y, y + height):
            for offset in range((row * image.width + x) * 3, (row * image.width + x + width) * 3):
                samples.append(image.samples[offset])
        return Image(width, height, image.maximum, samples)
    if kind == "invert":
        exact(operation, ["op"])
        for value in image.samples:
            samples.append(image.maximum - value)
    else:
        assert kind == "threshold", "unknown filter"
        exact(operation, ["op", "value", "mode"])
        threshold: int = json_int(operation["value"])
        mode: str = text(operation["mode"])
        assert 0 <= threshold <= image.maximum and mode in ["channel", "mean"], "threshold range or mode"
        for offset in range(0, len(image.samples), 3):
            total: int = image.samples[offset] + image.samples[offset + 1] + image.samples[offset + 2]
            for channel in range(3):
                white: bool = (
                    image.samples[offset + channel] >= threshold if mode == "channel" else total >= 3 * threshold
                )
                samples.append(image.maximum if white else 0)
    return Image(image.width, image.height, image.maximum, samples)


def process(source: bytes, pipeline: Json) -> Result:
    operations: list[Json] = json_array(pipeline)
    assert len(operations) <= 32, "filter count limit"
    original: Image = decode(source)
    current: Image = original
    processed: int = current.width * current.height
    steps: list[Json] = []
    for index in range(len(operations)):
        processed = processed + current.width * current.height
        assert processed <= 4194304, "processing pixel budget"
        current = apply(current, operations[index])
        steps.append(
            {
                "index": index,
                "filter": operations[index],
                "width": current.width,
                "height": current.height,
                "raster_sha256": digest(raster(current)),
            }
        )
    summary: Json = {
        "input": describe(original, source),
        "output": describe(current, encode(current)),
        "steps": steps,
        "processed_pixels": processed,
    }
    return Result(original, current, summary)
