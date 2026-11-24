"""Independent interval oracle, restarted daemons and durable crash-boundary checks."""

# ruff: noqa: PLR1711 - explicit repository returns
import copy
import datetime as dt
import hashlib
import json
import os
import random
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .common import Application


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def utc(seconds: int) -> str:
    value = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)
    return value.isoformat().replace("+00:00", "Z")


def policies(start: int = 100, every: int = 10) -> list[dict]:
    return [
        {"id": kind, "message": f"{kind}: take a break 世界 😀", "start": start, "every": every, "policy": kind}
        for kind in ["all", "latest", "skip"]
    ]


def initial(reminders: list[dict]) -> dict:
    return {
        "version": 1,
        "policy": reminders,
        "clock": -1,
        "ticks": 0,
        "sequence": 0,
        "records": [{"id": row["id"], "next": row["start"], "emitted": 0, "skipped": 0} for row in reminders],
        "history": [],
    }


def oracle(reminders: list[dict], times: list[int], previous: dict | None = None) -> tuple[dict, list[dict]]:
    state = copy.deepcopy(previous if previous is not None else initial(reminders))
    events = []
    for observed in times:
        observed = max(state["clock"], observed)
        for reminder, record in zip(reminders, state["records"], strict=True):
            pending = range(record["next"], observed + 1, reminder["every"])
            if not pending:
                continue
            selected = list(pending[:16]) if reminder["policy"] == "all" else [pending[-1]]
            if reminder["policy"] == "skip" and selected[-1] != observed:
                selected = []
            consumed = len(selected) if reminder["policy"] == "all" else len(pending)
            for scheduled in selected:
                state["sequence"] += 1
                event = {
                    "sequence": state["sequence"],
                    "id": reminder["id"],
                    "message": reminder["message"],
                    "scheduled": scheduled,
                    "scheduled_utc": utc(scheduled),
                    "observed": observed,
                    "observed_utc": utc(observed),
                    "late_seconds": observed - scheduled,
                }
                events.append(event)
                state["history"].append(event)
            record["next"] += consumed * reminder["every"]
            record["emitted"] += len(selected)
            record["skipped"] += consumed - len(selected)
        state["history"] = state["history"][-256:]
        state["ticks"] += 1
        state["clock"] = observed
    return state, events


def view(state: dict) -> dict:
    return {
        "clock": state["clock"],
        "ticks": state["ticks"],
        "sequence": state["sequence"],
        "records": [dict(row, next_utc=utc(row["next"])) for row in state["records"]],
        "history": state["history"],
    }


def encoded(state: dict) -> bytes:
    return canonical({"state": state, "sha256": hashlib.sha256(canonical(state)).hexdigest()}) + b"\n"


@dataclass
class Fixture:
    directory: Path
    reminders: list[dict]

    @property
    def store(self) -> Path:
        return self.directory / "state.json"

    @property
    def settings(self) -> dict:
        return {"REMINDER_CONFIG": str(self.directory / "job.json"), "REMINDER_TRACE": "clock.json"}


def fixture(directory: Path, reminders: list[dict] | None = None) -> Fixture:
    directory.mkdir(parents=True)
    reminders = policies() if reminders is None else reminders
    (directory / "job.json").write_text(json.dumps({"version": 1, "store": "state.json", "reminders": reminders}))
    (directory / "clock.json").write_text("[]")
    return Fixture(directory, reminders)


def logs(result: subprocess.CompletedProcess) -> list[dict]:
    return [json.loads(line.split("REMINDER ", 1)[1]) for line in result.stderr.splitlines() if "REMINDER " in line]


