"""Exact gain and quantization decisions with bounded statistics and waveform envelopes."""

import math
from dataclasses import dataclass

from binary import digest, exact, text
from pcm import Wave, encode

from py2rust.stdlib import Json, json_int


@dataclass
class Processed:
    samples: list[int]
    audio: bytes
    results: Json


def statistics(samples: list[int], rate: int) -> Json:
    total: int = 0
    squares: int = 0
    peak: int = 0
    for value in samples:
        total = total + value
        squares = squares + value * value
        peak = max(peak, abs(value))
    count: int = len(samples)
    denominator: int = max(1, count)
    return {
        "samples": count,
        "minimum": min(samples) if count > 0 else None,
        "maximum": max(samples) if count > 0 else None,
        "peak": peak,
        "sum": total,
        "sum_squares": squares,
        "mean": float(total) / float(denominator),
        "rms": math.sqrt(float(squares) / float(denominator)),
        "duration_seconds": float(count) / float(rate),
    }


def envelope(before: list[int], after: list[int]) -> list[Json]:
    rows: list[Json] = []
    count: int = len(before)
    buckets: int = min(count, 256)
    for bucket in range(buckets):
        start: int = bucket * count // buckets
        end: int = (bucket + 1) * count // buckets
        original: list[int] = before[start:end]
        changed: list[int] = after[start:end]
        rows.append(
            {
                "start": start,
                "end": end,
                "input_min": min(original),
                "input_max": max(original),
                "output_min": min(changed),
                "output_max": max(changed),
            }
        )
    return rows


def process(wave: Wave, settings: Json, source_bytes: int) -> Processed:
    method: str = text(settings["method"])
    numerator: int = 1
    denominator: int = 1
    before: Json = statistics(wave.samples, wave.rate)
    if method == "peak":
        exact(settings, ["method", "target"])
        target: int = json_int(settings["target"])
        assert 1 <= target <= 32767, "peak target range"
        if json_int(before["peak"]) != 0:
            numerator = target
            denominator = json_int(before["peak"])
    else:
        assert method == "gain", "unknown gain method"
        exact(settings, ["method", "numerator", "denominator"])
        numerator = json_int(settings["numerator"])
        denominator = json_int(settings["denominator"])
        assert 0 <= numerator <= 1000000 and 1 <= denominator <= 1000000, "gain ratio range"
    converted: list[int] = []
    clipped_low: int = 0
    clipped_high: int = 0
    changed: int = 0
    for value in wave.samples:
        magnitude: int = (abs(value) * numerator * 2 + denominator) // (denominator * 2)
        rounded: int = -magnitude if value < 0 else magnitude
        if rounded < -32768:
            clipped_low = clipped_low + 1
        if rounded > 32767:
            clipped_high = clipped_high + 1
        result: int = max(-32768, min(32767, rounded))
        if result != value:
            changed = changed + 1
        converted.append(result)
    audio: bytes = encode(wave.rate, converted)
    results: Json = {
        "sample_rate": wave.rate,
        "source_bytes": source_bytes,
        "chunks": wave.chunks,
        "gain": {"numerator": numerator, "denominator": denominator},
        "input": before,
        "output": statistics(converted, wave.rate),
        "changed_samples": changed,
        "clipped_low": clipped_low,
        "clipped_high": clipped_high,
        "waveform": envelope(wave.samples, converted),
        "normalized_sha256": digest(audio),
    }
    return Processed(converted, audio, results)
