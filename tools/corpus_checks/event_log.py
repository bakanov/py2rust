"""Offline per-stream reference, exact byte locations and diagnostic/publication fixtures."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import io
import json
import math
import os
import random
import re
import selectors
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .common import Application
from .csv_json import canonical

REQUIRED = ["id", "stream", "sequence", "time", "from", "to"]


def event(
    number: int,
    stream: str = "a",
    *,
    sequence: int | None = None,
    before: str | None = None,
    after: str = "active",
    **changes: object,
) -> dict:
    result = {
        "id": f"{stream}-{number}",
        "stream": stream,
        "sequence": number if sequence is None else sequence,
        "time": (dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=number)).isoformat(),
        "from": before if before is not None else ("new" if number == 1 else "active"),
        "to": after,
    }
    result.update(changes)
    return result


def encoded(rows: list[object], ending: bytes = b"\n") -> bytes:
    return b"".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode() + ending for row in rows)


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def source(self) -> Path:
        return self.work / "events.jsonl"

    @property
    def path(self) -> Path:
        return self.work / "event-job.json"

    @property
    def output(self) -> Path:
        return self.work / "diagnostics"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict[str, str]:
        return {"EVENT_CONFIG": str(self.path), "EVENT_MODE": mode, **extra}


def fixture(directory: Path, name: str, rows: list[object] | bytes, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "input": "events.jsonl",
        "output": "diagnostics",
        "states": ["new", "active", "paused", "closed"],
        "initial_state": "new",
        "transitions": [
            {"from": a, "to": b}
            for a, b in [
                ("new", "active"),
                ("active", "active"),
                ("active", "paused"),
                ("paused", "active"),
                ("active", "closed"),
            ]
        ],
        "first_sequence": 1,
        "global_time_order": True,
        "max_streams": 1000,
        "max_records": 10000,
        "max_line_bytes": 65536,
        "max_input_bytes": 8388608,
    }
    config.update(changes)
    fix = Fixture(work, config)
    fix.save()
    fix.source.write_bytes(rows if isinstance(rows, bytes) else encoded(rows))
    return fix


def timestamp(value: object) -> str:
    assert type(value) is str and value.isascii()
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", value)
    if not value.endswith("Z"):
        assert int(value[-5:-3]) <= 23 and int(value[-2:]) <= 59
    return (
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(dt.timezone.utc)
        .isoformat(timespec="microseconds")
    )


def walk(value: object, depth_limit: int, node_limit: int | None = None) -> None:
    pending = [(value, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        assert depth <= depth_limit and (node_limit is None or nodes <= node_limit)
        if isinstance(value, dict):
            for key in value:
                key.encode()
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            value.encode()
        elif type(value) is int:
            assert -(2**63) <= value < 2**63
        elif type(value) is float:
            assert math.isfinite(value)
    return  # noqa: PLR1711


def normalized(raw: bytes, states: list[str]) -> tuple[dict | None, list[str]]:
    try:
        value = json.loads(raw.decode())
        walk(value, 64)
    except (ValueError, UnicodeError, AssertionError):
        return None, ["json_or_utf8"]
    if not isinstance(value, dict):
        return None, ["object"]
    errors = ["missing:" + name for name in REQUIRED if name not in value]
    errors += ["unknown:" + name for name in sorted(value) if name not in [*REQUIRED, "data"]]
    if errors:
        return None, errors
    value = copy.deepcopy(value)
    value.setdefault("data", None)
    for name in [*REQUIRED, "data"]:
        try:
            item = value[name]
            if name in ["id", "stream"]:
                assert type(item) is str and 1 <= len(item.encode()) <= 128 and item.strip() == item
                assert re.fullmatch(r"[^\x00-\x1f\x7f]+", item)
            elif name == "sequence":
                assert type(item) is int and item >= 1
            elif name == "time":
                value[name] = timestamp(item)
            elif name in ["from", "to"]:
                assert type(item) is str and item in states
            else:
                walk(item, 16, 1000)
        except (ValueError, TypeError, OverflowError, UnicodeError, AssertionError):
            errors.append(name)
    return (None if errors else value), errors


def oracle(fix: Fixture) -> dict:
    data, config = fix.source.read_bytes(), fix.config
    records, by_stream = [], defaultdict(list)
    identifiers, positions = {}, {}
    offset, valid = 0, 0
    for number, raw in enumerate(io.BytesIO(data).readlines(), 1):
        row = {
            "line": number,
            "offset": offset,
            "length": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "event": None,
            "issues": [],
        }
        offset += len(raw)
        if len(raw) > config["max_line_bytes"]:
            row["issues"].append({"code": "oversized_record", "details": {"limit": config["max_line_bytes"]}})
        else:
            value, errors = normalized(raw, config["states"])
            row["event"] = value
            if errors:
                row["issues"].append({"code": "invalid_record", "details": {"fields": errors}})
            else:
                valid += 1
                identifier = value["id"]
                key = value["stream"], value["sequence"]
                signature = canonical(value)
                if identifier in identifiers:
                    first, old = identifiers[identifier]
                    code = "duplicate_id" if signature == old else "conflicting_id"
                    row["issues"].append({"code": code, "details": {"first_line": first}})
                else:
                    identifiers[identifier] = number, signature
                    if key in positions:
                        row["issues"].append({"code": "duplicate_sequence", "details": {"first_line": positions[key]}})
                    else:
                        positions[key] = number
                        by_stream[value["stream"]].append(row)
        records.append(row)
    summary = {}
    permitted = {(entry["from"], entry["to"]) for entry in config["transitions"]}
    advanced = []
    for name, stream in by_stream.items():
        advanced.extend(stream)
        first = config["first_sequence"]
        sequences = sorted({row["event"]["sequence"] for row in stream if row["event"]["sequence"] >= first})
        boundaries = [first - 1, *sequences]
        missing = [{"first": left + 1, "last": right - 1} for left, right in pairwise(boundaries) if right - left > 1]
        high, high_line, clock, clock_line = first - 1, 0, "", 0
        state, state_line = config["initial_state"], 0
        for row in stream:
            value, number = row["event"], row["line"]
            sequence = value["sequence"]
            if sequence < first:
                row["issues"].append({"code": "sequence_before_start", "details": {"first": first, "actual": sequence}})
            elif sequence < high:
                row["issues"].append({"code": "sequence_out_of_order", "details": {"highest": high, "line": high_line}})
            elif sequence > high + 1:
                row["issues"].append({"code": "sequence_gap", "details": {"first": high + 1, "last": sequence - 1}})
            if sequence > high:
                high, high_line = sequence, number
            if value["time"] < clock:
                row["issues"].append(
                    {"code": "stream_time_regression", "details": {"latest": clock, "line": clock_line}}
                )
            if value["time"] > clock:
                clock, clock_line = value["time"], number
            if value["from"] != state:
                row["issues"].append(
                    {
                        "code": "state_mismatch",
                        "details": {"expected": state, "actual": value["from"], "line": state_line},
                    }
                )
            if (value["from"], value["to"]) not in permitted:
                row["issues"].append(
                    {"code": "invalid_transition", "details": {"from": value["from"], "to": value["to"]}}
                )
            state, state_line = value["to"], number
        summary[name] = {
            "checked_records": len(stream),
            "first_line": stream[0]["line"],
            "last_observed_state": state,
            "state_line": state_line,
            "highest_sequence": high,
            "highest_sequence_line": high_line,
            "latest_utc": clock,
            "time_line": clock_line,
            "missing": missing,
            "missing_count": sum(row["last"] - row["first"] + 1 for row in missing),
        }
    clock, clock_line = "", 0
    for row in sorted(advanced, key=lambda row: row["line"]):
        moment = row["event"]["time"]
        if config["global_time_order"] and moment < clock:
            row["issues"].append({"code": "global_time_regression", "details": {"latest": clock, "line": clock_line}})
        if moment > clock:
            clock, clock_line = moment, row["line"]
    priority = {
        name: index
        for index, name in enumerate(
            [
                "sequence_before_start",
                "sequence_out_of_order",
                "sequence_gap",
                "stream_time_regression",
                "global_time_regression",
                "state_mismatch",
                "invalid_transition",
            ]
        )
    }
    for row in records:
        row["issues"].sort(key=lambda issue: priority.get(issue["code"], -1))
    diagnostics = [row for row in records if row["issues"]]
    return {
        "consistent": not diagnostics,
        "records": len(records),
        "schema_valid": valid,
        "checked": len(advanced),
        "invalid_records": len(records) - valid,
        "duplicate_records": valid - len(advanced),
        "input_bytes": len(data),
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "latest_utc": clock,
        "latest_time_line": clock_line,
        "issue_counts": dict(Counter(issue["code"] for row in diagnostics for issue in row["issues"])),
        "diagnostics": diagnostics,
        "streams": summary,
    }


def text_report(report: dict) -> bytes:
    lines = [
        "Event-log consistency report",
        "Status: " + ("consistent" if report["consistent"] else "inconsistent"),
        "Records: " + str(report["records"]),
        "Checked: " + str(report["checked"]),
        "Input SHA-256: " + report["input_sha256"],
    ]
    lines += [
        "Stream " + canonical(name) + ": " + canonical(report["streams"][name]) for name in sorted(report["streams"])
    ]
    lines += [
        "Line " + str(row["line"]) + " " + canonical(issue) for row in report["diagnostics"] for issue in row["issues"]
    ]
    return ("\n".join(lines) + "\n").encode()


def bundle(fix: Fixture, report: dict) -> None:
    assert {p.name for p in fix.output.iterdir()} == {"report.json", "report.txt"}
    assert canonical(json.loads((fix.output / "report.json").read_bytes())) == canonical(report)
    assert (fix.output / "report.txt").read_bytes() == text_report(report)
    return  # noqa: PLR1711


def run(app: Application, fix: Fixture, timeout: int = 30) -> dict:
    report = oracle(fix)
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file()}
    for mode in ["preview", "write"]:
        result = app.run(fix.work, fix.settings(mode), timeout=timeout)
        assert result.returncode == (0 if report["consistent"] else 1), result.stderr
        assert canonical(json.loads(result.stdout)) == canonical(report)
        if mode == "preview":
            assert not fix.output.exists()
        else:
            bundle(fix, report)
    assert not list(fix.work.glob(".event-log-*"))
    assert all((fix.work / name).read_bytes() == value for name, value in before.items())
    again = app.run(fix.work, fix.settings())
    assert again.returncode == 2 and "already exists" in again.stderr
    bundle(fix, report)
    return report


def reject(app: Application, fix: Fixture, message: str = "", **settings: str) -> None:
    before = {p.name: p.read_bytes() for p in fix.work.iterdir() if p.is_file() and not p.is_symlink()}
    result = app.run(fix.work, fix.settings(**settings), timeout=60)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, result.stderr
    assert not fix.output.exists() and not list(fix.work.glob(".event-log-*"))
    assert all((fix.work / name).read_bytes() == value for name, value in before.items())
    return  # noqa: PLR1711


def check_sequences(app: Application, directory: Path) -> int:
    maximum = 2**63 - 1
    patterns = [
        [],
        [1],
        [2],
        [1, 3, 2, 4],
        [1, 1, 2],
        [3, 2, 1],
        [3, maximum, 7],
        [maximum],
        [1, 3, 5, 7, 2, 6],
        [maximum, maximum - 1],
        [3, 4, 3, 5],
    ]
    count = 0
    for first in [1, 3, maximum]:
        for pattern in patterns:
            rows = [event(i + 1, sequence=sequence) for i, sequence in enumerate(pattern)]
            report = run(app, fixture(directory, f"seq-{count}", rows, first_sequence=first))
            if pattern == [1, 3, 2, 4] and first == 1:
                assert report["streams"]["a"]["missing"] == [] and report["issue_counts"]["sequence_gap"] == 1
            if pattern == [3, maximum, 7] and first == 1:
                assert report["streams"]["a"]["missing_count"] == maximum - 3
            count += 1
    rows = [event(1), event(2), event(3, stream="b", sequence=1, before="new")]
    rows += [
        copy.deepcopy(rows[0]),
        {**rows[0], "time": "2026-01-01T05:00:01+05:00", "data": None},
        {**rows[0], "data": "conflict"},
        {**rows[0], "stream": "other"},
        event(6, sequence=2),
        {**event(6, sequence=2), "data": "second use of rejected ID"},
        event(7, sequence=3),
    ]
    report = run(app, fixture(directory, "identifiers", rows))
    assert report["issue_counts"]["duplicate_id"] == 2
    assert report["issue_counts"]["conflicting_id"] == 3
    assert report["duplicate_records"] == 6 and "other" not in report["streams"]
    return count + 1


def check_time_states(app: Application, directory: Path) -> int:
    times = [
        "2026-01-01T00:00:00Z",
        "2026-01-01T05:00:00+05:00",
        "2026-01-01T00:00:00.000001Z",
        "2025-12-31T21:00:00.000002-03:00",
        "2026-01-01T00:00:00.000001Z",
        "2026-01-01T00:00:00.000001Z",
    ]
    rows = [event(i + 1, time=value) for i, value in enumerate(times)]
    report = run(app, fixture(directory, "times", rows))
    assert report["issue_counts"] == {"stream_time_regression": 2, "global_time_regression": 2}
    interleaved = [
        event(1, time="2026-01-01T00:00:02Z"),
        event(1, "b", time="2026-01-01T00:00:01Z"),
        event(2, "b", time="2026-01-01T00:00:01.5Z"),
    ]
    for enabled in [True, False]:
        report = run(app, fixture(directory, "global-" + str(enabled), interleaved, global_time_order=enabled))
        assert report["consistent"] == (not enabled)
    states = ["new", "active", "paused", "closed"]
    for i, before in enumerate(states):
        for j, after in enumerate(states):
            run(app, fixture(directory, f"edge-{i}-{j}", [event(1), event(2, before=before, after=after)]))
    chain = [event(1, before="active", after="closed"), event(2, before="closed", after="active"), event(3)]
    report = run(app, fixture(directory, "observed-state", chain))
    assert report["streams"]["a"]["last_observed_state"] == "active" and report["checked"] == 3
    custom = fixture(
        directory,
        "custom-state",
        [event(1, before="Idle", after="Idle")],
        states=["Idle"],
        initial_state="Idle",
        transitions=[{"from": "Idle", "to": "Idle"}],
    )
    assert run(app, custom)["consistent"]
    run(app, fixture(directory, "no-transitions", [event(1)], transitions=[]))
    return 22


def check_invalid_records(app: Application, directory: Path) -> int:
    rows: list[object] = [None, [], "text", 1, True, {}, {"id": "x"}, {**event(1), "extra": 1}]
    for name, values in {
        "id": [None, True, "", " x", "x\n", "x\0", "x" * 129],
        "stream": [2, "", "x\t", "😀" * 33],
        "sequence": [None, True, 0, -1, 1.0, "1"],
        "from": [None, "missing", 1],
        "to": [False, "missing"],
        "time": [
            None,
            "2026-01-01",
            "2026-01-01T00:00:00",
            "2026-01-01T00:00:60Z",
            "2026-02-30T00:00:00Z",
            "2026-01-01T00:00:00.1234567Z",
            "2026-01-01T00:00:00+01:60",
            "2026-01-01T00:00:00+24:00",
            "0000-01-01T00:00:00Z",
            "0001-01-01T00:00:00+01:00",
            "9999-12-31T23:59:59-01:00",
            "２０２６-01-01T00:00:00Z",
        ],
    }.items():
        rows.extend({**event(1), name: value} for value in values)
    deep: object = None
    for _ in range(17):
        deep = [deep]
    rows += [{**event(1), "data": deep}, {**event(1), "data": [0] * 1000}]
    raw = encoded(rows) + b'\xff\n{bad}\n\n   \n{"id":NaN}\n{"id":"\\ud800"}\n9223372036854775808\n'
    raw += encoded([event(1, id="valid-after-errors")])
    report = run(app, fixture(directory, "invalid-records", raw))
    assert report["checked"] == 1 and report["invalid_records"] == len(rows) + 7
    combined = {**event(2), "id": "", "sequence": False, "time": "bad", "from": "absent"}
    run(app, fixture(directory, "all-fields", [combined]))
    for number, source in enumerate(
        [
            encoded([event(1)], b"\r\n"),
            encoded([event(1)])[:-1],
            b"\xef\xbb\xbf" + encoded([event(1)]),
            b" \t\r" + encoded([event(1)]),
            encoded([event(1)], b"\r") + encoded([event(2)]),
        ]
    ):
        run(app, fixture(directory, "lines-" + str(number), source))
    for number, value in enumerate(["0001-01-01T00:00:00Z", "9999-12-31T23:59:59.999999Z", "2024-02-29T23:59:59.1Z"]):
        run(app, fixture(directory, "valid-time-" + str(number), [event(1, time=value)]))
    return len(rows) + 16


def check_generated(app: Application, directory: Path) -> dict:
    rng = random.Random(460046)
    rows, counters, states = [], Counter(), defaultdict(lambda: "new")
    options = {"new": ["active"], "active": ["active", "paused", "closed"], "paused": ["active"], "closed": []}
    for number in range(180):
        choices = [name for name in ["a", "b", "c", "d", "世界"] if options[states[name]]]
        if not choices:
            break
        name = rng.choice(choices)
        counters[name] += 1
        before, after = states[name], rng.choice(options[states[name]])
        states[name] = after
        rows.append(
            event(number + 1, name, sequence=counters[name], before=before, after=after, data={"value": number})
        )
    hashes = []
    for case in range(24):
        changed = copy.deepcopy(rows)
        for _ in range(case % 7):
            index = rng.randrange(len(changed))
            action = rng.randrange(5)
            if action == 0:
                changed.insert(index, copy.deepcopy(changed[index]))
            elif action == 1:
                changed[index]["sequence"] += 2
            elif action == 2:
                changed[index]["from"] = "closed"
            elif action == 3:
                changed[index]["time"] = "2025-01-01T00:00:00Z"
            else:
                changed[index]["id"] = changed[0]["id"]
        report = run(app, fixture(directory, f"generated-{case}", changed))
        hashes.append(hashlib.sha256(canonical(report).encode()).hexdigest())
    return {
        "cases": 24,
        "baseline_rows": len(rows),
        "reports_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
    }


def check_configuration(app: Application, directory: Path) -> int:
    changes = [
        {"extra": 1},
        {"states": []},
        {"states": ["new", "new"]},
        {"states": ["new", "bad space"]},
        {"states": ["s" + str(i) for i in range(33)]},
        {"initial_state": "absent"},
        {"transitions": {}},
        {"transitions": [{"from": "new", "to": "absent"}]},
        {"transitions": [{"from": "new", "to": "active"}] * 2},
        {"transitions": [{"from": "new", "to": "active", "extra": 1}]},
        {"first_sequence": 0},
        {"first_sequence": True},
        {"first_sequence": 1.0},
        {"global_time_order": 1},
        {"input": "missing"},
        {"input": ""},
        {"output": "events.jsonl"},
        {"output": "event-job.json"},
        {"output": "missing/child"},
    ]
    for name, limit in [
        ("max_streams", 1000),
        ("max_records", 10000),
        ("max_line_bytes", 65536),
        ("max_input_bytes", 8388608),
    ]:
        changes.extend({name: value} for value in [0, limit + 1, True, 1.5, "1"])
    for number, change in enumerate(changes):
        reject(app, fixture(directory, f"bad-config-{number}", [], **change))
    for number, data in enumerate([b"[]", b"{}", b"{", b"\xff", b"{}" + b" " * 65536]):
        fix = fixture(directory, f"bad-config-json-{number}", [])
        fix.path.write_bytes(data)
        reject(app, fix)
    reject(app, fixture(directory, "bad-mode", []), EVENT_MODE="check")
    return len(changes) + 6


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(EVENT_PAUSE=point, EVENT_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(20), "event checker did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    output, error = process.communicate(timeout=30)
    return subprocess.CompletedProcess(process.args, process.returncode, output, error)


def check_publication(app: Application, directory: Path) -> int:
    points = ["row:1", "validated", "stage", "report.json", "report.txt", "ready", "published"]
    for point in points:
        for killed in [False, True]:
            fix = fixture(directory, f"fault-{point.replace(':', '-')}-{killed}", [event(1), event(3, sequence=3)])
            report = oracle(fix)
            if killed:
                process = pause(app, fix, point)
                process.kill()
                process.communicate(timeout=10)
                assert process.returncode == -9
            else:
                result = app.run(fix.work, fix.settings(EVENT_FAIL=point))
                assert result.returncode == 2 and "injected failure: " + point in result.stderr
            if point == "published":
                bundle(fix, report)
            else:
                assert not fix.output.exists()
            stages = list(fix.work.glob(".event-log-*"))
            assert len(stages) == int(killed and point not in ["row:1", "validated", "published"])
            for stage in stages:
                shutil.rmtree(stage)
            if point != "published":
                run(app, fix)
    count = len(points) * 2
    for point in ["row:1", "validated", "ready"]:
        for name in ["events.jsonl", "event-job.json", "output"]:
            fix = fixture(directory, f"changed-{point.replace(':', '-')}-{name}", [event(1), event(2)])
            process = pause(app, fix, point)
            try:
                if name == "output":
                    fix.output.mkdir()
                    (fix.output / "keep").write_bytes(b"untouched")
                else:
                    path = fix.work / name
                    path.write_bytes(path.read_bytes() + b" ")
                result = resume(process, fix)
                assert result.returncode == 2 and not list(fix.work.glob(".event-log-*"))
                if name == "output":
                    assert {p.name for p in fix.output.iterdir()} == {"keep"}
                    assert (fix.output / "keep").read_bytes() == b"untouched"
                else:
                    assert not fix.output.exists() and "changed" in result.stderr
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            count += 1
    for point in ["stage", "report.json"]:
        fix = fixture(directory, "permission-" + point, [event(1)])
        process = pause(app, fix, point)
        stage = next(fix.work.glob(".event-log-*"))
        try:
            assert os.getuid() != 0
            stage.chmod(0o500)
            result = resume(process, fix)
            assert result.returncode == 2 and "Permission denied" in result.stderr and not fix.output.exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if stage.exists():
                stage.chmod(0o700)
                shutil.rmtree(stage)
        (fix.work / "continue").unlink()
        run(app, fix)
        count += 1
    return count


def check_paths(app: Application, directory: Path) -> int:
    for kind in ["symlink", "fifo", "directory", "output-file", "output-directory", "output-symlink", "permission"]:
        fix = fixture(directory, "paths-" + kind, [event(1)])
        if kind == "symlink":
            fix.source.rename(fix.work / "original")
            fix.source.symlink_to("original")
        elif kind == "fifo":
            fix.source.unlink()
            os.mkfifo(fix.source)
        elif kind == "directory":
            fix.source.unlink()
            fix.source.mkdir()
        elif kind == "output-file":
            fix.output.write_bytes(b"keep")
        elif kind == "output-directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif kind == "output-symlink":
            fix.output.symlink_to("missing")
        else:
            fix.work.chmod(0o500)
        try:
            result = app.run(fix.work, fix.settings(), timeout=10)
            assert result.returncode == 2 and not list(fix.work.glob(".event-log-*"))
            if kind == "output-file":
                assert fix.output.read_bytes() == b"keep"
            if kind == "output-directory":
                assert (fix.output / "keep").read_bytes() == b"keep"
            if kind == "output-symlink":
                assert fix.output.is_symlink() and os.readlink(fix.output) == "missing"
        finally:
            fix.work.chmod(0o700)
    return 7


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    run(limited, fixture(directory, "records-exact", [event(i) for i in range(1, 10001)]), timeout=120)
    reject(limited, fixture(directory, "records-above", [event(1), event(2)], max_records=1), "record limit")
    run(limited, fixture(directory, "streams-exact", [event(1, f"s{i}") for i in range(1000)]), timeout=120)
    reject(limited, fixture(directory, "streams-above", [event(1, "a"), event(1, "b")], max_streams=1), "stream limit")
    base = encoded([event(1, data="")])
    row = encoded([event(1, data="x" * (65536 - len(base)))])
    assert len(row) == 65536
    report = run(limited, fixture(directory, "line-exact", row))
    assert report["consistent"]
    report = run(limited, fixture(directory, "line-above", row[:-1] + b" \n"))
    assert report["issue_counts"] == {"oversized_record": 1}
    report = run(limited, fixture(directory, "large-invalid-line", b"\xff" * 8388608), timeout=120)
    assert report["issue_counts"] == {"oversized_record": 1} and report["input_bytes"] == 8388608
    reject(limited, fixture(directory, "input-above", b" " * 8388609), "byte limit")
    run(limited, fixture(directory, "id-exact", [event(1, id="😀" * 32, stream="x" * 128)]))
    nested: object = None
    for _ in range(16):
        nested = [nested]
    run(limited, fixture(directory, "payload-depth", [event(1, data=nested)]))
    run(limited, fixture(directory, "payload-nodes", [event(1, data=[0] * 999)]))
    # Input stays below 8 MiB; diagnostic indentation would expand beyond the report budget.
    rows = [event(i + 1, before="closed", data=[0] * 999) for i in range(2500)]
    fix = fixture(directory, "report-overflow", rows)
    assert fix.source.stat().st_size <= 8388608
    reject(limited, fix, "diagnostic report exceeds 16 MiB")
    return {
        "memory_limit": 268435456,
        "records": 10000,
        "streams": 1000,
        "input_bytes": 8388608,
        "line_bytes": 65536,
        "id_bytes": 128,
        "payload_nodes": 1000,
        "payload_depth": 16,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "sequence_cases": check_sequences(app, directory),
        "time_state_cases": check_time_states(app, directory),
        "invalid_record_cases": check_invalid_records(app, directory),
        "generated": check_generated(app, directory),
        "configuration_cases": check_configuration(app, directory),
        "publication_cases": check_publication(app, directory),
        "path_cases": check_paths(app, directory),
        "limits": check_limits(app, directory),
    }
