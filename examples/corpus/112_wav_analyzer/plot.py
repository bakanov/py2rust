"""Two waveform envelopes on the same signed16 scale, with exact sample-span tooltips."""

from py2rust.stdlib import Json, json_array, json_int


def render(results: Json) -> bytes:
    count: int = json_int(results["input"]["samples"])
    rows: list[str] = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="660" viewBox="0 0 1000 660">',
        "<title>WAV level preview</title>",
        "<desc>Input and output minimum/maximum envelopes. Both panels use the full signed16 scale.</desc>",
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        '<g font-family="DejaVu Sans, sans-serif" fill="#243145">',
        '<text x="80" y="32" font-size="22">WAV level preview</text>',
        '<text x="80" y="56">Samples: '
        + str(count)
        + " · Rate: "
        + str(json_int(results["sample_rate"]))
        + " Hz</text>",
        '<text x="80" y="635">Clamped samples: '
        + str(json_int(results["clipped_low"]) + json_int(results["clipped_high"]))
        + "</text>",
    ]
    for panel in range(2):
        label: str = "Input" if panel == 0 else "Output"
        prefix: str = "input" if panel == 0 else "output"
        center: int = 200 + panel * 280
        color: str = "#2678c8" if panel == 0 else "#d25c32"
        rows.append('<text x="80" y="' + str(center - 112) + '" font-size="18">' + label + "</text>")
        rows.append(
            '<path d="M80 ' + str(center - 100) + " V" + str(center + 100) + ' H960" fill="none" stroke="#708095"/>'
        )
        rows.append('<path d="M80 ' + str(center) + ' H960" stroke="#c4cdd7"/>')
        rows.append('<text x="15" y="' + str(center - 95) + '">32767</text>')
        rows.append('<text x="15" y="' + str(center + 100) + '">-32768</text>')
        if count == 0:
            rows.append('<text x="460" y="' + str(center - 10) + '">No samples</text>')
        for row in json_array(results["waveform"]):
            start: int = json_int(row["start"])
            end: int = json_int(row["end"])
            x: int = 80 + (start + end) * 880 // (2 * count)
            low: int = json_int(row[prefix + "_min"])
            high: int = json_int(row[prefix + "_max"])
            top: int = center - high * 100 // 32768
            bottom: int = center - low * 100 // 32768
            rows.append(
                '<path class="'
                + prefix
                + '" d="M'
                + str(x)
                + " "
                + str(top)
                + " V"
                + str(bottom)
                + '" stroke="'
                + color
                + '" stroke-width="2" stroke-linecap="round"><title>Samples '
                + str(start)
                + ".."
                + str(end)
                + ": "
                + str(low)
                + ".."
                + str(high)
                + "</title></path>"
            )
        rows.append('<text x="80" y="' + str(center + 124) + '">0</text>')
        rows.append('<text x="960" y="' + str(center + 124) + '" text-anchor="end">' + str(count) + "</text>")
    rows.append("</g></svg>")
    return ("\n".join(rows) + "\n").encode()
