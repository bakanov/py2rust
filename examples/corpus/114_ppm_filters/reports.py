"""Original-preserving binary exports, exact histograms and directly usable replay requests."""

# ruff: noqa: PLC0206 - subset dictionary iteration

from filters import Result, histogram
from model import digest, encoded
from ppm import encode
from preview import preview

from py2rust.stdlib import Json, pretty


def histogram_csv(result: Result) -> bytes:
    before: dict[str, list[int]] = histogram(result.original)
    after: dict[str, list[int]] = histogram(result.filtered)
    red_before: list[int] = before["red"]
    green_before: list[int] = before["green"]
    blue_before: list[int] = before["blue"]
    red_after: list[int] = after["red"]
    green_after: list[int] = after["green"]
    blue_after: list[int] = after["blue"]
    lines: list[str] = ["value,red_input,red_output,green_input,green_output,blue_input,blue_output"]
    for value in range(result.original.maximum + 1):
        counts: list[int] = [
            red_before[value],
            red_after[value],
            green_before[value],
            green_after[value],
            blue_before[value],
            blue_after[value],
        ]
        total: int = 0
        for count in counts:
            total = total + count
        if total > 0:
            row: str = str(value)
            for count in counts:
                row = row + "," + str(count)
            lines.append(row)
    return ("\n".join(lines) + "\n").encode()


def bundle(mode: str, source: bytes, pipeline: Json, result: Result) -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "original.ppm": source,
        "filtered.ppm": encode(result.filtered),
        "preview.svg": preview(result.original, result.filtered),
        "histogram.csv": histogram_csv(result),
        "archive.json": encoded(
            {"version": 1, "source_hex": source.hex(), "pipeline": pipeline, "results": result.summary}
        ),
        "report.json": (pretty({"version": 1, "mode": mode, "results": result.summary}) + "\n").encode(),
        "process.json": encoded(
            {"version": 1, "mode": "process", "input": "original.ppm", "output": "processed", "pipeline": pipeline}
        ),
        "replay.json": encoded({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    manifest: Json = {}
    for name in files:
        assert len(files[name]) <= 16777216, "export byte limit"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = encoded(manifest)
    return files
