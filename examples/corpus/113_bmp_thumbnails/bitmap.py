"""Read bounded BMP layouts into top-down BGR pixels; write canonical INFO bitmaps."""

from dataclasses import dataclass

from model import digest, signed32, unsigned

from py2rust.stdlib import Json


@dataclass
class Bitmap:
    width: int
    height: int
    pixels: bytes
    metadata: Json


def decode(data: bytes) -> Bitmap:
    assert len(data) >= 26 and data[:2] == b"BM", "expected BMP file"
    assert unsigned(data[2:6]) == len(data) and data[6:10] == b"\0\0\0\0", "file size or reserved fields"
    offset: int = unsigned(data[10:14])
    dib: int = unsigned(data[14:18])
    assert dib in [12, 40, 108, 124] and len(data) >= 14 + dib, "unsupported or truncated DIB header"
    width: int = unsigned(data[18:20]) if dib == 12 else signed32(data[18:22])
    signed_height: int = unsigned(data[20:22]) if dib == 12 else signed32(data[22:26])
    height: int = abs(signed_height)
    assert 1 <= width <= 1024 and 1 <= height <= 1024 and width * height <= 262144, "image dimension or pixel limit"
    plane_at: int = 22 if dib == 12 else 26
    assert unsigned(data[plane_at : plane_at + 2]) == 1, "expected one plane"
    assert unsigned(data[plane_at + 2 : plane_at + 4]) == 24, "only 24-bit pixels are supported"
    stride: int = (width * 3 + 3) // 4 * 4
    end: int = offset + stride * height
    palette: int = 0 if dib == 12 else unsigned(data[46:50])
    assert offset >= 14 + dib + palette * 4 and end <= len(data), "pixel offset or truncated pixel rows"
    if dib != 12:
        assert unsigned(data[30:34]) == 0, "only BI_RGB is supported"
        assert unsigned(data[34:38]) in [0, stride * height], "inconsistent image size"
    color_space: int = unsigned(data[70:74]) if dib >= 108 else 0
    profile_bytes: int = 0
    if dib == 124:
        assert unsigned(data[134:138]) == 0, "reserved V5 field"
        if color_space in [1279872587, 1296188740]:
            profile: int = 14 + unsigned(data[126:130])
            profile_bytes = unsigned(data[130:134])
            assert profile >= 14 + dib + palette * 4 and profile_bytes > 0, "invalid color profile offset or size"
            assert profile + profile_bytes <= len(data), "truncated color profile"
            assert profile + profile_bytes <= offset or profile >= end, "color profile overlaps pixels"
    pixels: bytearray = bytearray()
    for y in range(height):
        stored_y: int = height - 1 - y if signed_height > 0 else y
        start: int = offset + stored_y * stride
        pixels.extend(data[start : start + width * 3])
    metadata: Json = {
        "width": width,
        "height": height,
        "top_down": signed_height < 0,
        "dib_bytes": dib,
        "pixel_offset": offset,
        "stride": stride,
        "palette_entries": palette,
        "gap_bytes": offset - 14 - dib,
        "trailing_bytes": len(data) - end,
        "color_space": color_space,
        "profile_bytes": profile_bytes,
        "color_management": False,
        "source_sha256": digest(data),
        "pixels_sha256": digest(bytes(pixels)),
    }
    return Bitmap(width, height, bytes(pixels), metadata)


def encode(image: Bitmap) -> bytes:
    stride: int = (image.width * 3 + 3) // 4 * 4
    body: bytearray = bytearray()
    for y in range(image.height - 1, -1, -1):
        start: int = y * image.width * 3
        body.extend(image.pixels[start : start + image.width * 3])
        for padding in range(stride - image.width * 3):
            body.append(0)
    header: bytes = (40).to_bytes(4, "little") + image.width.to_bytes(4, "little")
    header = header + image.height.to_bytes(4, "little") + b"\x01\0\x18\0" + b"\0\0\0\0"
    header = header + len(body).to_bytes(4, "little") + bytes(bytearray(16))
    file_header: bytes = b"BM" + (54 + len(body)).to_bytes(4, "little") + b"\0\0\0\0" + (54).to_bytes(4, "little")
    return file_header + header + bytes(body)


def resize(image: Bitmap, width: int, height: int) -> Bitmap:
    pixels: bytearray = bytearray()
    for y in range(height):
        source_y: int = (2 * y + 1) * image.height // (2 * height)
        for x in range(width):
            source_x: int = (2 * x + 1) * image.width // (2 * width)
            at: int = (source_y * image.width + source_x) * 3
            pixels.extend(image.pixels[at : at + 3])
    return Bitmap(width, height, bytes(pixels), None)
