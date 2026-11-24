"""Independent brute-force overlap oracle for a persisted balanced interval index."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

MINIMUM = -(2**63)
MAXIMUM = 2**63 - 1


def event(identifier: str, start: int, end: int, text: str = "", data: object = None) -> dict:
    return {"id": identifier, "start_ms": start, "end_ms": end, "text": text, "data": data}


def query(start: int, end: int, text: str = "", offset: int = 0, limit: int = 1024) -> dict:
    return {"op": "QUERY", "start_ms": start, "end_ms": end, "text": text, "offset": offset, "limit": limit}


def point(time: int, text: str = "", offset: int = 0, limit: int = 1024) -> dict:
    return {"op": "POINT", "time_ms": time, "text": text, "offset": offset, "limit": limit}


def sample() -> list:
    return [
        event("outer", -5, 30, "whole session", {"nested": [True, None, 1.25]}),
        event("a", 0, 10, "Straße request"),
        event("b", 10, 20, "世界 response"),
        event("empty", 10, 10),
        event("nested", 2, 3, "inner"),
        event("old", -20, -10),
    ]


def order(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row["start_ms"], row["end_ms"], row["id"]))


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int = 16) -> dict:
    return {"version": 1, "capacity": capacity, "steps": 0, "events": []}


def oracle(fix: Fixture) -> tuple[dict, list, dict, list[int]]:
    state = fresh(fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    values = {row["id"]: copy.deepcopy(row) for row in state["events"]}
    imported = {"read": 0, "added": 0, "replaced": 0}
    if fix.config["records"]:
        for row in json.loads((fix.work / fix.config["records"]).read_bytes()):
            imported["read"] += 1
            imported["replaced" if row["id"] in values else "added"] += 1
            values[row["id"]] = copy.deepcopy(row)
    before = state["steps"]
    steps = before
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())
    events = []
    bounds = []

    def view() -> dict:
        rows = list(values.values())
        return {
            "capacity": state["capacity"],
            "steps": steps,
            "records": len(rows),
            "height": len(rows).bit_length(),
            "minimum_start_ms": min(row["start_ms"] for row in rows) if rows else None,
            "maximum_end_ms": max(row["end_ms"] for row in rows) if rows else None,
        }

    for command in trace:
        steps += 1
        operation = command["op"]
        result = {"step": steps, "op": operation}
        if operation == "PUT":
            row = command["event"]
            found = row["id"] in values
            accepted = found or len(values) < state["capacity"]
            result.update(accepted=accepted, previous=copy.deepcopy(values.get(row["id"])))
            if accepted:
                values[row["id"]] = copy.deepcopy(row)
            else:
                result["reason"] = "capacity"
        elif operation in ["DELETE", "GET"]:
            name = command["id"]
            result.update(found=name in values, event=copy.deepcopy(values.get(name)))
            if operation == "DELETE":
                values.pop(name, None)
        elif operation in ["QUERY", "POINT"]:
            rows = []
            for row in values.values():
                if operation == "POINT":
                    overlaps = row["start_ms"] <= command["time_ms"] < row["end_ms"]
                else:
                    overlaps = (
                        command["start_ms"] < command["end_ms"]
                        and row["start_ms"] < row["end_ms"]
                        and row["start_ms"] < command["end_ms"]
                        and command["start_ms"] < row["end_ms"]
                    )
                if overlaps and command["text"].casefold() in row["text"].casefold():
                    rows.append(copy.deepcopy(row))
            rows = order(rows)
            start, stop = command["offset"], command["offset"] + command["limit"]
            result["result"] = {"hits": rows[start:stop], "count": len(rows), "more": stop < len(rows)}
        else:
            assert operation == "INSPECT"
            result["index"] = view()
        events.append(result)
        bounds.append(len(values))
    state.update(steps=steps, events=sorted(values.values(), key=lambda row: row["id"]))
    report = {
        "before_steps": before,
        "after_steps": steps,
        "commands": len(trace),
        "imported": imported,
        "index": view(),
    }
    return envelope(state), events, report, bounds


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "interval-job.json"

    @property
    def output(self) -> Path:
        return self.work / "interval-run"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "INTERVAL_CONFIG": str(self.path),
            "INTERVAL_MODE": mode,
            "INTERVAL_FAIL": "",
            "INTERVAL_PAUSE": "",
            "INTERVAL_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, rows: list, commands: list, prior: dict | None = None, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "records.json").write_text(json.dumps(rows, ensure_ascii=False))
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {
        "records": "records.json",
        "trace": "trace.json",
        "state": "",
        "capacity": 16,
        "output": "interval-run",
        **changes,
    }
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def outputs(fix: Fixture, expected: tuple[dict, list, dict, list[int]]) -> tuple[dict, list, dict]:
    assert sorted(path.name for path in fix.output.iterdir()) == [
        "events.jsonl",
        "records.jsonl",
        "report.json",
        "state.json",
    ]
    state = json.loads((fix.output / "state.json").read_bytes())
    actual = [json.loads(line) for line in (fix.output / "events.jsonl").read_bytes().splitlines()]
    report = json.loads((fix.output / "report.json").read_bytes())
    assert state == expected[0] and (fix.output / "state.json").read_bytes() == (canonical(expected[0]) + "\n").encode()
    assert len(actual) == len(expected[1])
    for number, wanted in enumerate(expected[1]):
        observed = copy.deepcopy(actual[number])
        if wanted["op"] in ["QUERY", "POINT"]:
            visits = observed["result"].pop("visited_nodes")
            assert type(visits) is int and wanted["result"]["count"] <= visits <= expected[3][number]
        assert observed == wanted, (number, observed, wanted)
    assert report == expected[2], (report, expected[2])
    assert (fix.output / "events.jsonl").read_bytes() == "".join(canonical(row) + "\n" for row in actual).encode()
    assert (fix.output / "records.jsonl").read_bytes() == "".join(
        canonical(row) + "\n" for row in order(state["state"]["events"])
    ).encode()
    return state, actual, report


def success(app: Application, fix: Fixture, mode: str = "write") -> tuple[dict, list, dict]:
    expected = oracle(fix)
    paths = [fix.path, fix.work / fix.config["trace"]]
    paths += [fix.work / fix.config[key] for key in ["records", "state"] if fix.config[key]]
    before = [path.read_bytes() for path in paths]
    result = app.run(fix.work, fix.settings(mode), timeout=120)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    assert json.loads(result.stdout) == expected[2]
    assert before == [path.read_bytes() for path in paths]
    observed = expected[:3]
    if mode == "write":
        observed = outputs(fix, expected)
        assert (fix.output / "report.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".interval-browser-*"))
    return observed


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=120)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".interval-browser-*"))
    return


def traces(app: Application, directory: Path) -> tuple[int, str]:
    rng = random.Random(59059)
    basic = [
        query(9, 10),
        point(10),
        query(10, 10),
        query(2, 3, "STRASSE"),
        {"op": "PUT", "event": event("a", 12, 14, "updated")},
        point(10),
        {"op": "DELETE", "id": "outer"},
        {"op": "GET", "id": "missing"},
        {"op": "INSPECT"},
    ]
    cases = [([], [query(0, 1), point(0), {"op": "INSPECT"}], 16), (sample(), basic, 16)]
    extremes = [
        event("whole", MINIMUM, MAXIMUM),
        event("min-empty", MINIMUM, MINIMUM),
        event("max-empty", MAXIMUM, MAXIMUM),
    ]
    cases.append((extremes, [point(MINIMUM), point(MAXIMUM), query(MINIMUM, MAXIMUM), query(MAXIMUM, MAXIMUM)], 16))
    cases.append(
        (
            [event("one", 0, 1)],
            [
                {"op": "PUT", "event": event("two", 2, 3)},
                {"op": "PUT", "event": event("one", 3, 4)},
                {"op": "DELETE", "id": "one"},
                {"op": "PUT", "event": event("two", 2, 3)},
                query(0, 10),
            ],
            1,
        )
    )
    labels = ["", "Straße", "STRASSE", "世界", "İ", "i\u0307", "Σςσ", "CAFÉ", "cafe\u0301", "😀", "\x00"]
    for trial in range(28):
        rows = []
        for number in range(12):
            start = rng.randrange(-40, 41)
            rows.append(
                event(
                    f"id-{number}",
                    start,
                    start + rng.randrange(0, 60),
                    rng.choice(labels),
                    {"i": number, "values": [None, True, 1.25]},
                )
            )
        commands = []
        for _ in range(100):
            operation = rng.choice(["QUERY"] * 4 + ["POINT"] * 2 + ["PUT", "DELETE", "GET", "INSPECT"])
            if operation == "PUT":
                start = rng.randrange(-60, 61)
                commands.append(
                    {
                        "op": operation,
                        "event": event(
                            f"id-{rng.randrange(24)}", start, start + rng.randrange(0, 90), rng.choice(labels)
                        ),
                    }
                )
            elif operation in ["DELETE", "GET"]:
                commands.append({"op": operation, "id": f"id-{rng.randrange(24)}"})
            elif operation in ["QUERY", "POINT"]:
                start = rng.randrange(-100, 101)
                needle = rng.choice(labels)
                offset, limit = rng.randrange(0, 6), rng.randrange(1, 8)
                commands.append(
                    query(start, start + rng.randrange(0, 80), needle, offset, limit)
                    if operation == "QUERY"
                    else point(start, needle, offset, limit)
                )
            else:
                commands.append({"op": operation})
        commands += [query(MINIMUM, MAXIMUM), {"op": "INSPECT"}]
        cases.append((rows, commands, 16))
    observations = []
    for number, (rows, commands, capacity) in enumerate(cases):
        fix = fixture(directory, f"trace-{number}", rows, commands, capacity=capacity)
        observed = success(app, fix)
        observations.append(observed)
        if number < 14:
            split = len(commands) // 2
            first = fixture(directory, f"split-{number}-a", rows, commands[:split], capacity=capacity)
            success(app, first)
            second = fixture(
                directory,
                f"split-{number}-b",
                [],
                commands[split:],
                state=str(first.output / "state.json"),
                capacity=capacity,
            )
            resumed = success(app, second)
            assert resumed[0] == observed[0]
            for name in ["state.json", "records.jsonl"]:
                assert (second.output / name).read_bytes() == (fix.output / name).read_bytes()
            assert (first.output / "events.jsonl").read_bytes() + (second.output / "events.jsonl").read_bytes() == (
                fix.output / "events.jsonl"
            ).read_bytes()
    imported = fixture(directory, "imported", sample(), [])
    success(app, imported)
    combined = fixture(
        directory,
        "import-merge",
        [event("a", 40, 50, "replacement"), event("added", -1, 0)],
        [query(-100, 100), {"op": "INSPECT"}],
        state=str(imported.output / "state.json"),
    )
    outcome = success(app, combined)
    assert outcome[2]["imported"] == {"read": 2, "added": 1, "replaced": 1}
    preview = fixture(directory, "preview", sample(), basic)
    success(app, preview, "preview")
    success(app, preview)
    omitted = fixture(directory, "optional-records", [], [], records="")
    success(app, omitted)
    return len(cases), hashlib.sha256(canonical(observations).encode()).hexdigest()


def invalid_inputs(app: Application, directory: Path) -> int:
    bad = [
        None,
        [],
        {},
        event("", 0, 1),
        event("x", 2, 1),
        event("x", True, 1),
        event("x", 0, 1.0),
        event("x" * 65, 0, 1),
        event("😀" * 65, 0, 1),
        event("x", 0, 1, "x" * 257),
        event("x", 0, 1, data="x" * 4095),
    ]
    valid = event("x", 0, 1)
    bad += [{key: value for key, value in valid.items() if key != field} for field in valid]
    bad.append({**valid, "extra": True})
    nested = None
    for _ in range(9):
        nested = [nested]
    bad.append(event("deep", 0, 1, data=nested))
    count = 0
    for row in bad:
        failure(app, fixture(directory, f"import-{count}", [row], []))
        failure(app, fixture(directory, f"put-{count}", [], [{"op": "PUT", "event": row}]), "command 1:")
        count += 2
    failure(app, fixture(directory, "duplicates", [valid, valid], []), "duplicate imported ID")
    failure(app, fixture(directory, "import-capacity", sample(), [], capacity=1), "import exceeds capacity")
    count += 2
    bad_commands = [None, [], {}, {"op": "unknown"}, {"op": 1}, {"op": "query"}]
    commands = [
        {"op": "PUT", "event": valid},
        {"op": "GET", "id": "x"},
        {"op": "DELETE", "id": "x"},
        query(0, 1),
        point(0),
        {"op": "INSPECT"},
    ]
    for command in commands:
        bad_commands.append({**command, "extra": True})
        bad_commands += [{key: value for key, value in command.items() if key != field} for field in command]
    for value in ["", None, 1, "x" * 65]:
        bad_commands += [{"op": "GET", "id": value}, {"op": "DELETE", "id": value}]
    for field, values in {
        "offset": [-1, 1025, True, 1.0],
        "limit": [0, 1025, True, None],
        "text": [None, False, "x" * 257],
        "start_ms": [None, True, 1.0],
        "end_ms": [None, True, 1.0],
    }.items():
        bad_commands += [{**query(0, 1), field: value} for value in values]
    bad_commands += [point(None), point(True), point(1.0), query(2, 1)]
    for command in bad_commands:
        failure(
            app, fixture(directory, f"command-{count}", sample(), [{"op": "GET", "id": "a"}, command]), "command 2:"
        )
        count += 1
    for field, values in {
        "capacity": [0, 1025, True, 1.0, None],
        "records": [None, 1, "\x00"],
        "trace": ["", None, "\x00"],
        "state": [None, 1, "\x00"],
        "output": ["", None, "\x00"],
    }.items():
        for value in values:
            failure(app, fixture(directory, f"config-{count}", [], [], **{field: value}))
            count += 1
    config = fixture(directory, "base", [], []).config
    for field in config:
        fix = fixture(directory, f"missing-{field}", [], [])
        del fix.config[field]
        fix.save()
        failure(app, fix, "unexpected object fields")
        count += 1
    for name in ["records.json", "trace.json", "interval-job.json"]:
        for raw in [b"null", b"{", b"\xff"]:
            fix = fixture(directory, f"root-{count}", [], [])
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    for value in [MAXIMUM + 1, MINIMUM - 1]:
        failure(app, fixture(directory, f"integer-{count}", [event("x", value, value)], []))
        count += 1
    failure(app, fixture(directory, "mode", [], []), "invalid browser mode", INTERVAL_MODE="other")
    return count + 1


def invalid_states(app: Application, directory: Path) -> int:
    original = {**fresh(), "steps": 8, "events": sample()}
    bad = []
    for field in original:
        state = copy.deepcopy(original)
        del state[field]
        bad.append(state)
    for field, value in [
        ("version", 2),
        ("version", True),
        ("capacity", 17),
        ("capacity", True),
        ("steps", -1),
        ("steps", 1000000001),
        ("steps", True),
        ("steps", 1.0),
        ("events", None),
        ("events", {}),
    ]:
        bad.append({**copy.deepcopy(original), field: value})
    for row in [
        None,
        {},
        event("", 0, 1),
        event("bad", 2, 1),
        event("bad", False, 1),
        event("bad", 0, 1, text="x" * 257),
        event("bad", 0, 1, data="x" * 4095),
        {**event("bad", 0, 1), "extra": True},
    ]:
        bad.append({**copy.deepcopy(original), "events": [row]})
    bad.append({**copy.deepcopy(original), "events": sample() + [sample()[0]]})
    bad.append({**copy.deepcopy(original), "events": [event(str(i), i, i + 1) for i in range(17)]})
    for number, state in enumerate(bad):
        failure(app, fixture(directory, f"state-{number}", [], [], prior=envelope(state)))
    count = len(bad)
    for value in [
        None,
        [],
        {},
        {"state": original},
        {"state": original, "sha256": "0" * 64},
        {**envelope(original), "extra": True},
        {"state": original, "sha256": True},
    ]:
        fix = fixture(directory, f"envelope-{count}", [], [], prior={})
        (fix.work / "prior.json").write_text(canonical(value))
        failure(app, fix)
        count += 1
    # A valid checksum cannot hide malformed nested payloads in retained events.
    deep = None
    for _ in range(9):
        deep = [deep]
    state = {**fresh(), "events": [event("deep", 0, 1, data=deep)]}
    failure(app, fixture(directory, "state-depth", [], [], prior=envelope(state)), "payload nesting")
    return count + 1


def limits(app: Application, directory: Path) -> dict:
    rows = [event(f"event-{i:04}", i * 10, i * 10 + 5, f"event {i}", {"row": i}) for i in range(1024)]
    commands = [point(i * 10 + 1) for i in [0, 1, 255, 511, 512, 700, 1023]]
    commands += [
        query(-100, -10),
        point(-1),
        query(20000, 20001),
        query(0, 0),
        query(0, 20000),
        {"op": "PUT", "event": event("overflow", 0, 1)},
        {"op": "PUT", "event": event("event-0000", 20001, 20002)},
        point(1),
        point(20001),
        {"op": "DELETE", "id": "event-0512"},
        point(5121),
        {"op": "INSPECT"},
    ]
    fix = fixture(directory, "capacity-pruning", rows, commands, capacity=1024)
    observed = success(app, fix)
    for result in observed[1][:7]:
        assert result["result"]["count"] == 1 and result["result"]["visited_nodes"] <= 11
    assert all(result["result"]["visited_nodes"] == 0 for result in observed[1][7:11])
    assert observed[1][11]["result"]["count"] == observed[1][11]["result"]["visited_nodes"] == 1024
    assert observed[1][12]["accepted"] is False and observed[1][13]["accepted"] is True
    assert observed[1][14]["result"]["count"] == 0 and observed[1][15]["result"]["count"] == 1
    assert observed[1][17]["result"]["count"] == 0
    failure(
        app,
        fixture(directory, "import-above", rows + [event("one-more", 0, 1)], [], capacity=1024),
        "import exceeds 1024",
    )
    exact = fixture(directory, "trace-exact", [], [{"op": "INSPECT"}] * 2048)
    success(app, exact)
    failure(app, fixture(directory, "trace-above", [], [{"op": "INSPECT"}] * 2049), "trace exceeds 2048")
    deep = None
    for _ in range(8):
        deep = [deep]
    allowed = [event("😀" * 64, 0, 1, "😀" * 256, "é" * 2047), event("deep", 1, 2, data=deep)]
    success(app, fixture(directory, "fields-exact", allowed, [query(0, 2)]))
    for name, maximum in [("configuration", 65536), ("records", 4194304), ("trace", 4194304), ("state", 8388608)]:
        for extra in [0, 1]:
            fix = fixture(directory, f"bytes-{name}-{extra}", [], [], prior=envelope(fresh()))
            target = {
                "configuration": fix.path,
                "records": fix.work / "records.json",
                "trace": fix.work / "trace.json",
                "state": fix.work / "prior.json",
            }[name]
            raw = target.read_bytes()
            target.write_bytes(raw + b" " * (maximum + extra - len(raw)))
            if extra:
                failure(app, fix, "input byte limit exceeded")
            else:
                success(app, fix)
    saturated = {**fresh(), "steps": 1000000000}
    success(app, fixture(directory, "lifetime-exact", [], [], prior=envelope(saturated)))
    failure(
        app,
        fixture(directory, "lifetime-above", [], [{"op": "INSPECT"}], prior=envelope(saturated)),
        "lifetime command limit",
    )
    failure(
        app, fixture(directory, "events-above", rows, [query(0, 20000)] * 200, capacity=1024), "events exceed 16 MiB"
    )
    return {
        "capacity": 1024,
        "trace_commands": 2048,
        "pruned_single_hit_max_visits": 11,
        "whole_range_visits": 1024,
        "empty_or_outside_visits": 0,
        "payload_bytes": 4096,
        "payload_depth": 8,
        "state_bytes": 8388608,
        "input_bytes": 4194304,
        "event_bytes": 16777216,
        "lifetime_commands": 1000000000,
    }


def paused(app: Application, fix: Fixture, point: str = "ready") -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(INTERVAL_PAUSE=point, INTERVAL_CONTINUE=str(fix.work / "continue"))),
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
    points = ["validated", "stage", "state.json", "events.jsonl", "records.jsonl", "report.json", "ready", "published"]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample(), [query(-100, 100)])
        result = app.run(fix.work, fix.settings(INTERVAL_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout, result
        assert not list(fix.work.glob(".interval-browser-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["records", "trace", "config", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), [query(-100, 100)], prior=envelope(fresh()))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = {
                    "records": fix.work / "records.json",
                    "trace": fix.work / "trace.json",
                    "config": fix.path,
                    "state": fix.work / "prior.json",
                }[name]
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output, (output, error)
            assert not list(fix.work.glob(".interval-browser-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample(), [query(-100, 100)])
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".interval-browser-*"))
    assert len(abandoned) == 1
    before = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0
    outputs(fix, oracle(fix))
    assert before == {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    return len(points) + 6


def paths(app: Application, directory: Path) -> int:
    for name in ["file", "directory", "symlink", "dangling", "same-trace", "same-config"]:
        fix = fixture(directory, "destination-" + name, sample(), [query(-100, 100)])
        if name == "file":
            fix.output.write_bytes(b"keep")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("trace.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = "trace.json" if name == "same-trace" else "interval-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["records", "trace", "config", "state"]:
        fix = fixture(directory, "symlink-" + name, sample(), [query(-100, 100)], prior=envelope(fresh()))
        path = {
            "records": fix.work / "records.json",
            "trace": fix.work / "trace.json",
            "config": fix.path,
            "state": fix.work / "prior.json",
        }[name]
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert (fix.work / "original").read_bytes() == original and path.is_symlink()
    fix = fixture(directory, "no-write", sample(), [query(-100, 100)])
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
    return 11


def check(app: Application, directory: Path) -> dict:
    count, digest = traces(app, directory / "traces")
    print(app.engine + " interval browser: brute-force comparisons and split restarts passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    states = invalid_states(app, directory / "states")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    bounds = limits(app, directory / "limits")
    print(app.engine + " interval browser: validation, publication and pruning boundaries passed", flush=True)
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
