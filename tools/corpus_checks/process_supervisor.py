"""Independent native launch/timing records, exact retained bytes and whole-group cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import queue
import resource
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .process_fixture import alive, gone, ready
from .supervisor_fixture import build_fixture


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def service(root: Path, helper: Path, name: str = "worker", mode: str = "flap", **changes: object) -> dict:
    row = {
        "id": name,
        "argv": [
            str(helper),
            mode,
            str(root / (name + ".launch")),
            str(root / (name + ".counter")),
            "37",
            "19",
            "0",
            "0",
        ],
        "cwd": ".",
        "environment": {},
        "restarts": 2,
        "backoff_ms": 30,
        "max_backoff_ms": 50,
        "log_bytes": 65536,
    }
    row.update(changes)
    return row


@dataclass
class Fixture:
    root: Path
    config: dict

    @property
    def source(self) -> Path:
        return self.root / "supervisor.json"

    @property
    def state(self) -> Path:
        return self.root / self.config["state"]

    @property
    def settings(self) -> dict[str, str]:
        return {"SUPERVISOR_CONFIG": str(self.source)}

    def save(self) -> None:
        self.source.write_bytes(canonical(self.config))
        return  # noqa: PLR1711 - explicit repository returns


def fixture(root: Path, helper: Path, **changes: object) -> Fixture:
    root.mkdir(parents=True)
    config = {
        "version": 1,
        "state": "session",
        "stop": "stop",
        "run_ms": 5000,
        "grace_ms": 100,
        "services": [service(root, helper)],
    }
    config.update(changes)
    fix = Fixture(root, config)
    fix.save()
    return fix


def events(fix: Fixture, name: str) -> list[tuple[str, int, int, int, int]]:
    path = fix.root / (name + ".launch")
    if not path.exists():
        return []
    return [
        (kind, int(pid), int(attempt), int(stamp), int(code))
        for kind, pid, attempt, stamp, code in [line.split() for line in path.read_text().splitlines()]
    ]


def report(fix: Fixture) -> dict:
    doc = json.loads((fix.state / "status.json").read_bytes())
    assert set(doc) == {"version", "phase", "reason", "elapsed_ms", "interrupt_signal", "services"}
    assert doc["version"] == 1 and doc["phase"] == "finished"
    assert 0 <= doc["elapsed_ms"] <= fix.config["run_ms"] + fix.config["grace_ms"] + 3000
    assert [row["id"] for row in doc["services"]] == sorted(spec["id"] for spec in fix.config["services"])
    expected_files = {"status.json"}
    specs = {spec["id"]: spec for spec in fix.config["services"]}
    for row in doc["services"]:
        assert set(row) == {
            "id",
            "state",
            "pid",
            "attempts",
            "next_ms",
            "returncode",
            "error",
            "history",
            "stdout",
            "stderr",
        }
        name, spec = row["id"], specs[row["id"]]
        assert row["pid"] == 0 and row["state"] in ["exited", "failed", "stopped"]
        assert row["attempts"] == len(row["history"]) <= spec["restarts"] + 1
        starts = [event for event in events(fix, name) if event[0] == "start"]
        assert all(not alive(event[1]) for event in starts), "managed leader survived shutdown"
        ends = [event for event in events(fix, name) if event[0] == "end"]
        spawned = [item for item in row["history"] if item["kind"] != "spawn_error"]
        assert len(starts) == len(spawned), (name, starts, row)
        for index, item in enumerate(row["history"]):
            assert set(item) == {"attempt", "started_ms", "ended_ms", "kind", "returncode", "delay_ms"}
            assert item["attempt"] == index + 1
            assert 0 <= item["started_ms"] <= item["ended_ms"] <= doc["elapsed_ms"]
            if index + 1 < len(row["history"]):
                delay = min(spec["backoff_ms"] * 2**index, spec["max_backoff_ms"])
                assert item["delay_ms"] == delay
                assert row["history"][index + 1]["started_ms"] - item["ended_ms"] >= delay
        for index in range(1, len(starts)):
            prior = next(event for event in ends if event[2] == starts[index - 1][2])
            delay = min(spec["backoff_ms"] * 2 ** (index - 1), spec["max_backoff_ms"])
            assert starts[index][3] - prior[3] >= (delay - 2) * 1000000
        for stream in ["stdout", "stderr"]:
            details = row[stream]
            assert set(details) == {"file", "bytes", "seen", "discarded", "sha256"}
            assert details["file"] == name + "." + stream
            path = fix.state / details["file"]
            data = path.read_bytes()
            assert details["bytes"] == len(data) <= spec["log_bytes"]
            assert details["seen"] == len(data) + details["discarded"] and details["discarded"] >= 0
            assert details["sha256"] == digest(data)
            expected_files.add(details["file"])
        pids = fix.root / (name + ".launch.pids")
        if pids.exists():
            gone(pids, minimum=2)
    assert {path.name for path in fix.state.iterdir()} == expected_files
    return doc


def exact_logs(fix: Fixture, name: str, attempts: int, out: int, err: int) -> None:
    spec = next(row for row in fix.config["services"] if row["id"] == name)
    doc = report(fix)
    row = next(item for item in doc["services"] if item["id"] == name)
    for stream, data in [
        ("stdout", b"".join(bytes([i + 1]) * out for i in range(attempts))),
        ("stderr", b"e" * err * attempts),
    ]:
        assert (fix.state / (name + "." + stream)).read_bytes() == data[: spec["log_bytes"]]
        assert row[stream]["seen"] == len(data)
    return  # noqa: PLR1711 - explicit repository returns


def run(app: Application, fix: Fixture, code: int = 0, memory: int = 0, **settings: str) -> dict:
    def memory_limit() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        return  # noqa: PLR1711 - explicit repository returns

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, **settings)),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        preexec_fn=memory_limit if memory else None,
    )
    assert result.returncode == code and not result.stdout and not result.stderr, result
    return report(fix)


def semantics(app: Application, root: Path, helper: Path) -> dict:
    fix = fixture(root / "mixed", helper)
    a = service(fix.root, helper, "recover", restarts=3)
    a["argv"][7] = "2"
    b = service(fix.root, helper, "exhaust", restarts=3)
    b["argv"][7] = "99"
    c = service(fix.root, helper, "slow")
    c["argv"][6] = "350"
    fix.config["services"] = [c, a, b]
    fix.save()
    doc = run(app, fix, 1)
    assert doc["reason"] == "completed"
    assert [(row["id"], row["state"], row["attempts"]) for row in doc["services"]] == [
        ("exhaust", "failed", 4),
        ("recover", "exited", 3),
        ("slow", "exited", 1),
    ]
    for name, count in [("exhaust", 4), ("recover", 3), ("slow", 1)]:
        exact_logs(fix, name, count, 37, 19)
    first_end = next(row[3] for row in events(fix, "slow") if row[0] == "end")
    assert events(fix, "recover")[0][3] < first_end and events(fix, "exhaust")[0][3] < first_end
    missing = fixture(root / "spawn-error", helper)
    missing.config["services"][0]["argv"][0] = str(missing.root / "missing")
    missing.save()
    doc = run(app, missing, 1)
    assert doc["services"][0]["attempts"] == 3 and doc["services"][0]["error"] == "process pool spawn failed"
    assert all(item["kind"] == "spawn_error" for item in doc["services"][0]["history"])
    binary = fixture(root / "binary", helper)
    binary.config["services"][0]["argv"][4:6] = ["131073", "65537"]
    binary.save()
    run(app, binary)
    exact_logs(binary, "worker", 1, 131073, 65537)
    empty = fixture(root / "empty", helper, services=[])
    assert run(app, empty)["services"] == []
    stopped = fixture(root / "pre-stopped", helper)
    (stopped.root / "stop").touch()
    doc = run(app, stopped)
    assert doc["reason"] == "stop_file" and doc["services"][0]["attempts"] == 0
    return {
        "mixed_attempts": 8,
        "successful_recovery_attempts": 3,
        "exhausted_attempts": 4,
        "spawn_error_attempts": 3,
        "concurrent_launches_verified": True,
        "actual_backoff_timestamps_checked": True,
        "binary_stdout_bytes": 131073,
        "binary_stderr_bytes": 65537,
        "empty_and_pre_stopped": True,
    }


def start_process(app: Application, fix: Fixture, **settings: str) -> subprocess.Popen:
    return subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, **settings)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def await_state(fix: Fixture, process: subprocess.Popen, state: str, name: str = "worker") -> dict:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        assert process.poll() is None, process.communicate()
        path = fix.state / "status.json"
        if path.exists():
            doc = json.loads(path.read_bytes())
            if any(row["id"] == name and row["state"] == state for row in doc["services"]):
                return doc
        time.sleep(0.005)
    raise AssertionError("state deadline: " + state)


def finish(process: subprocess.Popen, code: int = 0) -> None:
    output, error = process.communicate(timeout=8)
    assert process.returncode == code and not output and not error, (process.returncode, output, error)
    return  # noqa: PLR1711 - explicit repository returns


def cleanup(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
    return  # noqa: PLR1711 - explicit repository returns


def shutdown(app: Application, root: Path, helper: Path) -> dict:
    for mode in ["hold", "term", "closed", "orphan"]:
        fix = fixture(root / mode, helper, run_ms=300, grace_ms=120)
        fix.config["services"][0]["argv"][1] = mode
        fix.save()
        doc = run(app, fix)
        row = doc["services"][0]
        assert doc["reason"] == ("completed" if mode == "orphan" else "deadline")
        assert row["attempts"] == 1 and row["returncode"] == (0 if mode in ["term", "orphan"] else -9)
        if mode == "term":
            assert doc["elapsed_ms"] < 1000
        exact_logs(fix, "worker", 1, 0 if mode == "closed" else 37, 0 if mode == "closed" else 19)
    flood = fixture(root / "flood", helper, run_ms=600)
    row = service(flood.root, helper, "flood", "flood", log_bytes=1024)
    peer = service(flood.root, helper, "peer")
    peer["argv"][7] = "1"
    flood.config["services"] = [row, peer]
    flood.save()
    doc = run(app, flood)
    assert doc["services"][1]["state"] == "exited" and doc["services"][1]["attempts"] == 2
    for stream, value in [("stdout", b"\1"), ("stderr", b"e")]:
        assert (flood.state / ("flood." + stream)).read_bytes() == value * 1024
        assert doc["services"][0][stream]["discarded"] > 0
    for how in ["stop", "int", "term", "backoff"]:
        fix = fixture(root / ("external-" + how), helper, run_ms=10000)
        row = fix.config["services"][0]
        row["argv"][1] = "hold"
        if how == "backoff":
            row["argv"][1], row["argv"][7] = "flap", "99"
            row["backoff_ms"] = row["max_backoff_ms"] = 5000
        fix.save()
        process = start_process(app, fix)
        try:
            if how == "backoff":
                await_state(fix, process, "backoff")
            else:
                ready(fix.root / "worker.launch.pids", process)
                await_state(fix, process, "running")
            number = signal.SIGINT if how == "int" else (signal.SIGTERM if how == "term" else 0)
            if number:
                process.send_signal(number)
            else:
                (fix.root / "stop").touch()
            finish(process, 128 + number if number else 0)
            doc = report(fix)
            assert doc["interrupt_signal"] == number and doc["services"][0]["attempts"] == 1
            assert doc["reason"] == ("signal" if number else "stop_file")
        finally:
            cleanup(process)
    return {
        "shutdown_cases": 9,
        "parent_signals": [2, 15],
        "term_then_kill": True,
        "native_descendants_gone": True,
        "orphan_pipe_cleanup": True,
        "flood_does_not_starve_restarts": True,
        "backoff_cancelled_without_restart": True,
    }


def rejected(app: Application, fix: Fixture) -> None:
    result = app.run(fix.root, fix.settings, timeout=10)
    assert result.returncode == 2 and result.stderr and not list(fix.root.glob("*.launch")), result
    return  # noqa: PLR1711 - explicit repository returns


def invalid(app: Application, root: Path, helper: Path) -> dict:
    changes = [
        ("id", ""),
        ("id", "1bad"),
        ("id", "A" * 33),
        ("argv", []),
        ("argv", ["x"] * 65),
        ("argv", ["/bin/true", "x" * 1025]),
        ("argv", ["/bin/true", "\0"]),
        ("argv", [1]),
        ("cwd", "missing"),
        ("environment", []),
        ("environment", {"0BAD": "x"}),
        ("environment", {"A": "\0"}),
        ("environment", {"A": 1}),
        ("environment", {"A": "x" * 16382}),
        ("environment", {"A" * 129: "x"}),
        ("environment", {"K" + str(i): "" for i in range(33)}),
        ("restarts", -1),
        ("restarts", 9),
        ("restarts", True),
        ("restarts", 1.0),
        ("log_bytes", -1),
        ("log_bytes", 65537),
        ("log_bytes", False),
        ("backoff_ms", 0),
        ("backoff_ms", 10001),
        ("max_backoff_ms", 20),
        ("max_backoff_ms", 10001),
    ]
    invalid_fields = len(changes)
    for index, (key, value) in enumerate(changes):
        fix = fixture(root / f"field-{index}", helper)
        fix.config["services"][0][key] = value
        fix.save()
        rejected(app, fix)
    changes = [
        ("version", True),
        ("version", 2),
        ("run_ms", 0),
        ("run_ms", 60001),
        ("run_ms", True),
        ("grace_ms", -1),
        ("grace_ms", 2001),
        ("grace_ms", 1.0),
        ("state", "../escape"),
        ("state", "supervisor.json"),
        ("stop", "session"),
        ("stop", "session.lock"),
        ("stop", "supervisor.json"),
        ("services", {}),
        ("extra", 1),
    ]
    for index, (key, value) in enumerate(changes):
        fix = fixture(root / f"suite-{index}", helper)
        fix.config[key] = value
        fix.save()
        rejected(app, fix)
    for index in range(3):
        fix = fixture(root / f"services-{index}", helper)
        if index == 0:
            fix.config["services"] = [service(fix.root, helper, "s" + str(i)) for i in range(9)]
        elif index == 1:
            fix.config["services"] *= 2
        else:
            fix.config["services"][0]["extra"] = 1
        fix.save()
        rejected(app, fix)
    for index, data in enumerate([b"", b"{", b"[]", b"\xff", b'{"version":1,"version":1}']):
        fix = fixture(root / f"json-{index}", helper)
        fix.source.write_bytes(data)
        rejected(app, fix)
    return {
        "invalid_service_fields": invalid_fields,
        "invalid_suites": 15,
        "invalid_service_lists": 3,
        "malformed_json": 5,
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, SUPERVISOR_PAUSE=label, SUPERVISOR_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    messages: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
        return  # noqa: PLR1711 - explicit repository returns

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = messages.get(timeout=15)
            assert line is not None, "exited before pause " + label
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, root: Path, helper: Path) -> dict:
    for label in ["staged:running", "committed:running", "staged:finished", "committed:finished"]:
        fix = fixture(root / label.replace(":", "-"), helper)
        process = paused(app, fix, label)
        process.kill()
        assert process.wait(timeout=5) < 0
        if "running" in label:
            assert not events(fix, "worker")
        else:
            assert len([item for item in events(fix, "worker") if item[0] == "end"]) == 1
        if label == "committed:finished":
            report(fix)
        result = app.run(fix.root, fix.settings)
        assert result.returncode == 2 and "session directory already exists" in result.stderr
    for change in ["configuration", "staging", "permission", "contenders"]:
        fix = fixture(root / change, helper, run_ms=10000)
        fix.config["services"][0]["argv"][1] = "hold"
        fix.save()
        label = "staged:running" if change == "staging" else "cycle"
        process = paused(app, fix, label)
        try:
            if change != "staging":
                ready(fix.root / "worker.launch.pids", process)
            if change == "configuration":
                with fix.source.open("ab") as stream:
                    stream.write(b" ")
            elif change == "staging":
                with (fix.state / "status.tmp").open("ab") as stream:
                    stream.write(b" ")
            elif change == "permission":
                fix.state.chmod(0o500)
            else:
                for _ in range(8):
                    result = app.run(fix.root, fix.settings)
                    assert result.returncode == 2 and result.stderr
                assert len(events(fix, "worker")) == 1
                (fix.root / "stop").touch()
            (fix.root / "release").touch()
            assert process.wait(timeout=10) == (0 if change == "contenders" else 2)
            if change != "staging":
                gone(fix.root / "worker.launch.pids", minimum=2)
        finally:
            fix.state.chmod(0o700)
            (fix.root / "release").touch()
            cleanup(process)
    return {
        "actual_kill_boundaries_without_live_children": 4,
        "changed_config_or_staging_rejected": 2,
        "permission_error_cleans_children": True,
        "competing_supervisors_rejected": 8,
    }


def filesystem(app: Application, root: Path, helper: Path) -> dict:
    names = [
        "config-symlink",
        "config-hardlink",
        "config-fifo",
        "lock-symlink",
        "lock-hardlink",
        "stop-symlink",
        "stop-hardlink",
        "stop-fifo",
        "state-symlink",
        "state-file",
        "state-directory",
    ]
    for name in names:
        fix = fixture(root / name, helper)
        other = fix.root / "untouched"
        other.write_bytes(fix.source.read_bytes() if name.startswith("config") else b"keep")
        before = other.read_bytes()
        path = (
            fix.source
            if name.startswith("config")
            else fix.root
            / ("session.lock" if name.startswith("lock") else ("stop" if name.startswith("stop") else "session"))
        )
        if path.exists():
            path.unlink()
        if name.endswith("symlink"):
            path.symlink_to(other)
        elif name.endswith("hardlink"):
            os.link(other, path)
        elif name.endswith("fifo"):
            os.mkfifo(path)
        elif name.endswith("directory"):
            path.mkdir()
            (path / "unrelated").write_bytes(b"preserve")
        else:
            path.write_bytes(b"preserve")
        rejected(app, fix)
        assert other.read_bytes() == before
    return {"alias_and_control_cases": len(names)}


def limits(app: Application, root: Path, helper: Path) -> dict:
    fix = fixture(root / "maximum", helper, run_ms=60000, grace_ms=2000)
    rows = [service(fix.root, helper, "S" + str(i), restarts=8, backoff_ms=1, max_backoff_ms=2) for i in range(8)]
    for row in rows:
        row["argv"][4:8] = ["8193", "8193", "0", "8"]
    rows[0]["argv"] += ["x" * 1024] * 56
    rows[0]["environment"] = {"K" + str(i): "x" for i in range(31)} | {"K" * 128: ""}
    size = sum(len(key) + len(value) + 2 for key, value in rows[0]["environment"].items())
    rows[0]["environment"]["K" * 128] = "v" * (16384 - size)
    fix.config["services"] = rows
    fix.save()
    fix.source.write_bytes(fix.source.read_bytes().ljust(262144, b" "))
    doc = run(app, fix, memory=268435456)
    assert all(row["attempts"] == 9 and row["state"] == "exited" for row in doc["services"])
    for spec in rows:
        exact_logs(fix, spec["id"], 9, 8193, 8193)
    over = fixture(root / "config-over", helper)
    over.source.write_bytes(over.source.read_bytes().ljust(262145, b" "))
    rejected(app, over)
    return {
        "services": 8,
        "attempts_per_service": 9,
        "actual_launches": 72,
        "arguments": 64,
        "argument_bytes": 1024,
        "environment_variables": 32,
        "environment_bytes": 16384,
        "configuration_bytes": 262144,
        "retained_bytes_per_stream": 65536,
        "total_retained_bytes": 1048576,
        "memory_limit": 268435456,
        "run_ms": 60000,
        "grace_ms": 2000,
    }


def check(app: Application, directory: Path) -> dict:
    helper = build_fixture(directory)
    return {
        "semantics": semantics(app, directory / "semantics", helper),
        "shutdown": shutdown(app, directory / "shutdown", helper),
        "invalid": invalid(app, directory / "invalid", helper),
        "publication": publication(app, directory / "publication", helper),
        "filesystem": filesystem(app, directory / "filesystem", helper),
        "limits": limits(app, directory / "limits", helper),
        "independent_native_launch_timing_and_capture_oracle": True,
    }
