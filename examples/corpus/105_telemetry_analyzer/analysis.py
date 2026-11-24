"""Analyze count-based windows; gaps reset the baseline before the next observation is tested."""

# ruff: noqa: BLE001 - invalid series do not prevent later independent series from running
from statistics import Moments, calculate, classify, describe

from model import Parameters, Sample, samples, text

from py2rust.stdlib import Json


def analyze(name: str, readings: list[Sample], settings: Parameters) -> Json:
    values: list[float] = []
    window: list[float] = []
    baseline: Moments = calculate([])
    points: list[Json] = []
    gaps: list[Json] = []
    segment: int = 0
    outliers: int = 0
    for index in range(len(readings)):
        sample: Sample = readings[index]
        elapsed: int = 0 if index == 0 else sample.timestamp - readings[index - 1].timestamp
        gap: bool = index > 0 and elapsed > settings.gap_us
        if gap:
            gaps.append(
                {
                    "before_index": index - 1,
                    "after_index": index,
                    "elapsed_us": elapsed,
                    "from": readings[index - 1].utc,
                    "to": sample.utc,
                }
            )
            segment = segment + 1
            window = []
            baseline = calculate([])
        decision: Json = classify(sample.value, baseline, settings.warmup, settings.sigma)
        if text(decision["status"]) in ["outlier", "constant_shift"]:
            outliers = outliers + 1
        before: Json = {
            "start_index": None if baseline.count == 0 else index - baseline.count,
            "end_index": None if baseline.count == 0 else index - 1,
            "statistics": describe(baseline),
        }
        window.append(sample.value)
        window = window[-settings.window :]
        baseline = calculate(window)
        points.append(
            {
                "index": index,
                "utc": sample.utc,
                "timestamp_us": sample.timestamp,
                "value": sample.value,
                "segment": segment,
                "elapsed_us": None if index == 0 else elapsed,
                "gap": gap,
                "baseline": before,
                "decision": decision,
                "window": {
                    "start_index": index + 1 - len(window),
                    "end_index": index,
                    "statistics": describe(baseline),
                },
            }
        )
        values.append(sample.value)
    return {
        "id": name,
        "status": "analyzed",
        "samples": len(readings),
        "segments": 0 if len(readings) == 0 else segment + 1,
        "outliers": outliers,
        "first_utc": None if len(readings) == 0 else readings[0].utc,
        "last_utc": None if len(readings) == 0 else readings[-1].utc,
        "statistics": describe(calculate(values)),
        "gaps": gaps,
        "points": points,
    }


def evaluate(rows: list[Json], settings: Parameters) -> list[Json]:
    results: list[Json] = []
    for row in rows:
        name: str = text(row["id"])
        try:
            readings: list[Sample] = samples(row["samples"])
            results.append(analyze(name, readings, settings))
        except Exception as error:
            results.append({"id": name, "status": "rejected", "reason": str(error)})
    return results
