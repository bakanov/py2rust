"""Render comparable population series on one linear scale, including flat and one-point data."""

from model import display, text

from py2rust.stdlib import Json, floor, json_array, json_canonical, json_float


def escaped(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def short(value: str, length: int) -> str:
    return value if len(value) <= length else value[: length - 3] + "..."


def render(title: str, results: Json) -> bytes:
    rows: list[Json] = json_array(results["series"])
    times: list[Json] = json_array(results["times"])
    ceiling: float = 0.0
    for row in rows:
        ceiling = max(ceiling, json_float(row["maximum"]))
    scale: float = ceiling if ceiling > 0.0 else 1.0
    horizon: float = json_float(times[-1])
    duration: float = horizon if horizon > 0.0 else 1.0
    height: int = 460 + len(rows) * 22
    colors: list[str] = [
        "#2678c8",
        "#cf4a36",
        "#28834b",
        "#8c52b8",
        "#b97808",
        "#007e87",
        "#b34e8f",
        "#515a66",
        "#184b80",
        "#802e22",
        "#19542f",
        "#573374",
        "#765006",
        "#004e55",
        "#713158",
        "#262d35",
    ]
    shown: str = display(title)
    lines: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="'
        + str(height)
        + '" viewBox="0 0 1000 '
        + str(height)
        + '">',
        "<title>" + escaped(shown) + "</title>",
        (
            "<desc>Fixed-step RK4 population comparison. Time on the horizontal axis; population on the vertical axis. "
            "All series share a linear scale.</desc>"
        ),
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        '<g font-family="DejaVu Sans, sans-serif" fill="#243145">',
        '<text x="80" y="36" font-size="18">' + escaped(short(shown, 32)) + "</text>",
        '<text x="80" y="61" font-size="12">Population · fixed-step RK4 · shared linear scale</text>',
        '<path d="M80 80 V380 H960" fill="none" stroke="#708095"/>',
        '<text x="80" y="75" font-size="10">Max: ' + json_canonical(ceiling) + "</text>",
        '<text x="60" y="384" font-size="12">0</text>',
        '<text x="80" y="400" font-size="12">0</text>',
        '<text x="960" y="400" text-anchor="end" font-size="12">' + json_canonical(horizon) + "</text>",
        '<text x="520" y="421" text-anchor="middle" font-size="12">Time</text>',
    ]
    for index in range(len(rows)):
        row: Json = rows[index]
        values: list[Json] = json_array(row["values"])
        points: list[str] = []
        first_y: int = 0
        for step in range(len(times)):
            x: int = floor(80.0 + 880.0 * (json_float(times[step]) / duration) + 0.5)
            y: int = floor(80.0 + 300.0 * (1.0 - json_float(values[step]) / scale) + 0.5)
            points.append(str(x) + "," + str(y))
            if step == 0:
                first_y = y
        identifier: str = text(row["id"])
        name: str = display(text(row["name"]))
        color: str = colors[index]
        lines.append(
            '<polyline id="series-'
            + identifier
            + '" fill="none" stroke="'
            + color
            + '" stroke-width="2" points="'
            + " ".join(points)
            + '"><title>'
            + escaped(name)
            + "</title></polyline>"
        )
        lines.append(
            '<circle id="start-' + identifier + '" cx="80" cy="' + str(first_y) + '" r="3" fill="' + color + '"/>'
        )
        lines.append(
            '<text x="80" y="'
            + str(450 + index * 22)
            + '" font-size="12" fill="'
            + color
            + '"><title>'
            + escaped(identifier + " — " + name)
            + "</title>"
            + escaped(short(identifier + " — " + name, 44))
            + "</text>"
        )
    lines.append("</g></svg>")
    return ("\n".join(lines) + "\n").encode()
