"""Independent wave/struct/Decimal sample oracles and exact CSV/SVG export inspection."""

from __future__ import annotations

import csv
import decimal
import hashlib
import io
import json
import math
import struct
import wave
import xml.etree.ElementTree as ET
from typing import Any


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if type(item) is float:
            assert math.isfinite(item)
            mantissa, exponent = format(item, ".16e").split("e")
            return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        return json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    return (encode(value) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def pcm_wave(samples: list[int], rate: int = 8000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, rate, len(samples), "NONE", "not compressed"))
        output.writeframes(struct.pack("<" + str(len(samples)) + "h", *samples))
    return buffer.getvalue()


def read_wave(raw: bytes) -> tuple[int, list[int]]:
    with wave.open(io.BytesIO(raw), "rb") as source:
        assert source.getnchannels() == 1 and source.getsampwidth() == 2 and source.getcomptype() == "NONE"
        rate = source.getframerate()
        count = source.getnframes()
        samples = list(struct.unpack("<" + str(count) + "h", source.readframes(count)))
        assert source.readframes(1) == b""
    return rate, samples


def chunks(parts: list[tuple[bytes, bytes]], pad: bytes = b"\0") -> bytes:
    body = b"WAVE" + b"".join(
        name + struct.pack("<I", len(data)) + data + pad * (len(data) % 2) for name, data in parts
    )
    return b"RIFF" + struct.pack("<I", len(body)) + body


def parts_of(raw: bytes) -> list[tuple[bytes, bytes]]:
    parts = []
    cursor = 12
    while cursor < len(raw):
        name, count = struct.unpack_from("<4sI", raw, cursor)
        parts.append((name, raw[cursor + 8 : cursor + 8 + count]))
        cursor += 8 + count + count % 2
    assert cursor == len(raw)
    return parts