def run(app: Application, case: Fixture, times: list[int], previous: dict | None = None) -> tuple[dict, list[dict]]:
    (case.directory / "clock.json").write_text(json.dumps(times))
    inputs = {name: (case.directory / name).read_bytes() for name in ["job.json", "clock.json"]}
    expected, events = oracle(case.reminders, times, previous)
    result = app.run(case.directory, case.settings, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == view(expected)
    assert logs(result) == events
    assert len(result.stderr.splitlines()) == len(events)
    assert case.store.read_bytes() == encoded(expected)
    assert all((case.directory / name).read_bytes() == value for name, value in inputs.items())
    before = case.store.stat().st_mtime_ns
    inspected = app.run(case.directory, dict(case.settings, REMINDER_MODE="inspect"))
    assert inspected.returncode == 0 and not inspected.stderr, inspected
    assert json.loads(inspected.stdout) == view(expected)
    assert case.store.stat().st_mtime_ns == before
    return expected, events


def invalid_inputs(app: Application, directory: Path) -> int:
    case = fixture(directory)
    path = directory / "job.json"
    base = json.loads(path.read_text())
    invalid = [
        dict(base, **change)
        for change in [
            {"version": True},
            {"version": 2},
            {"extra": 1},
            {"store": ""},
            {"store": True},
            {"store": "job.json"},
            {"store": "clock.json"},
            {"store": "missing/state"},
            {"reminders": []},
            {"reminders": base["reminders"] * 11},
            {"reminders": base["reminders"] * 2},
        ]
    ]
    for key in base:
        changed = copy.deepcopy(base)
        del changed[key]
        invalid.append(changed)
    for change in [
        {"id": ""},
        {"id": "x" * 33},
        {"id": "1a"},
        {"id": "é"},
        {"message": ""},
        {"message": "😀" * 65},
        {"message": "a\n"},
        {"message": "\x00"},
        {"message": 4},
        {"start": -1},
        {"start": 4102444800},
        {"start": True},
        {"start": 1.5},
        {"every": 0},
        {"every": 31536001},
        {"every": "10"},
        {"policy": "ignore"},
        {"extra": 1},
    ]:
        invalid.append(dict(base, reminders=[dict(base["reminders"][0], **change)]))
    (directory / "folder").mkdir()
    (directory / "link").symlink_to(path)
    (directory / "dangling").symlink_to(directory / "absent")
    os.link(path, directory / "alias")
    for name in ["folder", "link", "dangling", "alias"]:
        invalid.append(dict(base, store=name))
    for config in invalid:
        path.write_text(json.dumps(config))
        names = sorted(p.name for p in directory.iterdir())
        result = app.run(directory, case.settings)
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        assert sorted(p.name for p in directory.iterdir()) == names
        assert not case.store.exists()
    path.write_text(json.dumps(base))
    for trace in [[-1], [4102444800], [True], [1.2], ["1"], {}, [0] * 1001]:
        (directory / "clock.json").write_text(json.dumps(trace))
        result = app.run(directory, case.settings)
        assert result.returncode == 2 and not case.store.exists() and not (directory / "state.json.lock").exists()
    (directory / "clock.json").write_text("[]")
    for settings in [
        {"REMINDER_MODE": "unknown"},
        {"REMINDER_POLLS": "true"},
        {"REMINDER_POLLS": "100001"},
        {"REMINDER_INTERVAL_MS": "9"},
        {"REMINDER_INTERVAL_MS": "60001"},
        {"REMINDER_STOP": "state.json"},
    ]:
        result = app.run(directory, dict(case.settings, **settings))
        assert result.returncode == 2 and not case.store.exists() and not (directory / "state.json.lock").exists()
    for data in [b"\xff", b"[", b" " * 65537]:
        (directory / "clock.json").write_bytes(data)
        result = app.run(directory, case.settings)
        assert result.returncode == 2 and not case.store.exists() and not (directory / "state.json.lock").exists()
    (directory / "clock.json").write_text("[]")
    lock = directory / "state.json.lock"
    for target in [path, directory / "absent"]:
        lock.symlink_to(target)
        result = app.run(directory, case.settings)
        assert result.returncode == 2 and not case.store.exists() and lock.is_symlink()
        lock.unlink()
    os.link(path, lock)
    result = app.run(directory, case.settings)
    assert result.returncode == 2 and not case.store.exists() and lock.read_bytes() == path.read_bytes()
    lock.unlink()
    return len(invalid) + 7 + 6 + 6


def corrupt_states(app: Application, directory: Path) -> int:
    case = fixture(directory)
    original, _events = run(app, case, [100, 145, 150])
    malformed = []
    for key, value in [
        ("version", 2),
        ("clock", -1),
        ("clock", 99),
        ("ticks", 0),
        ("ticks", True),
        ("sequence", 99),
        ("history", []),
        ("records", []),
        ("policy", []),
    ]:
        changed = copy.deepcopy(original)
        changed[key] = value
        malformed.append(changed)
    for key, value in [("id", "wrong"), ("next", 151), ("emitted", -1), ("skipped", 1)]:
        changed = copy.deepcopy(original)
        changed["records"][0][key] = value
        malformed.append(changed)
    for key, value in [
        ("sequence", 42),
        ("id", "missing"),
        ("message", "changed"),
        ("scheduled", 101),
        ("observed", 99),
        ("late_seconds", 1),
        ("scheduled_utc", "bad"),
        ("observed_utc", "bad"),
    ]:
        changed = copy.deepcopy(original)
        changed["history"][0][key] = value
        malformed.append(changed)
    contents = [b"{", b"x" * 1048577, canonical({"state": original, "sha256": "0" * 64})]
    contents.extend(encoded(state) for state in malformed)
    changed = copy.deepcopy(original)
    event = next(row for row in changed["history"] if row["id"] == "latest" and row["observed"] == 145)
    event.update(scheduled=130, scheduled_utc=utc(130), late_seconds=15)
    contents.append(encoded(changed))
    changed = copy.deepcopy(original)
    event = next(row for row in changed["history"] if row["id"] == "skip")
    event.update(observed=101, observed_utc=utc(101), late_seconds=1)
    contents.append(encoded(changed))
    for content in contents:
        case.store.write_bytes(content)
        result = app.run(directory, dict(case.settings, REMINDER_MODE="inspect"))
        assert result.returncode == 2 and not result.stdout and result.stderr
        assert case.store.read_bytes() == content
    case.store.write_bytes(encoded(original))
    config = json.loads((directory / "job.json").read_text())
    config["reminders"][0]["message"] = "changed"
    (directory / "job.json").write_text(json.dumps(config))
    result = app.run(directory, case.settings)
    assert result.returncode == 2 and case.store.read_bytes() == encoded(original)
    return len(contents) + 1


def faults(app: Application, directory: Path) -> int:
    for boundary in ["before_commit", "after_commit", "after_log"]:
        case = fixture(directory / boundary)
        (case.directory / "clock.json").write_text("[100]")
        result = app.run(case.directory, dict(case.settings, REMINDER_FAULT=boundary))
        assert result.returncode == 2 and not result.stdout
        first, events = oracle(case.reminders, [100])
        assert logs(result) == (events if boundary == "after_log" else [])
        if boundary == "before_commit":
            assert not case.store.exists()
            expected, replay = run(app, case, [100])
            assert replay == events
        else:
            assert case.store.read_bytes() == encoded(first)
            expected, replay = run(app, case, [100], first)
            assert replay == [] and expected["sequence"] == len(events)
    return 3


def killed_processes(app: Application, directory: Path) -> int:
    for boundary in ["before_commit", "after_commit", "after_log"]:
        case = fixture(directory / boundary)
        (case.directory / "clock.json").write_text("[100]")
        with (case.directory / "stdout.txt").open("w") as output, (case.directory / "stderr.txt").open("w") as error:
            process = subprocess.Popen(
                app.command,
                cwd=case.directory,
                env=app.environment(dict(case.settings, REMINDER_PAUSE=boundary)),
                stdout=output,
                stderr=error,
            )
            try:
                deadline = time.monotonic() + 15
                while "PAUSED " + boundary not in (case.directory / "stdout.txt").read_text():
                    assert process.poll() is None and time.monotonic() < deadline
                    time.sleep(0.01)
                before = case.store.read_bytes() if case.store.exists() else None
                contender = app.run(case.directory, case.settings)
                assert contender.returncode == 2 and not contender.stdout
                assert (case.store.read_bytes() if case.store.exists() else None) == before
                process.kill()
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
        first, events = oracle(case.reminders, [100])
        previous = None if boundary == "before_commit" else first
        _state, replay = run(app, case, [100], previous)
        assert replay == (events if previous is None else [])
    return 3


def live_clock(app: Application, directory: Path) -> None:
    before = int(time.time())
    case = fixture(directory, policies(before - 1, 1))
    result = app.run(directory, dict(case.settings, REMINDER_MODE="run", REMINDER_POLLS="3", REMINDER_INTERVAL_MS="10"))
    after = int(time.time())
    assert result.returncode == 0, result
    report = json.loads(result.stdout)
    assert report["ticks"] == 3 and before <= report["clock"] <= after
    assert all(before <= event["observed"] <= after for event in logs(result))
    inspected = app.run(directory, dict(case.settings, REMINDER_MODE="inspect"))
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == report
    before_state = case.store.read_bytes()
    (directory / "stop").touch()
    stopped = app.run(directory, dict(case.settings, REMINDER_MODE="run", REMINDER_STOP="stop"))
    assert stopped.returncode == 0 and not stopped.stderr and case.store.read_bytes() == before_state
    (directory / "stop").unlink()
    with (directory / "live-output.txt").open("w") as output, (directory / "live-error.txt").open("w") as error:
        process = subprocess.Popen(
            app.command,
            cwd=directory,
            env=app.environment(
                dict(case.settings, REMINDER_MODE="run", REMINDER_STOP="stop", REMINDER_INTERVAL_MS="10")
            ),
            stdout=output,
            stderr=error,
        )
        try:
            deadline = time.monotonic() + 10
            while json.loads(case.store.read_text())["state"]["ticks"] < 5:
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.01)
            (directory / "stop").touch()
            assert process.wait(timeout=5) == 0
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    final = json.loads((directory / "live-output.txt").read_text())
    assert final["ticks"] >= 5
    inspected = app.run(directory, dict(case.settings, REMINDER_MODE="inspect"))
    assert inspected.returncode == 0 and json.loads(inspected.stdout) == final
    return


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    trace = [99, 100, 145, 130, 150, 150, 1000, 1000, 999, 1000, 2000]
    case = fixture(directory / "basic")
    state, _events = run(app, case, trace[:6])
    assert [(r["emitted"], r["skipped"], r["next"]) for r in state["records"]] == [
        (6, 0, 160),
        (3, 3, 160),
        (2, 4, 160),
    ]
    state, _events = run(app, case, trace[6:], state)
    whole, _events = run(app, fixture(directory / "whole"), trace)
    assert state == whole
    rng = random.Random(81081)
    reminders = [
        dict(row, id="rem" + str(i), start=rng.randrange(100), every=rng.randrange(1, 35))
        for i, row in enumerate(policies() * 4)
    ]
    generated = [rng.randrange(2500) for _ in range(120)]
    generated_case = fixture(directory / "generated", reminders)
    generated_state = None
    for start in range(0, len(generated), 15):
        generated_state, _events = run(app, generated_case, generated[start : start + 15], generated_state)
    assert len(generated_state["history"]) == 256
    maximum = [
        dict(row, id="maximum" + str(i), start=0, every=1, message="😀" * 64)
        for i, row in enumerate((policies() * 11)[:32])
    ]
    capacity_app = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    capacity, _events = run(capacity_app, fixture(directory / "capacity", maximum), [4102444799, 0])
    assert len(capacity["history"]) == 256
    zero, _events = run(app, fixture(directory / "empty"), [])
    assert zero["clock"] == -1 and zero["ticks"] == 0
    boundary, _events = run(
        app, fixture(directory / "last-second", policies(4102444799, 31536000)), [4102444798, 4102444799]
    )
    assert all(row["next"] == 4133980799 for row in boundary["records"])
    leap = int(dt.datetime(2024, 2, 29, tzinfo=dt.timezone.utc).timestamp())
    run(app, fixture(directory / "leap", policies(leap, 86400)), [leap, leap + 86400])
    invalid = invalid_inputs(app, directory / "invalid")
    corrupt = corrupt_states(app, directory / "corrupt")
    fault_count = faults(app, directory / "faults")
    killed = killed_processes(app, directory / "killed")
    live_clock(app, directory / "live")
    return {
        "missed_run_policies": 3,
        "generated_clock_ticks": 120,
        "generated_reminders": 12,
        "restart_segments": 8,
        "clock_rollback_high_water_mark": True,
        "bounded_catch_up_without_lost_occurrences": True,
        "retained_history": 256,
        "invalid_inputs_without_state_writes": invalid,
        "corrupt_or_changed_state_rejected": corrupt,
        "fault_boundaries": fault_count,
        "killed_process_boundaries": killed,
        "concurrent_writer_exclusion": True,
        "live_clock_and_stop_file": True,
        "maximum_reminders": 32,
        "memory_limit": 268435456,
        "basic_state_sha256": hashlib.sha256(encoded(state)).hexdigest(),
        "generated_state_sha256": hashlib.sha256(encoded(generated_state)).hexdigest(),
        "capacity_state_sha256": hashlib.sha256(encoded(capacity)).hexdigest(),
    }
