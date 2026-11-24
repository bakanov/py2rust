"""A chronological reference list and math.fsum verify the circular recorder independently."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

COUNTERS = ["steps", "ingested", "advances", "summaries", "exports", "inspections", "expired", "overwritten"]
MAX_TIME = 253402300799999


def command(operation: str, **fields: object) -> dict:
    return {"op": operation, **fields}


def ingest(time: int, value: float) -> dict:
    return command("INGEST", time_ms=time, value=value)


def interval(operation: str, start: int, end: int) -> dict:
    return command(operation, start_ms=start, end_ms=end)


def sample() -> list:
    return [
        ingest(0, 1e9),
        ingest(0, 1e-9),
        ingest(1, -1e9),
        interval("SUMMARY", 0, 10),
        ingest(2, 2.5),
        interval("EXPORT", 0, 10),
        command("ADVANCE", time_ms=11),
        command("INSPECT"),
    ]


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int = 3, window: int = 10) -> dict:
    return {
        "version": 1,
        "capacity": capacity,
        "window_ms": window,
        "clock_ms": 0,
        "samples": [],
        "stats": dict.fromkeys(COUNTERS, 0),
    }


def summarize(rows: list[dict]) -> dict:
    values = [row["value"] for row in rows]
    total = math.fsum(values)
    return {
        "count": len(rows),
        "sum": total,
        "mean": total / len(rows) if rows else None,
        "minimum": min(values) if rows else None,
        "maximum": max(values) if rows else None,
        "first_ms": rows[0]["time_ms"] if rows else None,
        "last_ms": rows[-1]["time_ms"] if rows else None,
    }


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["capacity"], fix.config["window_ms"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    rows = copy.deepcopy(state["samples"])
    stats = copy.deepcopy(state["stats"])
    clock = state["clock_ms"]
    before = stats["steps"]
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())
    events = []

    def view() -> dict:
        return {
            "capacity": state["capacity"],
            "window_ms": state["window_ms"],
            "clock_ms": clock,
            "summary": summarize(rows),
            "stats": copy.deepcopy(stats),
        }

    for instruction in trace:
        operation = instruction["op"]
        stats["steps"] += 1
        stats[
            {
                "INGEST": "ingested",
                "ADVANCE": "advances",
                "SUMMARY": "summaries",
                "EXPORT": "exports",
                "INSPECT": "inspections",
            }[operation]
        ] += 1
        event = {"step": stats["steps"], "op": operation}
        if operation in ["INGEST", "ADVANCE"]:
            clock = instruction["time_ms"]
            retained = [row for row in rows if row["time_ms"] >= clock - state["window_ms"]]
            event["expired"] = len(rows) - len(retained)
            stats["expired"] += event["expired"]
            rows = retained
            event["clock_ms"] = clock
        if operation == "INGEST":
            value = float(instruction["value"])
            row = {"sequence": stats["ingested"], "time_ms": clock, "value": 0.0 if value == 0.0 else value}
            event["overwritten"] = copy.deepcopy(rows[0]) if len(rows) == state["capacity"] else None
            if event["overwritten"] is not None:
                stats["overwritten"] += 1
            rows = (rows + [row])[-state["capacity"] :]
            event["sample"] = row
        elif operation in ["SUMMARY", "EXPORT"]:
            start, end = instruction["start_ms"], instruction["end_ms"]
            selected = [row for row in rows if start <= row["time_ms"] <= end]
            event.update(start_ms=start, end_ms=end)
            event["summary" if operation == "SUMMARY" else "samples"] = (
                summarize(selected) if operation == "SUMMARY" else selected
            )
        elif operation == "INSPECT":
            event["recorder"] = view()
        events.append(copy.deepcopy(event))
    state.update(samples=rows, stats=stats, clock_ms=clock)
    report = {"before_steps": before, "after_steps": stats["steps"], "commands": len(trace), "recorder": view()}
    return envelope(state), events, report


def compare(actual: object, expected: object) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict) and actual.keys() == expected.keys(), (actual, expected)
        for key, value in expected.items():
            compare(actual[key], value)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), (actual, expected)
        for left, right in zip(actual, expected):
            compare(left, right)
    elif type(expected) is float:
        assert type(actual) in (int, float) and math.isfinite(actual)
        # A compensated double sum need not round identically to fsum's exact
        # expansion. Compare within four binary64 ULPs, including near zero.
        assert abs(actual - expected) <= 4 * math.ulp(expected), (actual, expected)
    else:
        assert actual == expected, (actual, expected)
    return


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "ring-job.json"

    @property
    def output(self) -> Path:
        return self.work / "ring-run"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "RING_CONFIG": str(self.path),
            "RING_MODE": mode,
            "RING_FAIL": "",
            "RING_PAUSE": "",
            "RING_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, commands: list, prior: dict | None = None, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {"trace": "trace.json", "state": "", "capacity": 3, "window_ms": 10, "output": "ring-run", **changes}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> tuple[dict, list, dict]:
    assert sorted(path.name for path in fix.output.iterdir()) == [
        "events.jsonl",
        "report.json",
        "state.json",
        "window.jsonl",
    ]
    state = json.loads((fix.output / "state.json").read_bytes())
    events = [json.loads(line) for line in (fix.output / "events.jsonl").read_bytes().splitlines()]
    report = json.loads((fix.output / "report.json").read_bytes())
    assert state == expected[0] and (fix.output / "state.json").read_bytes() == (canonical(expected[0]) + "\n").encode()
    compare(events, expected[1])
    compare(report, expected[2])
    assert (fix.output / "events.jsonl").read_bytes() == "".join(canonical(row) + "\n" for row in events).encode()
    assert (fix.output / "window.jsonl").read_bytes() == "".join(
        canonical(row) + "\n" for row in state["state"]["samples"]
    ).encode()
    return state, events, report


def success(app: Application, fix: Fixture, mode: str = "write") -> tuple[dict, list, dict]:
    expected = oracle(fix)
    inputs = [fix.path, fix.work / fix.config["trace"]]
    if fix.config["state"]:
        inputs.append(fix.work / fix.config["state"])
    before = [path.read_bytes() for path in inputs]
    result = app.run(fix.work, fix.settings(mode), timeout=120)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    compare(json.loads(result.stdout), expected[2])
    assert [path.read_bytes() for path in inputs] == before
    observed = expected
    if mode == "write":
        observed = outputs(fix, expected)
        assert (fix.output / "report.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".ring-recorder-*"))
    return observed


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=120)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".ring-recorder-*"))
    return


def traces(app: Application, directory: Path) -> tuple[int, str]:
    rng = random.Random(58058)
    cases = [([], 3, 10), (sample(), 3, 10), ([ingest(0, -0.0), ingest(0, 0), command("ADVANCE", time_ms=1)], 2, 0)]
    boundary = [
        ingest(0, 1),
        ingest(1, 2),
        command("ADVANCE", time_ms=10),
        command("INSPECT"),
        command("ADVANCE", time_ms=11),
        command("INSPECT"),
        command("ADVANCE", time_ms=12),
        command("INSPECT"),
    ]
    cases.append((boundary, 2, 10))
    extremes = [ingest(MAX_TIME - 1, -1e9), ingest(MAX_TIME, 1e9), interval("EXPORT", MAX_TIME, MAX_TIME)]
    cases.append((extremes, 1, 31536000000))
    for trial in range(28):
        now = 0
        trace = []
        for _ in range(200):
            op = rng.choice(["INGEST"] * 5 + ["ADVANCE", "SUMMARY", "EXPORT", "INSPECT"])
            if op in ["INGEST", "ADVANCE"]:
                now += rng.choice([0, 0, 1, 2, 10])
                trace.append(
                    ingest(now, rng.choice([1e9, -1e9, 1e-9, -1e-9, 0.0, -0.0, 0.1, rng.uniform(-50, 50)]))
                    if op == "INGEST"
                    else command(op, time_ms=now)
                )
            elif op in ["SUMMARY", "EXPORT"]:
                begin = rng.randrange(now + 1)
                trace.append(interval(op, begin, rng.randrange(begin, now + 2)))
            else:
                trace.append(command(op))
        trace += [command("INSPECT"), interval("EXPORT", 0, now)]
        cases.append((trace, [1, 3, 8, 32][trial % 4], [0, 10, 100, 31536000000][trial % 4]))
    # Many laps with repeated timestamps and a cancellation-sensitive summary.
    laps = [ingest(50, [1e9, 1e-9, -1e9][i % 3]) for i in range(120)]
    laps += [interval("SUMMARY", 50, 50), interval("EXPORT", 50, 50)]
    cases.append((laps, 3, 0))
    observations = []
    for number, (trace, capacity, window) in enumerate(cases):
        fix = fixture(directory, f"trace-{number}", trace, capacity=capacity, window_ms=window)
        observed = success(app, fix)
        observations.append(observed)
        if number < 14:
            split = len(trace) // 2
            first = fixture(directory, f"split-{number}-a", trace[:split], capacity=capacity, window_ms=window)
            success(app, first)
            second = fixture(
                directory,
                f"split-{number}-b",
                trace[split:],
                state=str(first.output / "state.json"),
                capacity=capacity,
                window_ms=window,
            )
            resumed = success(app, second)
            assert resumed[0] == observed[0]
            for name in ["state.json", "window.jsonl"]:
                assert (second.output / name).read_bytes() == (fix.output / name).read_bytes()
            assert (first.output / "events.jsonl").read_bytes() + (second.output / "events.jsonl").read_bytes() == (
                fix.output / "events.jsonl"
            ).read_bytes()
    preview = fixture(directory, "preview", sample())
    success(app, preview, "preview")
    success(app, preview)
    return len(cases), hashlib.sha256(canonical(observations).encode()).hexdigest()


def invalid_inputs(app: Application, directory: Path) -> int:
    bad = [None, [], {}, {"op": "unknown"}, {"op": 1}, {"op": "ingest"}]
    commands = [
        ingest(1, 1),
        command("ADVANCE", time_ms=1),
        interval("SUMMARY", 0, 1),
        interval("EXPORT", 0, 1),
        command("INSPECT"),
    ]
    for valid in commands:
        bad.append({**valid, "extra": True})
        bad += [{key: value for key, value in valid.items() if key != field} for field in valid]
    for value in [None, True, "1", {}, [], 1000000000.1, -1000000000.1]:
        bad.append(ingest(1, value))
    for value in [-1, MAX_TIME + 1, True, 1.0, None, "1"]:
        bad += [
            ingest(value, 1),
            command("ADVANCE", time_ms=value),
            interval("SUMMARY", value, 1),
            interval("EXPORT", 0, value),
        ]
    bad += [interval("SUMMARY", 2, 1), interval("EXPORT", 2, 1), ingest(0, 1), command("ADVANCE", time_ms=0)]
    count = 0
    for item in bad:
        failure(app, fixture(directory, f"command-{count}", [ingest(1, 1), item]), "command 2:")
        count += 1
    for field, values in {
        "capacity": [0, 4097, -1, True, 1.0, "1"],
        "window_ms": [-1, 31536000001, True, 1.0, None],
        "trace": [None, "", "\x00"],
        "state": [None, 1],
        "output": [None, "", "\x00"],
    }.items():
        for value in values:
            failure(app, fixture(directory, f"config-{count}", [], **{field: value}))
            count += 1
    base = fixture(directory, "base", []).config
    for field in base:
        fix = fixture(directory, f"missing-{field}", [])
        del fix.config[field]
        fix.save()
        failure(app, fix, "unexpected object fields")
        count += 1
    for value in [b"[]", b"null", b"{", b"\xff", b" " * 65537]:
        fix = fixture(directory, f"configuration-root-{count}", [])
        fix.path.write_bytes(value)
        failure(app, fix)
        count += 1
    for value in [
        b"{}",
        b"null",
        b"[",
        b"\xff",
        b'[{"op":"INGEST","time_ms":0,"value":NaN}]',
        b'[{"op":"INGEST","time_ms":0,"value":1e999}]',
    ]:
        fix = fixture(directory, f"trace-root-{count}", [])
        (fix.work / "trace.json").write_bytes(value)
        failure(app, fix)
        count += 1
    failure(app, fixture(directory, "mode", []), "invalid recorder mode", RING_MODE="other")
    return count + 1


def invalid_states(app: Application, directory: Path) -> int:
    base = fixture(directory, "base", sample())
    original = oracle(base)[0]["state"]
    bad = []
    for field in original:
        state = copy.deepcopy(original)
        del state[field]
        bad.append(state)
    for name, value in [
        ("version", 2),
        ("version", True),
        ("capacity", 4),
        ("window_ms", 11),
        ("clock_ms", -1),
        ("clock_ms", MAX_TIME + 1),
        ("clock_ms", 0.0),
        ("clock_ms", 1),
        ("samples", []),
        ("samples", {}),
        ("stats", None),
    ]:
        bad.append({**copy.deepcopy(original), name: value})
    for name in COUNTERS:
        for value in [-1, 1000000001, True, 1.0]:
            state = copy.deepcopy(original)
            state["stats"][name] = value
            bad.append(state)
        state = copy.deepcopy(original)
        del state["stats"][name]
        bad.append(state)
    for name, value in [
        ("sequence", 4),
        ("sequence", 1),
        ("sequence", 3.0),
        ("time_ms", 0),
        ("time_ms", 12),
        ("time_ms", True),
        ("value", None),
        ("value", True),
        ("value", "1"),
        ("value", 1000000000.1),
    ]:
        state = copy.deepcopy(original)
        state["samples"][0][name] = value
        bad.append(state)
    for name in original["samples"][0]:
        state = copy.deepcopy(original)
        del state["samples"][0][name]
        bad.append(state)
    state = copy.deepcopy(original)
    state["samples"][0]["time_ms"] = 3
    bad.append(state)  # timestamps become descending
    state = copy.deepcopy(original)
    state["stats"]["steps"] += 1
    bad.append(state)
    for index, state in enumerate(bad):
        failure(app, fixture(directory, f"state-{index}", [], prior=envelope(state)))
    checks = len(bad)
    for name, state, message in [
        (
            "overwrite",
            {**fresh(), "stats": {**fresh()["stats"], "steps": 1, "ingested": 1, "overwritten": 1}},
            "impossible overwrite",
        ),
        (
            "expiration",
            {
                **fresh(),
                "clock_ms": 5,
                "stats": {**fresh()["stats"], "steps": 2, "ingested": 1, "advances": 1, "expired": 1},
            },
            "impossible expiration",
        ),
        ("unused-clock", {**fresh(), "clock_ms": 1}, "clock moved without"),
    ]:
        failure(app, fixture(directory, name, [], prior=envelope(state)), message)
        checks += 1
    state = copy.deepcopy(original)
    state["stats"]["advances"] = 0
    state["stats"]["steps"] -= 1
    failure(app, fixture(directory, "ingestion-clock", [], prior=envelope(state)), "last ingestion must define")
    checks += 1
    for env in [
        None,
        [],
        {},
        {"state": original},
        {"state": original, "sha256": "0" * 64},
        {**envelope(original), "extra": True},
        {"state": original, "sha256": 1},
    ]:
        fix = fixture(directory, f"envelope-{checks}", [], prior={})
        (fix.work / "prior.json").write_text(canonical(env))
        failure(app, fix)
        checks += 1
    return checks


def paused(app: Application, fix: Fixture, point: str = "ready") -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(RING_PAUSE=point, RING_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED " + point + "\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    points = ["validated", "stage", "state.json", "events.jsonl", "window.jsonl", "report.json", "ready", "published"]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        result = app.run(fix.work, fix.settings(RING_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout, result
        assert not list(fix.work.glob(".ring-recorder-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["trace", "config", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), prior=envelope(fresh()))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = {"trace": fix.work / "trace.json", "config": fix.path, "state": fix.work / "prior.json"}[name]
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output, (output, error)
            assert not list(fix.work.glob(".ring-recorder-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".ring-recorder-*"))
    assert len(abandoned) == 1
    before = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0
    outputs(fix, oracle(fix))
    assert before == {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    for name in ["file", "directory", "symlink", "dangling", "same-trace", "same-config"]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"keep")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("trace.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = "trace.json" if name == "same-trace" else "ring-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace", "config", "state"]:
        fix = fixture(directory, "symlink-" + name, sample(), prior=envelope(fresh()))
        path = {"trace": fix.work / "trace.json", "config": fix.path, "state": fix.work / "prior.json"}[name]
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert (fix.work / "original").read_bytes() == original and path.is_symlink()
    fix = fixture(directory, "no-write", sample())
    parent = fix.work / "read-only"
    parent.mkdir()
    fix.config["output"] = "read-only/result"
    fix.save()
    parent.chmod(0o500)
    try:
        failure(app, fix)
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)
    return 10


def limits(app: Application, directory: Path) -> dict:
    # Two complete laps of the maximum capacity exercise actual wraparound.
    trace = [ingest(0, (index % 17) / 8) for index in range(8192)]
    fix = fixture(directory, "capacity-and-trace-exact", trace, capacity=4096, window_ms=0)
    expected = success(app, fix)
    assert len(expected[0]["state"]["samples"]) == 4096
    assert expected[0]["state"]["stats"]["overwritten"] == 4096
    resumed = fixture(
        directory,
        "capacity-resumed",
        [ingest(0, -1.0), interval("SUMMARY", 0, 0), command("ADVANCE", time_ms=1), command("INSPECT")],
        capacity=4096,
        window_ms=0,
        state=str(fix.output / "state.json"),
    )
    result = success(app, resumed)
    assert result[2]["recorder"]["summary"]["count"] == 0
    assert result[2]["recorder"]["stats"]["expired"] == 4096
    failure(app, fixture(directory, "trace-above", [command("INSPECT")] * 8193), "trace exceeds 8192")
    for name in ["configuration", "trace", "state"]:
        maximum = 65536 if name == "configuration" else 1048576
        fix = fixture(directory, "bytes-exact-" + name, [], prior=envelope(fresh()))
        path = {"configuration": fix.path, "trace": fix.work / "trace.json", "state": fix.work / "prior.json"}[name]
        original = path.read_bytes()
        path.write_bytes(original + b" " * (maximum - len(original)))
        success(app, fix)
        next_fix = fixture(directory, "bytes-above-" + name, [], prior=envelope(fresh()))
        path = {
            "configuration": next_fix.path,
            "trace": next_fix.work / "trace.json",
            "state": next_fix.work / "prior.json",
        }[name]
        original = path.read_bytes()
        path.write_bytes(original + b" " * (maximum + 1 - len(original)))
        failure(app, next_fix, "input byte limit exceeded")
    saturated = fresh()
    saturated["stats"].update(steps=1000000000, inspections=1000000000)
    success(app, fixture(directory, "lifetime-exact", [], prior=envelope(saturated)))
    failure(
        app,
        fixture(directory, "lifetime-above", [command("INSPECT")], prior=envelope(saturated)),
        "lifetime command limit",
    )
    many_exports = [interval("EXPORT", 0, 0)] * 100
    failure(
        app,
        fixture(
            directory,
            "events-above",
            many_exports,
            capacity=4096,
            window_ms=0,
            state=str(fix_path := directory / "capacity-and-trace-exact/ring-run/state.json"),
        ),
        "events exceed 16 MiB",
    )
    assert fix_path.exists()
    return {
        "capacity": 4096,
        "trace_commands": 8192,
        "whole_laps": 2,
        "input_bytes": 1048576,
        "configuration_bytes": 65536,
        "event_bytes": 16777216,
        "lifetime_commands": 1000000000,
    }


def check(app: Application, directory: Path) -> dict:
    count, digest = traces(app, directory / "traces")
    print(app.engine + " ring recorder: reference traces and split restarts passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    states = invalid_states(app, directory / "states")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    bounds = limits(app, directory / "limits")
    print(app.engine + " ring recorder: validation, publication and boundaries passed", flush=True)
    return {
        "traces": count,
        "generated_traces": 28,
        "restart_splits": 14,
        "results_sha256": digest,
        "invalid_inputs": invalid,
        "invalid_states": states,
        "publication_cases": faults,
        "path_cases": path_cases,
        "limits": bounds,
    }