def source_values(raw: bytes) -> tuple[int, list[int], list[dict]]:
    parts = parts_of(raw)
    values = dict(parts)
    fmt = struct.unpack("<HHIIHH", values[b"fmt "][:16])
    assert fmt[0] == fmt[1] == 1 and fmt[4:] == (2, 16) and fmt[3] == fmt[2] * 2
    audio = values[b"data"]
    samples = list(struct.unpack("<" + str(len(audio) // 2) + "h", audio))
    offset = 12
    inventory = []
    for name, data in parts:
        inventory.append(
            {
                "id_hex": name.hex(),
                "offset": offset,
                "bytes": len(data),
                "padding_bytes": len(data) % 2,
                "sha256": digest(data),
            }
        )
        offset += 8 + len(data) + len(data) % 2
    if next(i for i, (n, _) in enumerate(parts) if n == b"fmt ") < next(
        i for i, (n, _) in enumerate(parts) if n == b"data"
    ):
        assert read_wave(raw) == (fmt[2], samples)
    return fmt[2], samples, inventory


def normalize(samples: list[int], settings: dict) -> tuple[list[int], dict, int, int]:
    peak = max(map(abs, samples), default=0)
    if settings["method"] == "peak":
        numerator, denominator = (settings["target"], peak) if peak else (1, 1)
    else:
        numerator, denominator = settings["numerator"], settings["denominator"]
    with decimal.localcontext() as context:
        context.prec = 50
        rounded = [
            int(
                (decimal.Decimal(sample * numerator) / decimal.Decimal(denominator)).to_integral_value(
                    rounding=decimal.ROUND_HALF_UP
                )
            )
            for sample in samples
        ]
    converted = [max(-32768, min(32767, sample)) for sample in rounded]
    return (
        converted,
        {"numerator": numerator, "denominator": denominator},
        sum(v < -32768 for v in rounded),
        sum(v > 32767 for v in rounded),
    )


def inspect_statistics(found: dict, samples: list[int], rate: int) -> None:
    expected = {
        "samples": len(samples),
        "minimum": min(samples, default=None),
        "maximum": max(samples, default=None),
        "peak": max(map(abs, samples), default=0),
        "sum": sum(samples),
        "sum_squares": sum(v * v for v in samples),
    }
    assert found.keys() == expected.keys() | {"mean", "rms", "duration_seconds"}
    assert canonical({k: found[k] for k in expected}) == canonical(expected)
    assert type(found["mean"]) is float and found["mean"] == sum(samples) / max(1, len(samples))
    assert type(found["duration_seconds"]) is float and found["duration_seconds"] == len(samples) / rate
    with decimal.localcontext() as context:
        context.prec = 70
        exact = (decimal.Decimal(expected["sum_squares"]) / decimal.Decimal(max(1, len(samples)))).sqrt()
    assert type(found["rms"]) is float and math.isclose(found["rms"], float(exact), rel_tol=2e-15, abs_tol=0)
    return  # noqa: PLR1711


def inspect_results(raw: bytes, settings: dict, results: dict) -> tuple[list[int], list[int]]:
    rate, before, inventory = source_values(raw)
    after, gain, low, high = normalize(before, settings)
    assert results.keys() == {
        "sample_rate",
        "source_bytes",
        "chunks",
        "gain",
        "input",
        "output",
        "changed_samples",
        "clipped_low",
        "clipped_high",
        "waveform",
        "normalized_sha256",
    }
    expected = {
        "sample_rate": rate,
        "source_bytes": len(raw),
        "chunks": inventory,
        "gain": gain,
        "changed_samples": sum(a != b for a, b in zip(before, after)),
        "clipped_low": low,
        "clipped_high": high,
        "normalized_sha256": digest(pcm_wave(after, rate)),
    }
    assert canonical({k: results[k] for k in expected}) == canonical(expected)
    inspect_statistics(results["input"], before, rate)
    inspect_statistics(results["output"], after, rate)
    count = min(256, len(before))
    expected_rows = []
    for i in range(count):
        start, end = i * len(before) // count, (i + 1) * len(before) // count
        expected_rows.append(
            {
                "start": start,
                "end": end,
                "input_min": min(before[start:end]),
                "input_max": max(before[start:end]),
                "output_min": min(after[start:end]),
                "output_max": max(after[start:end]),
            }
        )
    assert canonical(results["waveform"]) == canonical(expected_rows)
    return before, after


def inspect_csv(raw: bytes, before: list[int], after: list[int]) -> None:
    rows = list(csv.reader(io.StringIO(raw.decode())))
    assert rows.pop(0) == ["sample", "input", "output"]
    assert rows == [[str(i), str(a), str(b)] for i, (a, b) in enumerate(zip(before, after))]
    return  # noqa: PLR1711


def inspect_svg(raw: bytes, results: dict) -> None:
    svg = ET.fromstring(raw)
    ns = "{http://www.w3.org/2000/svg}"
    assert svg.tag == ns + "svg" and svg.attrib == {"width": "1000", "height": "660", "viewBox": "0 0 1000 660"}
    assert svg.find(ns + "title").text == "WAV level preview"
    assert all(n.tag in {ns + t for t in ["svg", "title", "desc", "rect", "g", "text", "path"]} for n in svg.iter())
    assert all(not key.startswith("on") and "href" not in key for node in svg.iter() for key in node.attrib)
    count = results["input"]["samples"]
    spans = results["waveform"]
    for label, center, color in [("input", 200, "#2678c8"), ("output", 480, "#d25c32")]:
        paths = [p for p in svg.findall(".//" + ns + "path") if p.attrib.get("class") == label]
        assert len(paths) == len(spans)
        for path, row in zip(paths, spans):
            x = 80 + (row["start"] + row["end"]) * 880 // (2 * count)
            low, high = row[label + "_min"], row[label + "_max"]
            top, bottom = center - math.floor(high * 100 / 32768), center - math.floor(low * 100 / 32768)
            assert 80 <= x <= 960 and center - 100 <= top <= bottom <= center + 100
            assert path.attrib == {
                "class": label,
                "d": f"M{x} {top} V{bottom}",
                "stroke": color,
                "stroke-width": "2",
                "stroke-linecap": "round",
            }
            assert path.find(ns + "title").text == f'Samples {row["start"]}..{row["end"]}: {low}..{high}'
    texts = [n.text for n in svg.findall(".//" + ns + "text")]
    assert texts.count("No samples") == (2 if count == 0 else 0)
    assert f'Samples: {count} · Rate: {results["sample_rate"]} Hz' in texts
    assert f'Clamped samples: {results["clipped_low"]+results["clipped_high"]}' in texts
    return  # noqa: PLR1711
