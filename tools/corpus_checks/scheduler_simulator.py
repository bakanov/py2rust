"""Independent scanning scheduler, trace conservation audit and real publication failures."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import random
import resource
import subprocess
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .common import Application

STATUSES = ["pending", "queued", "running", "on_time", "late", "expired", "rejected"]
TERMINAL = set(STATUSES[3:])


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def job(key: str, arrival: int, service: int, deadline: int) -> dict:
    return {"id": key, "arrival": arrival, "service": service, "deadline": deadline}


def examples() -> list[dict]:
    return [
        job("exact", 0, 5, 5),
        job("expires", 0, 1, 5),
        job("waiting", 0, 3, 20),
        job("full", 0, 1, 8),
        job("zero_slack", 1, 2, 1),
        job("newcomer", 5, 5, 9),
    ]


@dataclass
class Fixture:
    root: Path
    config: dict
    filename: str = "job.json"

    @property
    def output(self) -> Path:
        return self.root / self.config["output"]

    @property
    def settings(self) -> dict:
        return {"SCHEDULER_CONFIG": str(self.root / self.filename)}

    def write(self) -> None:
        (self.root / self.filename).write_text(canonical(self.config))
        return


def fixture(
    root: Path, jobs: list[dict] | None = None, workers: int = 1, capacity: int = 2, generated: dict | None = None
) -> Fixture:
    root.mkdir(parents=True)
    config = {
        "version": 1,
        "workers": workers,
        "queue_capacity": capacity,
        "workload": (
            generated if generated is not None else {"mode": "explicit", "jobs": examples() if jobs is None else jobs}
        ),
        "output": "output",
    }
    fix = Fixture(root, copy.deepcopy(config))
    fix.write()
    return fix


def generated(seed: int, count: int = 80) -> dict:
    return {"mode": "generated", "seed": seed, "count": count, "gap": [0, 5], "service": [1, 20], "slack": [0, 30]}


def workload(config: dict) -> tuple[list[dict], dict]:
    spec = config["workload"]
    if spec["mode"] == "explicit":
        return copy.deepcopy(spec["jobs"]), {"algorithm": "none", "seed": 0, "state": 0, "draws": 0}
    # Jump directly to the nth state by modular exponentiation, independently of the application's recurrence.
    modulus, states, draws, position, jobs = 2147483647, 2147483646, 0, 0, []
    final_state = spec["seed"]
    for index in range(spec["count"]):
        values = []
        for key in ["gap", "service", "slack"]:
            low, high = spec[key]
            width = high - low + 1
            while True:
                draws += 1
                final_state = spec["seed"] * pow(16807, draws, modulus) % modulus
                bucket, remainder = divmod(final_state - 1, width)
                if bucket < states // width:
                    values.append(low + remainder)
                    break
        position += values[0]
        jobs.append(job("job_" + str(index + 1), position, values[1], position + values[2]))
    return jobs, {"algorithm": "park-miller-16807-v1", "seed": spec["seed"], "state": final_state, "draws": draws}


def reference(config: dict) -> tuple[dict, list[dict], list[dict], list[dict]]:
    inputs, generator = workload(config)
    rows = [dict(row, status="pending", started=-1, finished=-1, worker=-1) for row in inputs]
    trace, now = [], 0

    def emit(index: int, status: str, worker: int = -1) -> None:
        row = rows[index]
        row["status"] = status
        if status == "running":
            row.update(started=now, worker=worker)
        elif status in TERMINAL:
            row["finished"] = now
        counts = Counter(item["status"] for item in rows)
        trace.append(
            {
                "sequence": len(trace) + 1,
                "tick": now,
                "job": row["id"],
                "status": status,
                "worker": row["worker"],
                **{name: counts[name] for name in STATUSES[:3]},
                "terminal": sum(counts[name] for name in TERMINAL),
            }
        )
        return

    def available() -> list[int]:
        occupied = {row["worker"] for row in rows if row["status"] == "running"}
        return [index for index in range(config["workers"]) if index not in occupied]

    while any(row["status"] not in TERMINAL for row in rows):
        candidates = [row["arrival"] for row in rows if row["status"] == "pending"]
        candidates += [row["started"] + row["service"] for row in rows if row["status"] == "running"]
        candidates += [row["deadline"] for row in rows if row["status"] == "queued"]
        now = min(candidates)
        for index, row in enumerate(rows):
            if row["status"] == "running" and row["started"] + row["service"] == now:
                emit(index, "on_time" if now <= row["deadline"] else "late")
        for index, row in enumerate(rows):
            if row["status"] == "queued" and row["deadline"] == now:
                emit(index, "expired")
        waiting = sorted((row["arrival"], index) for index, row in enumerate(rows) if row["status"] == "queued")
        for (_, index), worker in zip(waiting, available()):
            emit(index, "running", worker)
        for index, row in enumerate(rows):
            if row["status"] != "pending" or row["arrival"] != now:
                continue
            idle = available()
            if row["deadline"] == now:
                emit(index, "expired")
            elif idle:
                emit(index, "running", idle[0])
            elif sum(item["status"] == "queued" for item in rows) < config["queue_capacity"]:
                emit(index, "queued")
            else:
                emit(index, "rejected")
    counts = {name: sum(row["status"] == name for row in rows) for name in STATUSES}
    completed = [row for row in rows if row["status"] in ["on_time", "late"]]
    queue_ticks = sum((row["started"] if row["started"] >= 0 else row["finished"]) - row["arrival"] for row in rows)
    busy_ticks = sum(row["service"] for row in completed)
    summary = {
        "version": 1,
        "generator": generator,
        "jobs": len(rows),
        "counts": counts,
        "horizon_ticks": now,
        "peak_queue": max((row["queued"] for row in trace), default=0),
        "trace_records": len(trace),
        "queue_ticks": queue_ticks,
        "busy_ticks": busy_ticks,
        "utilization": {"numerator": busy_ticks, "denominator": config["workers"] * now},
        "mean_queue": {"numerator": queue_ticks, "denominator": now},
        "mean_completed_wait": {
            "numerator": sum(row["started"] - row["arrival"] for row in completed),
            "denominator": len(completed),
        },
        "mean_completed_response": {
            "numerator": sum(row["finished"] - row["arrival"] for row in completed),
            "denominator": len(completed),
        },
    }
    return summary, rows, trace, inputs


def audit_trace(config: dict, summary: dict, rows: list[dict], trace: list[dict]) -> None:
    states = {row["id"]: "pending" for row in rows}
    metadata = {row["id"]: row for row in rows}
    transitions = {
        "pending": {"running", "queued", "rejected", "expired"},
        "queued": {"running", "expired"},
        "running": {"on_time", "late"},
    }
    assignments, queue_area, busy_area, clock = {}, 0, 0, 0
    for index, event in enumerate(trace):
        tick = event["tick"]
        assert tick >= clock and event["sequence"] == index + 1
        queue_area += (tick - clock) * sum(value == "queued" for value in states.values())
        busy_area += (tick - clock) * len(assignments)
        clock = tick
        key, status = event["job"], event["status"]
        assert status in transitions.get(states[key], set())
        states[key] = status
        row = metadata[key]
        assert tick >= row["arrival"]
        if status == "running":
            worker = event["worker"]
            assert 0 <= worker < config["workers"] and worker not in assignments
            assert tick < row["deadline"] and tick == row["started"]
            assignments[worker] = key
        elif status in ["on_time", "late"]:
            assert assignments.pop(event["worker"]) == key
            assert tick == row["started"] + row["service"] == row["finished"]
            assert (tick <= row["deadline"]) == (status == "on_time")
        elif status == "expired":
            assert tick == row["deadline"] == row["finished"] and event["worker"] == -1
        elif status == "rejected":
            assert tick == row["arrival"] == row["finished"] and event["worker"] == -1
        counts = Counter(states.values())
        assert all(event[name] == counts[name] for name in STATUSES[:3])
        assert event["terminal"] == sum(counts[name] for name in TERMINAL)
        assert sum(event[name] for name in ["pending", "queued", "running", "terminal"]) == len(rows)
        assert event["queued"] <= config["queue_capacity"] and event["running"] == len(assignments)
    assert all(value in TERMINAL for value in states.values()) and not assignments
    assert queue_area == summary["queue_ticks"] and busy_area == summary["busy_ticks"]
    assert clock == summary["horizon_ticks"]
    return


def verify(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {
        "summary.json",
        "jobs.json",
        "trace.jsonl",
        "report.txt",
        "scheduler-job.json",
        "resolved-job.json",
        "manifest.json",
    }
    summary, rows, trace, inputs = reference(fix.config)
    assert json.loads(files["summary.json"]) == summary
    assert json.loads(files["jobs.json"]) == rows
    assert [json.loads(line) for line in files["trace.jsonl"].splitlines()] == trace
    assert files["summary.json"] == (canonical(summary) + "\n").encode()
    assert files["jobs.json"] == (canonical(rows) + "\n").encode()
    assert files["trace.jsonl"] == "".join(canonical(event) + "\n" for event in trace).encode()
    audit_trace(fix.config, summary, rows, trace)
    assert json.loads(files["scheduler-job.json"]) == dict(fix.config, output="replayed")
    assert json.loads(files["resolved-job.json"]) == dict(
        fix.config, output="replayed", workload={"mode": "explicit", "jobs": inputs}
    )
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(data), "sha256": digest(data)}
            for name, data in files.items()
            if name != "manifest.json"
        },
    }
    assert ("Counts: " + canonical(summary["counts"])) in files["report.txt"].decode()
    for row in rows:
        assert (
            f"{row['id']}: {row['status']} start={row['started']} finish={row['finished']}"
            in files["report.txt"].decode()
        )
    return summary, files


def run(app: Application, fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    result = app.run(fix.root, fix.settings, timeout=60)
    assert result.returncode == 0, result.stderr
    summary, files = verify(fix)
    assert json.loads(result.stdout) == summary
    assert not list(fix.root.glob(".scheduler-*"))
    return summary, files


def rejected(app: Application, fix: Fixture, fragment: str = "") -> None:
    before = (fix.root / fix.filename).read_bytes() if (fix.root / fix.filename).is_file() else None
    result = app.run(fix.root, fix.settings)
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert fragment in result.stderr
    assert not fix.output.exists() and not list(fix.root.glob(".scheduler-*"))
    if before is not None:
        assert (fix.root / fix.filename).read_bytes() == before
    return


def semantics(app: Application, root: Path) -> dict:
    records = []
    cases = [
        ([], 1, 0),
        (examples(), 1, 2),
        (examples(), 2, 0),
        (examples(), 4, 4),
        ([job("no_time", 0, 1, 0)], 1, 0),
        ([job("late", 0, 8, 1)], 1, 1),
        ([job("future", 1000000000, 1000000, 2000000000)], 32, 512),
        ([job("B", 8, 2, 20), job("A", 0, 10, 10), job("C", 3, 1, 10)], 1, 2),
        ([job("A", 0, 5, 5), job("B", 0, 5, 5), job("C", 5, 1, 6), job("D", 0, 1, 5), job("E", 0, 1, 6)], 2, 3),
    ]
    rng = random.Random(880071)
    for case in range(32):
        jobs = [
            job("j" + str(index), arrival := rng.randrange(35), rng.randrange(1, 16), arrival + rng.randrange(30))
            for index in range(rng.randrange(1, 100))
        ]
        rng.shuffle(jobs)
        cases.append((jobs, rng.randrange(1, 6), rng.randrange(9)))
    for index, (jobs, workers, capacity) in enumerate(cases):
        fix = fixture(root / f"explicit-{index}", jobs, workers, capacity)
        summary, files = run(app, fix)
        records.append(digest(files["trace.jsonl"]))
        if index == 1:
            assert summary["counts"] == {
                "pending": 0,
                "queued": 0,
                "running": 0,
                "on_time": 2,
                "late": 1,
                "expired": 2,
                "rejected": 1,
            }
            assert summary["queue_ticks"] == 13 and summary["busy_ticks"] == 13
    seeds = [1, 2, 127, 20261014, 2147483646, 2147483645]
    # First state is M-1, forcing rejection for the million-wide gap range.
    rejection_seed = (2147483646 * pow(16807, -1, 2147483647)) % 2147483647
    vectors = [
        16807,
        282475249,
        1622650073,
        984943658,
        1144108930,
        470211272,
        101027544,
        1457850878,
        1458777923,
        2007237709,
    ]
    assert [pow(16807, i, 2147483647) for i in range(1, 11)] == vectors
    # Each one-job workload consumes exactly three draws. Choose seeds by the
    # independently computed inverse so the application's final state must hit
    # each published vector, including states between ordinary job boundaries.
    inverse = pow(pow(16807, 3, 2147483647), -1, 2147483647)
    for index, expected_state in enumerate(vectors):
        spec = dict(generated(expected_state * inverse % 2147483647, 1), gap=[0, 0], service=[1, 1], slack=[1, 1])
        fix = fixture(root / f"generator-vector-{index}", generated=spec)
        summary, files = run(app, fix)
        assert summary["generator"]["state"] == expected_state and summary["generator"]["draws"] == 3
        records.append(digest(files["summary.json"]))
    specs = [generated(seed, 120) for seed in seeds]
    specs += [
        generated(1, 0),
        dict(generated(1, 10), gap=[0, 0], service=[1, 1], slack=[0, 0]),
        dict(generated(rejection_seed, 512), gap=[0, 1000000], service=[1, 1000000], slack=[0, 1000000]),
    ]
    for index, spec in enumerate(specs):
        first = fixture(root / f"generated-{index}", workers=3, capacity=7, generated=spec)
        summary, files = run(app, first)
        again = fixture(root / f"repeated-{index}", workers=3, capacity=7, generated=spec)
        repeated, other = run(app, again)
        assert repeated == summary and other == files
        if index == len(specs) - 1:
            assert summary["generator"]["draws"] > 3 * spec["count"]
        records.append(digest(files["trace.jsonl"]))
    assert len(set(records[-9:-3])) == 6
    return {
        "explicit_workloads": len(cases),
        "seeded_workloads": len(specs),
        "identical_repeats": len(specs),
        "known_generator_states": 10,
        "rejection_sampling_exercised": True,
        "trace_sha256": digest("".join(records).encode()),
    }


def invalid(app: Application, root: Path) -> int:
    base = fixture(root / "template").config
    configurations = []
    for field, values in [
        ("version", [0, 2, True, 1.0, "1", None]),
        ("workers", [0, 33, True, 1.0, None, -1]),
        ("queue_capacity", [-1, 513, False, 2.5, None]),
        ("output", ["", "\x00", None, 1]),
    ]:
        for value in values:
            configurations.append(dict(copy.deepcopy(base), **{field: value}))
    for field in base:
        config = copy.deepcopy(base)
        del config[field]
        configurations.append(config)
    configurations.append(dict(copy.deepcopy(base), unexpected=1))
    for field, values in [
        ("id", ["", "1bad", "a" * 33, "two words", "λ", None]),
        ("arrival", [-1, 1000000001, True, "0", 0.5]),
        ("service", [0, -1, 1000001, True, 1.0]),
        ("deadline", [-1, 2000000001, False, 5.5]),
    ]:
        for value in values:
            config = copy.deepcopy(base)
            config["workload"]["jobs"][0][field] = value
            configurations.append(config)
    for value in [
        None,
        {},
        [None],
        [dict(job("x", 4, 1, 3))],
        [job("same", 0, 1, 5)] * 2,
        [job("j" + str(i), 0, 1, 5) for i in range(513)],
        [dict(job("x", 0, 1, 5), extra=1)],
    ]:
        config = copy.deepcopy(base)
        config["workload"]["jobs"] = value
        configurations.append(config)
    for value in [None, [], {}, {"mode": "unknown"}, {"mode": "explicit"}, {"mode": "explicit", "jobs": [], "seed": 1}]:
        configurations.append(dict(copy.deepcopy(base), workload=value))
    for field, values in [
        ("seed", [0, -1, 2147483647, True, 1.0]),
        ("count", [-1, 513, True, 0.5]),
        ("gap", [None, [], [1], [0, 1, 2], [2, 1], [-1, 1], [0, 1000001], [0, True]]),
        ("service", [[0, 1], [1, 1000001], [False, 1]]),
        ("slack", [[-1, 1], [0, 1000001], [0, None]]),
    ]:
        for value in values:
            config = dict(copy.deepcopy(base), workload=generated(1))
            config["workload"][field] = value
            configurations.append(config)
    for index, config in enumerate(configurations):
        fix = fixture(root / f"config-{index}")
        fix.config = config
        fix.write()
        # Keep the assertion target meaningful when the output field itself is malformed.
        if not isinstance(config.get("output"), str) or config["output"] in ["", "\x00"]:
            fix.config = dict(config, output="output")
        rejected(app, fix)
    raw_cases = [b"{", b"null", b"[]", b"{}", b"\xff", b'{"version":NaN}', b'{"version":1,"version":1}']
    for index, raw in enumerate(raw_cases):
        fix = fixture(root / f"raw-{index}")
        (fix.root / fix.filename).write_bytes(raw)
        rejected(app, fix)
    return len(configurations) + len(raw_cases)


def capacity(app: Application, root: Path) -> dict:
    rows = [job("j" + str(i).zfill(31), 1000000000, 1000000, 2000000000) for i in range(512)]
    fix = fixture(root / "maximum", rows, workers=32, capacity=512)
    path = fix.root / fix.filename
    raw = path.read_bytes()
    path.write_bytes(raw + b" " * (262144 - len(raw)))

    def limited() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=60,
        preexec_fn=limited,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    summary, files = verify(fix)
    assert json.loads(result.stdout) == summary
    assert summary["counts"]["on_time"] == 512 and summary["busy_ticks"] == 512000000
    assert summary["horizon_ticks"] == 1016000000 and summary["peak_queue"] == 480
    full = fixture(root / "full-queue", [job("j" + str(i), 0, 1, 2000) for i in range(512)], capacity=512)
    dense, _ = run(app, full)
    assert dense["peak_queue"] == 511 and dense["trace_records"] == 1535
    assert dense["queue_ticks"] == 512 * 511 // 2
    over = fixture(root / "oversized")
    path = over.root / over.filename
    raw = path.read_bytes()
    path.write_bytes(raw + b" " * (262145 - len(raw)))
    rejected(app, over, "input byte limit exceeded")
    return {
        "jobs": 512,
        "workers": 32,
        "configured_queue": 512,
        "observed_queue": 511,
        "trace_records": 1535,
        "input_bytes": 262144,
        "identifier_characters": 32,
        "memory_limit": 268435456,
        "summary_sha256": digest(files["summary.json"]),
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, SCHEDULER_PAUSE=label, SCHEDULER_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=15)
            assert line is not None, "exited before checkpoint"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, root: Path) -> dict:
    count = 0
    for label in ["staged", "published"]:
        for killed in [False, True]:
            fix = fixture(root / f"{label}-{killed}")
            if killed:
                process = paused(app, fix, label)
                process.kill()
                process.communicate(timeout=5)
            else:
                result = app.run(fix.root, dict(fix.settings, SCHEDULER_FAULT=label))
                assert result.returncode == 2
                assert not list(fix.root.glob(".scheduler-*"))
            if label == "staged":
                assert not fix.output.exists()
                orphan = next(fix.root.glob(".scheduler-*")) if killed else None
                original = {p.name: p.read_bytes() for p in orphan.iterdir()} if orphan else {}
                assert app.run(fix.root, fix.settings).returncode == 0
                verify(fix)
                if orphan:
                    assert original == {p.name: p.read_bytes() for p in orphan.iterdir()}
            else:
                _, files = verify(fix)
                assert app.run(fix.root, fix.settings).returncode == 2
                assert files == {p.name: p.read_bytes() for p in fix.output.iterdir()}
            count += 1
    fix = fixture(root / "live-change")
    process = paused(app, fix, "staged")
    path = fix.root / fix.filename
    path.write_bytes(path.read_bytes() + b" ")
    (fix.root / "release").write_text("resume")
    process.communicate(timeout=10)
    assert process.returncode == 2 and not fix.output.exists() and not list(fix.root.glob(".scheduler-*"))
    count += 1
    for kind in ["symlink", "hardlink", "directory", "fifo"]:
        fix = fixture(root / ("input-" + kind))
        path, target = fix.root / fix.filename, fix.root / "original"
        path.rename(target)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "directory":
            path.mkdir()
        else:
            os.mkfifo(path)
        rejected(app, fix)
        assert target.read_bytes() == canonical(fix.config).encode()
        count += 1
    for kind in ["directory", "file", "symlink", "input", "parent"]:
        fix = fixture(root / ("existing-" + kind))
        if kind == "directory":
            fix.output.mkdir()
            (fix.output / "preserved").write_text("keep")
        elif kind == "file":
            fix.output.write_text("keep")
        elif kind == "symlink":
            fix.output.symlink_to(fix.root / "missing")
        else:
            fix.config["output"] = fix.filename if kind == "input" else "."
            fix.write()
        result = app.run(fix.root, fix.settings)
        assert result.returncode == 2 and "output already exists" in result.stderr
        if kind == "directory":
            assert (fix.output / "preserved").read_text() == "keep"
        elif kind == "file":
            assert fix.output.read_text() == "keep"
        elif kind == "symlink":
            assert fix.output.is_symlink() and not fix.output.exists()
        assert (fix.root / fix.filename).read_bytes() == canonical(fix.config).encode()
        count += 1
    if os.getuid() != 0:
        fix = fixture(root / "permissions")
        fix.root.chmod(0o500)
        try:
            rejected(app, fix)
        finally:
            fix.root.chmod(0o700)
        count += 1
    fix = fixture(root / "concurrent")
    processes = [
        subprocess.Popen(
            app.command,
            cwd=fix.root,
            env=app.environment(fix.settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    results = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            results.append(process.returncode)
            assert process.returncode in [0, 2], (stdout, stderr)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    assert results.count(0) == 1
    verify(fix)
    assert not list(fix.root.glob(".scheduler-*"))
    return {"failure_and_alias_checks": count, "concurrent_writers": 8, "successful_publications": 1}


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid_documents": invalid(app, directory / "invalid"),
        "capacity": capacity(app, directory / "capacity"),
        "publication": publication(app, directory / "publication"),
        "independent_scanning_oracle": True,
        "independent_trace_integrals": True,
    }
