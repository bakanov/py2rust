"""Self-contained SVG sampled previews, labeled with original pixel dimensions."""

from model import Image


def panel(image: Image, left: int, title: str) -> str:
    width: int = image.width
    height: int = image.height
    if max(width, height) > 128:
        if width >= height:
            width = 128
            height = max(1, image.height * 128 // image.width)
        else:
            height = 128
            width = max(1, image.width * 128 // image.height)
    lines: list[str] = [
        '<text x="' + str(left) + '" y="34" font-size="20">' + title + "</text>",
        '<text x="'
        + str(left)
        + '" y="58" fill="#64748b">'
        + str(image.width)
        + " × "
        + str(image.height)
        + " · Maxval "
        + str(image.maximum)
        + "</text>",
        '<svg x="'
        + str(left)
        + '" y="80" width="256" height="256" viewBox="0 0 '
        + str(width)
        + " "
        + str(height)
        + '" preserveAspectRatio="xMidYMid meet" shape-rendering="crispEdges">',
    ]
    for y in range(height):
        source_y: int = (2 * y + 1) * image.height // (2 * height)
        for x in range(width):
            source_x: int = (2 * x + 1) * image.width // (2 * width)
            offset: int = (source_y * image.width + source_x) * 3
            color: str = ""
            for channel in range(3):
                value: int = (image.samples[offset + channel] * 255 + image.maximum // 2) // image.maximum
                color = color + value.to_bytes(1, "big").hex()
            lines.append('<rect x="' + str(x) + '" y="' + str(y) + '" width="1" height="1" fill="#' + color + '"/>')
    lines.append("</svg>")
    return "\n".join(lines)


def preview(original: Image, filtered: Image) -> bytes:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="380" viewBox="0 0 600 380">'
        '<rect width="600" height="380" fill="#f8fafc"/><g font-family="sans-serif" fill="#253349">'
        + panel(original, 24, "Original")
        + panel(filtered, 320, "Filtered")
        + '<text x="24" y="365" font-size="12">Sampled RGB preview · no gamma conversion · full data in PPM/CSV</text>'
        + "</g></svg>\n"
    ).encode()
