"""Deterministic counters, noncumulative latency buckets and nearest-rank percentiles."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_dumps,
    json_int,
    json_is_null,
    json_kind,
    json_string,
)


def percentile(ordered: list[int], percent: int) -> int:
    index: int = (len(ordered) * percent + 99) // 100 - 1
    return ordered[index]


def summarize(samples: list[Json], boundaries: list[int]) -> Json:
    counts: dict[str, int] = {"ok": 0, "http_error": 0, "transport_error": 0, "cancelled": 0, "late": 0}
    statuses: dict[str, int] = {}
    latencies: list[int] = []
    histogram: list[int] = []
    for index in range(len(boundaries) + 1):
        histogram.append(0)
    total: int = 0
    total_bytes: int = 0
    for sample in samples:
        state: str = json_string(sample["state"])
        counts[state] = counts[state] + 1
        total_bytes = total_bytes + json_int(sample["bytes"])
        if not json_is_null(sample["latency_us"]):
            latency: int = json_int(sample["latency_us"])
            latencies.append(latency)
            total = total + latency
            code: str = str(json_int(sample["status"]))
            statuses[code] = statuses.get(code, 0) + 1
            bucket: int = 0
            while bucket < len(boundaries) and latency > boundaries[bucket] * 1000:
                bucket = bucket + 1
            histogram[bucket] = histogram[bucket] + 1
    latencies.sort()
    buckets: list[Json] = []
    for index in range(len(boundaries)):
        buckets.append({"le_ms": boundaries[index], "count": histogram[index]})
    buckets.append({"le_ms": None, "count": histogram[-1]})
    latency_summary: Json = None
    if len(latencies) > 0:
        latency_summary = {
            "min_us": latencies[0],
            "max_us": latencies[-1],
            "mean_us": total // len(latencies),
            "sum_us": total,
            "p50_us": percentile(latencies, 50),
            "p95_us": percentile(latencies, 95),
            "p99_us": percentile(latencies, 99),
        }
    return {
        "planned": len(samples),
        "attempted": len(latencies),
        "counts": counts,
        "statuses": statuses,
        "bytes": total_bytes,
        "latency": latency_summary,
        "buckets": buckets,
    }


def result(policy: Json, samples: list[Json], elapsed_us: int) -> Json:
    boundaries: list[int] = []
    for value in json_array(policy["buckets_ms"]):
        boundaries.append(json_int(value))
    groups: list[Json] = []
    targets: list[Json] = []
    for target in json_array(policy["targets"]):
        selected: list[Json] = []
        for sample in samples:
            if json_string(sample["target"]) == json_string(target["id"]):
                selected.append(sample)
        groups.append({"target": target["id"], "summary": summarize(selected, boundaries)})
        targets.append({"id": target["id"], "method": target["method"], "url": target["url"]})
    overall: Json = summarize(samples, boundaries)
    state: str = "passed"
    if json_int(overall["counts"]["http_error"]) + json_int(overall["counts"]["transport_error"]) > 0:
        state = "failed"
    if json_int(overall["counts"]["cancelled"]) + json_int(overall["counts"]["late"]) > 0:
        state = "incomplete"
    return {
        "format": 1,
        "phase": "finished",
        "status": state,
        "elapsed_us": elapsed_us,
        "parameters": {
            "concurrency": policy["concurrency"],
            "timeout_ms": policy["timeout_ms"],
            "max_body": policy["max_body"],
            "duration_ms": policy["duration_ms"],
            "max_lag_ms": policy["max_lag_ms"],
            "buckets_ms": policy["buckets_ms"],
        },
        "targets": targets,
        "plan": policy["jobs"],
        "samples": samples,
        "overall": overall,
        "by_target": groups,
    }


def csv(samples: list[Json]) -> str:
    fields: list[str] = [
        "id",
        "target",
        "scheduled_ms",
        "state",
        "reason",
        "status",
        "started_us",
        "finished_us",
        "latency_us",
        "lateness_us",
        "bytes",
        "sha256",
    ]
    lines: list[str] = [",".join(fields)]
    for sample in samples:
        values: list[str] = []
        for field in fields:
            value: Json = sample[field]
            text: str = ""
            if json_kind(value) == "str":
                text = json_string(value)
            elif not json_is_null(value):
                text = json_dumps(value)
            values.append(text)
        lines.append(",".join(values))
    return "\n".join(lines) + "\n"
