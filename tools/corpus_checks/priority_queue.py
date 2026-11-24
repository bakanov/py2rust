# ruff: noqa: PLR1711 - explicit returns and supported subset operations
"""An independent sorted-record scheduler verifies stable priorities, retries and persisted state."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

COUNTERS = ["steps", "enqueued", "popped", "retried", "completed", "cancelled_queued", "cancelled_running"]


def command(op: str, identifier: str = "", **fields: object) -> dict:
    return {"op": op, **({"id": identifier} if op in {"ENQUEUE", "ACK", "CANCEL", "RETRY"} else {}), **fields}


def envelope(state: dict) -> dict:
    return {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}


def fresh(capacity: int) -> dict:
    return {"version": 1, "capacity": capacity, "next_sequence": 1, "jobs": [], "stats": dict.fromkeys(COUNTERS, 0)}


def sample() -> list:
    return [
        command("ENQUEUE", "z", priority=5, payload=None),
        command("ENQUEUE", "a", priority=5, payload={"text": "世界😀"}),
        command("ENQUEUE", "urgent", priority=-2, payload=[False, 1.5]),
        command("PEEK"),
        command("POP"),
        command("RETRY", "urgent", priority=5),
        command("POP"),
        command("ACK", "z"),
        command("CANCEL", "a"),
        command("ENQUEUE", "a", priority=5, payload="replacement"),
        command("PEEK"),
        command("POP"),
        command("RETRY", "urgent", priority=0),
        command("POP"),
        command("CANCEL", "urgent"),
        command("ACK", "a"),
        command("POP"),
        command("ACK", "a"),
        command("POP"),
        command("RETRY", "missing", priority=0),
        command("INSPECT"),
    ]


def oracle(fix: Fixture) -> tuple[dict, list, dict]:
    state = fresh(fix.config["capacity"])
    if fix.config["state"]:
        state = json.loads((fix.work / fix.config["state"]).read_bytes())["state"]
    records = copy.deepcopy(state["jobs"])
    stats, sequence = copy.deepcopy(state["stats"]), state["next_sequence"]
    before = stats["steps"]
    trace = json.loads((fix.work / fix.config["trace"]).read_bytes())
    events = []

    def view() -> dict:
        return copy.deepcopy(
            {
                "queued": sorted(
                    [row for row in records if row["status"] == "queued"],
                    key=lambda row: (row["priority"], row["sequence"]),
                ),
                "running": sorted([row for row in records if row["status"] == "running"], key=lambda row: row["id"]),
                "capacity": state["capacity"],
                "stats": stats,
            }
        )

    for instruction in trace:
        operation, name = instruction["op"], instruction.get("id")
        job = next((row for row in records if row["id"] == name), None)
        stats["steps"] += 1
        event = {"step": stats["steps"], "op": operation, "accepted": True}
        if name is not None:
            event["id"] = name
        reason = ""
        if operation == "ENQUEUE":
            if job is not None:
                reason = "duplicate_id"
            elif len(records) >= state["capacity"]:
                reason = "capacity"
            else:
                job = {
                    "id": name,
                    "priority": instruction["priority"],
                    "sequence": sequence,
                    "payload": copy.deepcopy(instruction["payload"]),
                    "status": "queued",
                    "attempts": 0,
                }
                sequence += 1
                records.append(job)
                stats["enqueued"] += 1
                event["job"] = job
        elif operation in {"POP", "PEEK"}:
            waiting = [row for row in records if row["status"] == "queued"]
            if waiting:
                selected = min(waiting, key=lambda row: (row["priority"], row["sequence"]))
                if operation == "POP":
                    selected["status"] = "running"
                    selected["attempts"] += 1
                    stats["popped"] += 1
                event["job"] = selected
            else:
                reason = "empty"
                event["job"] = None
        elif operation in {"ACK", "RETRY", "CANCEL"}:
            if job is None:
                reason = "not_found"
            elif operation != "CANCEL" and job["status"] != "running":
                reason = "not_running"
            elif operation == "RETRY":
                job.update(priority=instruction["priority"], sequence=sequence, status="queued")
                sequence += 1
                stats["retried"] += 1
                event["job"] = job
            else:
                stats["completed" if operation == "ACK" else "cancelled_" + job["status"]] += 1
                records.remove(job)
                event["job"] = job
        else:
            assert operation == "INSPECT"
            event["queue"] = view()
        if reason:
            event.update(accepted=False, reason=reason)
        events.append(copy.deepcopy(event))
    saved = {
        "version": 1,
        "capacity": state["capacity"],
        "next_sequence": sequence,
        "jobs": sorted(records, key=lambda row: row["id"]),
        "stats": stats,
    }
    report = {"before_steps": before, "after_steps": stats["steps"], "commands": len(trace), "queue": view()}
    return envelope(saved), events, report


def invalid_commands(app: Application, directory: Path) -> int:
    bad = [None, [], {}, {"op": "pop"}, {"op": 1}, {"op": "UNKNOWN"}]
    for op in ["ENQUEUE", "POP", "PEEK", "ACK", "CANCEL", "RETRY", "INSPECT"]:
        fields = {"priority": 0} if op in {"ENQUEUE", "RETRY"} else {}
        if op == "ENQUEUE":
            fields["payload"] = None
        valid = command(op, "k", **fields)
        bad += [{**valid, "extra": True}]
        for field in valid:
            bad.append({key: value for key, value in valid.items() if key != field})
    for name in ["", "😀" * 33, None, True, 1]:
        bad.append(command("ENQUEUE", name, priority=0, payload=None))
    for priority in [None, True, "1", 1.5, 2**63, -(2**63) - 1]:
        bad.append(command("ENQUEUE", "k", priority=priority, payload=None))
    nested = None
    for _ in range(17):
        nested = [nested]
    bad += [command("ENQUEUE", "k", priority=0, payload=value) for value in [nested, "😀" * 4096]]
    for index, instruction in enumerate(bad):
        fix = fixture(directory, f"invalid-command-{index}", [command("POP"), instruction])
        priority = instruction.get("priority") if isinstance(instruction, dict) else None
        message = "" if type(priority) is int and not -(2**63) <= priority < 2**63 else "command 2:"
        failure(app, fix, message)
    settings = [
        {field: value}
        for field, values in {
            "capacity": [0, 257, True, "3"],
            "state": [None],
            "trace": ["", "\x00"],
            "output": [""],
        }.items()
        for value in values
    ]
    settings += [{"extra": 1}]
    for index, changes in enumerate(settings):
        fix = fixture(directory, f"invalid-config-{index}", [])
        fix.config.update(changes)
        fix.save()
        failure(app, fix, "")
    for index, content in enumerate([b"{", b"\xff", b"null", b"{}", b"[NaN]"]):
        fix = fixture(directory, f"invalid-trace-{index}", [])
        (fix.work / "trace.json").write_bytes(content)
        failure(app, fix, "")
    return len(bad) + len(settings) + 5


def states(app: Application, directory: Path) -> int:
    fix = fixture(directory, "state-origin", sample()[:6])
    initial = success(app, fix)[0]["state"]
    mutations = []
    for field, value in [
        ("version", 2),
        ("capacity", 0),
        ("capacity", 4),
        ("next_sequence", 1),
        ("next_sequence", True),
        ("jobs", None),
        ("stats", {}),
    ]:
        mutations.append({**copy.deepcopy(initial), field: value})
    for counter in COUNTERS:
        for value in [-1, True, 1000000001]:
            state = copy.deepcopy(initial)
            state["stats"][counter] = value
            mutations.append(state)
    for field, value in [
        ("id", ""),
        ("id", "😀" * 33),
        ("priority", True),
        ("priority", 1.0),
        ("sequence", 0),
        ("sequence", 4),
        ("sequence", True),
        ("status", "done"),
        ("status", "running"),
        ("attempts", -1),
        ("attempts", 100),
        ("payload", "x" * 16383),
    ]:
        state = copy.deepcopy(initial)
        state["jobs"][0][field] = value
        mutations.append(state)
    for container in ["state", "job", "stats"]:
        for change in ["missing", "extra"]:
            state = copy.deepcopy(initial)
            target = state if container == "state" else (state["jobs"][0] if container == "job" else state["stats"])
            if change == "missing":
                target.pop(next(iter(target)))
            else:
                target["extra"] = None
            mutations.append(state)
    for field in ["id", "sequence"]:
        state = copy.deepcopy(initial)
        state["jobs"][0][field] = state["jobs"][1][field]
        mutations.append(state)
    state = copy.deepcopy(initial)
    state["jobs"] = state["jobs"][:-1]
    mutations.append(state)
    state = copy.deepcopy(initial)
    state["jobs"][1]["attempts"] = 0  # Retries cannot erase the only retained attempt.
    # Select the retried job independently of sorted snapshot ID positions.
    for job in state["jobs"]:
        if job["id"] == "urgent":
            job["attempts"] = 0
    mutations.append(state)
    for index, state in enumerate(mutations):
        bad = fixture(directory, f"bad-state-{index}", [], prior=envelope(state))
        failure(app, bad, "")
    raw = [None, [], {}, {"state": initial, "sha256": "invalid"}, {"state": initial, "sha256": 1}]
    for index, value in enumerate(raw):
        bad = fixture(directory, f"bad-envelope-{index}", [], prior=value)
        if value is None:
            bad.config["state"] = "prior.json"
            bad.save()
            (bad.work / "prior.json").write_text("null")
        failure(app, bad, "")
    # Array order is not scheduling order. A checksum-valid permutation rebuilds the same heap.
    permuted = copy.deepcopy(initial)
    permuted["jobs"].reverse()
    shuffled = fixture(directory, "shuffled-state", sample()[6:], prior=envelope(permuted))
    restored = success(app, shuffled)
    whole = fixture(directory, "state-whole", sample())
    assert canonical(restored[0]) == canonical(success(app, whole)[0])
    return len(mutations) + len(raw) + 1


def limits(app: Application, directory: Path) -> int:
    for size in [1, 256]:
        trace = [command("ENQUEUE", str(size - index), priority=0, payload=None) for index in range(size)]
        trace += [
            command("ENQUEUE", "overflow", priority=0, payload=None),
            command("ENQUEUE", "1", priority=0, payload=None),
        ]
        trace += [command("POP") for _ in range(size)]
        trace += [command("ENQUEUE", "still-full", priority=0, payload=None), command("INSPECT")]
        result = success(app, fixture(directory, f"full-{size}", trace, size))
        popped = [event["job"]["id"] for event in result[1] if event["op"] == "POP"]
        assert popped == [str(size - index) for index in range(size)]
        assert result[1][-2]["reason"] == "capacity"  # Running jobs still occupy slots.
    success(app, fixture(directory, "trace-max", [command("POP")] * 2000))
    failure(app, fixture(directory, "trace-too-many", [command("POP")] * 2001), "2000 commands")
    for name, target, size, message in [
        ("config", "queue-job.json", 65537, "input byte limit"),
        ("trace", "trace.json", 4194305, "input byte limit"),
        ("state", "prior.json", 8388609, "input byte limit"),
    ]:
        fix = fixture(directory, "bytes-" + name, [], prior=envelope(fresh(3)))
        with (fix.work / target).open("wb") as stream:
            stream.truncate(size)
        failure(app, fix, message)
    deep = None
    for _ in range(16):
        deep = [deep]
    success(
        app,
        fixture(
            directory,
            "payload-bound",
            [
                command("ENQUEUE", "😀" * 32, priority=-(2**63), payload="x" * 16382),
                command("ENQUEUE", "deep", priority=2**63 - 1, payload=deep),
            ],
        ),
    )
    # A small input can produce a too-large event stream via repeated inspections.
    trace = [command("ENQUEUE", "big", priority=0, payload="x" * 16382)] + [command("INSPECT")] * 1100
    failure(app, fixture(directory, "events-too-big", trace), "events exceed 16 MiB")
    capped = fresh(3)
    capped["stats"]["steps"] = 1000000000
    success(app, fixture(directory, "lifetime-at-limit", [], prior=envelope(capped)))
    failure(
        app, fixture(directory, "lifetime-overflow", [command("POP")], prior=envelope(capped)), "lifetime command limit"
    )
    fix = fixture(directory, "permission", sample())
    assert os.geteuid() != 0, "permission check needs a non-root user"
    fix.work.chmod(0o555)
    try:
        failure(app, fix, "")
    finally:
        fix.work.chmod(0o755)
    return 12


def check(app: Application, directory: Path) -> dict:
    cases = [(1, []), (3, []), (1, sample()), (3, sample()), (8, sample())]
    churn = [
        item
        for _ in range(100)
        for item in [command("ENQUEUE", "reuse", priority=99, payload=None), command("CANCEL", "reuse")]
    ]
    churn += [
        command("ENQUEUE", "reuse", priority=0, payload=True),
        command("POP"),
        command("ACK", "reuse"),
        command("POP"),
    ]
    cases.append((1, churn))
    rng = random.Random(530053)
    values = [None, False, True, -0.0, 5e-324, 2**63 - 1, "\x00世界😀", {"a": [1.5, None]}]
    for _ in range(32):
        trace = []
        for _index in range(180):
            op = rng.choice(["ENQUEUE"] * 4 + ["POP"] * 3 + ["RETRY"] * 2 + ["ACK", "CANCEL", "PEEK", "INSPECT"])
            fields = {"priority": rng.choice([-5, 0, 0, 1, 2**63 - 1, -(2**63)])} if op in {"ENQUEUE", "RETRY"} else {}
            if op == "ENQUEUE":
                fields["payload"] = rng.choice(values)
            trace.append(command(op, rng.choice(["a", "b", "c", "é", "e\u0301", "世界", "a\x00b"]), **fields))
        cases.append((rng.randrange(1, 9), trace))
    observations = []
    for index, (size, trace) in enumerate(cases):
        fix = fixture(directory, f"trace-{index}", trace, size)
        success(app, fix, "preview")
        expected = success(app, fix)
        observations.append(expected)
        resumed = fixture(directory, f"unchanged-{index}", [], size, state=str(fix.output / "state.json"))
        success(app, resumed)
        assert (resumed.output / "state.json").read_bytes() == (fix.output / "state.json").read_bytes()
    whole = fixture(directory, "full", sample())
    complete = success(app, whole)
    for split in range(len(sample()) + 1):
        prefix = fixture(directory, f"prefix-{split}", sample()[:split])
        success(app, prefix)
        suffix = fixture(directory, f"suffix-{split}", sample()[split:], state=str(prefix.output / "state.json"))
        result = success(app, suffix)
        assert canonical(result[0]) == canonical(complete[0])
        assert (prefix.output / "events.jsonl").read_bytes() + (suffix.output / "events.jsonl").read_bytes() == (
            whole.output / "events.jsonl"
        ).read_bytes()
    return {
        "traces": len(cases),
        "generated_traces": 32,
        "split_replays": len(sample()) + 1,
        "invalid_inputs": invalid_commands(app, directory),
        "state_checks": states(app, directory),
        "capacity_checks": limits(app, directory),
        "publication_checks": publication(app, directory),
        "results_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "queue-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "QUEUE_CONFIG": str(self.path),
            "QUEUE_MODE": mode,
            "QUEUE_FAIL": "",
            "QUEUE_PAUSE": "",
            "QUEUE_CONTINUE": "",
            **extra,
        }


def fixture(
    directory: Path, name: str, commands: list, capacity: int = 3, prior: dict | None = None, **changes: object
) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "trace.json").write_text(json.dumps(commands, ensure_ascii=False))
    config = {"trace": "trace.json", "state": "", "capacity": capacity, "output": "queue-run", **changes}
    if prior is not None:
        (work / "prior.json").write_text(canonical(prior))
        config["state"] = "prior.json"
    fix = Fixture(work, config)
    fix.save()
    return fix


def outputs(fix: Fixture, expected: tuple[dict, list, dict]) -> None:
    saved, events, report = expected
    assert sorted(path.name for path in fix.output.iterdir()) == ["events.jsonl", "report.json", "state.json"]
    assert (fix.output / "state.json").read_text() == canonical(saved) + "\n"
    assert (fix.output / "events.jsonl").read_text() == "".join(canonical(event) + "\n" for event in events)
    assert canonical(json.loads((fix.output / "report.json").read_bytes())) == canonical(report)
    return


def success(app: Application, fix: Fixture, mode: str = "write") -> tuple[dict, list, dict]:
    expected = oracle(fix)
    inputs = [fix.path, fix.work / fix.config["trace"]]
    if fix.config["state"]:
        inputs.append(fix.work / fix.config["state"])
    before = [path.read_bytes() for path in inputs]
    result = app.run(fix.work, fix.settings(mode), timeout=45)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    assert canonical(json.loads(result.stdout)) == canonical(expected[2])
    assert [path.read_bytes() for path in inputs] == before
    if mode == "write":
        outputs(fix, expected)
        assert (fix.output / "report.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".priority-queue-*"))
    return expected


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and not result.stdout, (result, message, fix.config)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".priority-queue-*"))
    return


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(QUEUE_PAUSE="ready", QUEUE_CONTINUE=str(signal))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(10))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        output, error = process.communicate(timeout=5)
        raise AssertionError((output, error))
    return process


def publication(app: Application, directory: Path) -> int:
    points = ["validated", "stage", "state.json", "events.jsonl", "report.json", "ready", "published"]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample())
        result = app.run(fix.work, fix.settings(QUEUE_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".priority-queue-*"))
        if point == "published":
            outputs(fix, oracle(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["trace", "configuration", "state", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), prior=envelope(fresh(3)))
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                filename = {"trace": "trace.json", "configuration": "queue-job.json", "state": "prior.json"}[name]
                with (fix.work / filename).open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=10)
            assert process.returncode == 2 and not output, (output, error)
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
            assert not list(fix.work.glob(".priority-queue-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "killed", sample())
    process = paused(app, fix)
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".priority-queue-*"))
    assert len(abandoned) == 1
    contents = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0
    outputs(fix, oracle(fix))
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == contents
    for name in ["file", "directory", "symlink", "dangling", "same-trace", "same-config"]:
        fix = fixture(directory, "existing-" + name, [])
        if name == "file":
            fix.output.write_bytes(b"keep")
        elif name == "directory":
            fix.output.mkdir()
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("trace.json" if name == "symlink" else "absent"))
        else:
            fix.config["output"] = "trace.json" if name == "same-trace" else "queue-job.json"
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["trace.json", "queue-job.json", "prior.json"]:
        fix = fixture(directory, "link-" + name, [], prior=envelope(fresh(3)))
        path = fix.work / name
        original = path.with_suffix(".original")
        path.rename(original)
        path.symlink_to(original)
        failure(app, fix, "input must be a regular file")
    return len(points) + 4 + 1 + 6 + 3
