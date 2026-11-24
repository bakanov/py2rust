"""Parse one bounded P6 image, preserving the exact header/raster boundary and sample depth."""

from dataclasses import dataclass

from model import Image


@dataclass
class Token:
    value: int
    end: int


def whitespace(value: int) -> bool:
    return value in [9, 10, 11, 12, 13, 32]


def comment_end(data: bytes, start: int) -> int:
    at: int = start
    while at < len(data) and data[at] not in [10, 13]:
        assert at < 65536, "header byte limit"
        at = at + 1
    return at


def number(data: bytes, start: int) -> Token:
    at: int = start
    while at < len(data):
        assert at < 65536, "header byte limit"
        if whitespace(data[at]):
            at = at + 1
        elif data[at] == 35:
            at = comment_end(data, at)
        else:
            break
    value: int = 0
    digits: int = 0
    while at < len(data) and 48 <= data[at] <= 57:
        assert at < 65536 and digits < 5, "numeric token or header limit"
        value = value * 10 + data[at] - 48
        at = at + 1
        digits = digits + 1
    assert digits > 0 and at < len(data), "missing or unterminated number"
    assert whitespace(data[at]) or data[at] == 35, "invalid numeric separator"
    return Token(value, at)


def decode(data: bytes) -> Image:
    assert len(data) >= 3 and data[:2] == b"P6", "expected P6"
    assert whitespace(data[2]) or data[2] == 35, "missing magic separator"
    width: Token = number(data, 2)
    height: Token = number(data, width.end)
    maximum: Token = number(data, height.end)
    assert 1 <= width.value <= 1024 and 1 <= height.value <= 1024, "image dimension limit"
    assert width.value * height.value <= 262144, "image pixel limit"
    assert 1 <= maximum.value <= 65535, "Maxval range"
    at: int = comment_end(data, maximum.end) if data[maximum.end] == 35 else maximum.end
    assert at < len(data) and whitespace(data[at]), "missing raster separator"
    at = at + 1
    assert at <= 65536, "header byte limit"
    size: int = 1 if maximum.value < 256 else 2
    assert len(data) - at == width.value * height.value * 3 * size, "raster byte count"
    samples: list[int] = []
    for offset in range(at, len(data), size):
        value: int = data[offset] if size == 1 else data[offset] * 256 + data[offset + 1]
        assert value <= maximum.value, "sample exceeds Maxval"
        samples.append(value)
    return Image(width.value, height.value, maximum.value, samples)


def raster(image: Image) -> bytes:
    output: bytearray = bytearray()
    size: int = 1 if image.maximum < 256 else 2
    for value in image.samples:
        output.extend(value.to_bytes(size, "big"))
    return bytes(output)


def encode(image: Image) -> bytes:
    header: str = "P6\n" + str(image.width) + " " + str(image.height) + "\n" + str(image.maximum) + "\n"
    return header.encode() + raster(image)
