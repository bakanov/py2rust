"""Sampled atlas pixels with true-coordinate sprite outlines and escaped hover labels."""

from packing import Atlas


def escaped(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def preview(atlas: Atlas) -> bytes:
    width: int = atlas.image.width
    height: int = atlas.image.height
    samples: list[int] = atlas.image.samples
    maximum: int = atlas.image.maximum
    columns: int = min(128, width)
    rows: int = min(128, height)
    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="480" viewBox="0 0 640 480">',
        '<rect width="640" height="480" fill="#f8fafc"/><g font-family="sans-serif" fill="#253349">',
        '<text x="24" y="32" font-size="22">Sprite atlas</text>',
        '<text x="24" y="57" font-size="14">'
        + str(len(atlas.placements))
        + " sprites · "
        + str(width)
        + " × "
        + str(height)
        + " · Maxval "
        + str(maximum)
        + "</text>",
        '<svg x="24" y="80" width="592" height="350" viewBox="0 0 '
        + str(width)
        + " "
        + str(height)
        + '" preserveAspectRatio="xMidYMid meet" shape-rendering="crispEdges">',
    ]
    for y in range(rows):
        top: int = y * height // rows
        bottom: int = (y + 1) * height // rows
        for x in range(columns):
            left: int = x * width // columns
            right: int = (x + 1) * width // columns
            offset: int = (((top + bottom) // 2) * width + (left + right) // 2) * 3
            color: str = ""
            for channel in range(3):
                value: int = (samples[offset + channel] * 255 + maximum // 2) // maximum
                color = color + value.to_bytes(1, "big").hex()
            lines.append(
                '<rect x="'
                + str(left)
                + '" y="'
                + str(top)
                + '" width="'
                + str(right - left)
                + '" height="'
                + str(bottom - top)
                + '" fill="#'
                + color
                + '"/>'
            )
    for placed in atlas.placements:
        lines.append(
            '<rect x="'
            + str(placed.x)
            + '" y="'
            + str(placed.y)
            + '" width="'
            + str(placed.sprite.image.width)
            + '" height="'
            + str(placed.sprite.image.height)
            + '" fill="none" stroke="#ffffff" stroke-width="'
            + str(max(1, min(width, height) // 256))
            + '"><title>'
            + escaped(placed.sprite.name)
            + "</title></rect>"
        )
    lines.append(
        '</svg><text x="24" y="460" font-size="12">Sampled preview · outlines use exact coordinates · '
        "full pixels in atlas.ppm</text></g></svg>"
    )
    return ("\n".join(lines) + "\n").encode()
