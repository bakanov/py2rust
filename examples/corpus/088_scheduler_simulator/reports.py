"""Export exact trace/statistics, replay inputs and a digest manifest as one bundle."""

# ruff: noqa: I001, PLC0206 - compact imports and explicit subset dictionary iteration
from simulation import State
from py2rust.stdlib import Json, json_canonical, json_int, json_string, sha256_digest, sha256_new, sha256_update


def summarize(state: State, workers: int, generator: Json) -> Json:
    waiting: int = 0
    response: int = 0
    completed_wait: int = 0
    for job in state.jobs:
        arrival: int = json_int(job["arrival"])
        started: int = json_int(job["started"])
        finished: int = json_int(job["finished"])
        if started >= 0:
            completed_wait = completed_wait + started - arrival
            response = response + finished - arrival
        waiting = waiting + (started if started >= 0 else finished) - arrival
    completed: int = state.counts["on_time"] + state.counts["late"]
    assert waiting == state.queue_area, "queue time integral disagrees with outcomes"
    return {
        "version": 1,
        "generator": generator,
        "jobs": len(state.jobs),
        "counts": state.counts,
        "horizon_ticks": state.now,
        "peak_queue": state.peak_queue,
        "trace_records": len(state.trace),
        "queue_ticks": state.queue_area,
        "busy_ticks": state.busy_area,
        "utilization": {"numerator": state.busy_area, "denominator": workers * state.now},
        "mean_queue": {"numerator": state.queue_area, "denominator": state.now},
        "mean_completed_wait": {"numerator": completed_wait, "denominator": completed},
        "mean_completed_response": {"numerator": response, "denominator": completed},
    }


def render(config: Json, jobs: list[Json], state: State, summary: Json) -> dict[str, bytes]:
    trace: list[str] = []
    for event in state.trace:
        trace.append(json_canonical(event))
    text: list[str] = [
        "Discrete-event scheduler",
        "Counts: " + json_canonical(summary["counts"]),
        "Horizon: " + str(state.now) + " ticks",
        "Statistics: " + json_canonical(summary),
    ]
    for job in state.jobs:
        text.append(
            json_string(job["id"])
            + ": "
            + json_string(job["status"])
            + " start="
            + json_canonical(job["started"])
            + " finish="
            + json_canonical(job["finished"])
        )
    replay: Json = config
    replay["output"] = "replayed"
    explicit: Json = {
        "version": 1,
        "workers": config["workers"],
        "queue_capacity": config["queue_capacity"],
        "workload": {"mode": "explicit", "jobs": jobs},
        "output": "replayed",
    }
    files: dict[str, bytes] = {
        "summary.json": (json_canonical(summary) + "\n").encode(),
        "jobs.json": (json_canonical(state.jobs) + "\n").encode(),
        "trace.jsonl": (("\n".join(trace) + "\n") if len(trace) > 0 else "").encode(),
        "report.txt": ("\n".join(text) + "\n").encode(),
        "scheduler-job.json": (json_canonical(replay) + "\n").encode(),
        "resolved-job.json": (json_canonical(explicit) + "\n").encode(),
    }
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 4194304, "report bundle exceeds 4 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": manifest}) + "\n").encode()
    return files
