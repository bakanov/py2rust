"""Real HTTP transitions checked against an independent event-history interval oracle."""

# ruff: noqa: PLR1711 - explicit repository returns
import contextlib
import copy
import hashlib
import http.client
import json
import os
import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from .common import Application, Server
from .csv_json import canonical


def envelope(state: dict) -> bytes:
    return (
        canonical({"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}) + "\n"
    ).encode()


@dataclass
class Fixture:
    directory: Path
    sessions: int = 32
    intervals: int = 32

    @property
    def store(self) -> Path:
        return self.directory / "state.json"

    def settings(self, **extra: str) -> dict:
        return {
            "TIMER_STATE": str(self.store),
            "TIMER_CLOCK": str(self.directory / "clock.json"),
            "TIMER_PORT": "0",
            "TIMER_SESSIONS": str(self.sessions),
            "TIMER_INTERVALS": str(self.intervals),
            "TIMER_FAULT": "",
            "TIMER_PAUSE": "",
            **extra,
        }

    def clock(self, wall: int, mono: int) -> None:
        temporary = self.directory / "clock.new"
        temporary.write_text(json.dumps({"wall_ms": wall, "mono_ms": mono}))
        temporary.replace(self.directory / "clock.json")
        return


def fixture(directory: Path, sessions: int = 32, intervals: int = 32) -> Fixture:
    directory.mkdir(parents=True)
    result = Fixture(directory, sessions, intervals)
    result.clock(1000000, 10000)
    return result


@dataclass
class Reference:
    capacity: int = 32
    interval_limit: int = 32
    clock: int = 0
    mono: int = 0
    history: dict[str, dict] = field(default_factory=dict)

    def rebase(self, wall: int, mono: int) -> None:
        self.clock, self.mono = max(self.clock, wall), mono
        return

    def record(self, key: str) -> dict:
        entry = self.history[key]
        events = entry["events"]
        intervals = []
        opened = None
        status = "running"
        for operation, moment in events:
            if operation in ["start", "resume"]:
                opened, status = moment, "running"
            else:
                if opened is not None:
                    intervals.append({"start_ms": opened, "end_ms": moment})
                opened, status = None, "paused" if operation == "pause" else "stopped"
        return {
            "name": entry["name"],
            "status": status,
            "created_ms": events[0][1],
            "updated_ms": events[-1][1],
            "open_ms": opened,
            "stopped_ms": events[-1][1] if status == "stopped" else None,
            "intervals": intervals,
            "total_ms": sum(row["end_ms"] - row["start_ms"] for row in intervals),
        }

    def state(self) -> dict:
        return {
            "version": 1,
            "clock_ms": self.clock,
            "mono_ms": self.mono,
            "sessions": {key: self.record(key) for key in self.history},
        }

    def view(self, key: str) -> dict:
        row = self.record(key)
        completed = row.pop("total_ms")
        active = 0 if row["open_ms"] is None else self.clock - row["open_ms"]
        return dict(
            row,
            id=key,
            completed_ms=completed,
            active_ms=active,
            elapsed_ms=completed + active,
            completed_seconds=completed / 1000,
            elapsed_seconds=(completed + active) / 1000,
        )

    def report(self) -> dict:
        rows = [self.view(key) for key in sorted(self.history)]
        names = sorted({row["name"] for row in rows})
        groups = []
        for name in names:
            matching = [row for row in rows if row["name"] == name]
            completed = sum(row["completed_ms"] for row in matching)
            elapsed = sum(row["elapsed_ms"] for row in matching)
            groups.append(
                {
                    "name": name,
                    "sessions": len(matching),
                    "completed_ms": completed,
                    "elapsed_ms": elapsed,
                    "completed_seconds": completed / 1000,
                    "elapsed_seconds": elapsed / 1000,
                }
            )
        completed = sum(row["completed_ms"] for row in rows)
        elapsed = sum(row["elapsed_ms"] for row in rows)
        return {
            "clock_ms": self.clock,
            "sessions": rows,
            "by_name": groups,
            "completed_ms": completed,
            "elapsed_ms": elapsed,
            "completed_seconds": completed / 1000,
            "elapsed_seconds": elapsed / 1000,
        }

    def apply(self, wall: int, mono: int, operation: str, key: str = "", name: str = "") -> tuple[int, dict]:
        row = self.record(key) if key in self.history else None
        if operation == "start":
            if row is not None:
                return 409, {"error": "session ID already exists"}
            if len(self.history) >= self.capacity:
                return 507, {"error": "session capacity reached"}
        elif operation not in ["report", "export"]:
            if row is None:
                return 404, {"error": "session does not exist"}
            valid = {"running": ["get", "pause", "stop"], "paused": ["get", "resume", "stop"], "stopped": ["get"]}
            if operation not in valid[row["status"]]:
                return 409, {"error": "illegal session transition"}
            if operation == "resume" and len(row["intervals"]) == self.interval_limit:
                return 507, {"error": "interval capacity reached"}
        assert mono >= self.mono
        self.clock = max(wall, self.clock + mono - self.mono)
        self.mono = mono
        if operation == "start":
            self.history[key] = {"name": name, "events": [(operation, self.clock)]}
        elif operation in ["pause", "resume", "stop"]:
            self.history[key]["events"].append((operation, self.clock))
        if operation in ["report", "export"]:
            return 200, self.report()
        return (201 if operation == "start" else 200), {"clock_ms": self.clock, "session": self.view(key)}


@contextlib.contextmanager
def running(app: Application, fix: Fixture, reference: Reference, **extra: str):
    sample = json.loads((fix.directory / "clock.json").read_text())
    reference.rebase(sample["wall_ms"], sample["mono_ms"])
    with app.server(fix.directory, fix.settings(**extra)) as server:
        assert fix.store.read_bytes() == envelope(reference.state())
        yield server
    return


def call(server: Server, operation: str, key: str = "", name: str = ""):
    if operation in ["report", "export"]:
        return server.request("GET", "/" + operation)
    if operation == "get":
        return server.request("GET", "/session?" + urlencode({"id": key}))
    body = {"id": key}
    if operation == "start":
        body["name"] = name
    return server.request("POST", "/" + operation, json.dumps(body, ensure_ascii=False).encode())


def step(
    fix: Fixture,
    reference: Reference,
    server: Server,
    wall: int,
    mono: int,
    operation: str,
    key: str = "",
    name: str = "",
) -> dict:
    fix.clock(wall, mono)
    code, expected = reference.apply(wall, mono, operation, key, name)
    response = call(server, operation, key, name)
    assert response.status == code and response.json() == expected, (
        operation,
        response.status,
        response.body,
        expected,
    )
    assert response.body == canonical(expected).encode()
    assert response.headers["content-type"] == "application/json" and response.headers["cache-control"] == "no-store"
    if operation == "export":
        assert response.headers["content-disposition"] == 'attachment; filename="activity.json"'
    assert fix.store.read_bytes() == envelope(reference.state())
    return {"status": code, "body": expected}


def exercise(app: Application, directory: Path) -> dict:
    fix, reference = fixture(directory / "traces"), Reference()
    observations = []
    with running(app, fix, reference) as server:
        for wall, mono, op, key, name in [
            (1000000, 10000, "start", "a", "Work 世界"),
            (1000000, 10000, "start", "b", "Work 世界"),
            (1000250, 10250, "pause", "a", ""),
            (900000, 10750, "get", "a", ""),
            (900000, 10750, "get", "b", ""),
            (1001000, 11000, "resume", "a", ""),
            (1002000, 12000, "pause", "b", ""),
            (1002250, 12250, "stop", "a", ""),
            (1002250, 12250, "start", "c", "Review"),
            (2000000, 20000, "pause", "a", ""),
            (2000000, 20000, "stop", "missing", ""),
            (1002250, 12250, "export", "", ""),
        ]:
            observations.append(step(fix, reference, server, wall, mono, op, key, name))
        assert reference.view("a")["completed_ms"] == 1500
        assert reference.view("b")["completed_ms"] == 2000
    fix.clock(1005000, 0)
    with running(app, fix, reference) as server:
        observations.append(step(fix, reference, server, 1005000, 0, "report"))
        assert reference.view("c")["active_ms"] == 2750 and reference.view("b")["active_ms"] == 0
        observations.append(step(fix, reference, server, 900000, 400, "stop", "c"))
        assert reference.view("c")["completed_ms"] == 3150
        observations.append(step(fix, reference, server, 900000, 400, "stop", "b"))
    rng = random.Random(83083)
    next_key = 0
    wall = 1006000
    for _restart in range(4):
        mono = 0
        fix.clock(wall, mono)
        with running(app, fix, reference) as server:
            for _ in range(70):
                wall += rng.choice([-2000, 0, 1, 50, 1000])
                mono += rng.choice([0, 1, 50, 500])
                active = [key for key in reference.history if reference.record(key)["status"] != "stopped"]
                key, name = "", ""
                if not active or rng.randrange(10) == 0:
                    op, key, name = (
                        "start",
                        "generated" + str(next_key),
                        rng.choice(["Work 世界", "Review", "é😀", "__proto__"]),
                    )
                    next_key += 1
                elif rng.randrange(5) == 0:
                    op = rng.choice(["report", "export"])
                else:
                    key = rng.choice(active)
                    status = reference.record(key)["status"]
                    op = rng.choice(["get", "pause" if status == "running" else "resume", "stop", "resume"])
                observations.append(step(fix, reference, server, wall, mono, op, key, name))
    return {
        "oracle_requests": len(observations),
        "trace_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
        "state_sha256": hashlib.sha256(fix.store.read_bytes()).hexdigest(),
    }


def invalid_requests(app: Application, directory: Path) -> int:
    fix, reference = fixture(directory / "invalid"), Reference()
    base = {"id": "x", "name": "Work"}
    invalid = [None, [], {}, dict(base, extra=1)]
    invalid += [dict(base, id=value) for value in [None, True, 1, "", "1x", "x" * 33, "é", "x/y"]]
    invalid += [dict(base, name=value) for value in [None, True, "", "😀" * 33, "x\n", "x\0"]]
    requests = [("POST", "/start", json.dumps(value).encode(), 400) for value in invalid]
    requests += [("POST", "/start", data, 400) for data in [b"{", b"\xff", b'{"id":"x","name":NaN}']]
    requests += [("POST", "/start", b"x" * 4097, 413), ("GET", "/missing", b"", 404)]
    requests += [("GET", "/" + op, b"", 405) for op in ["start", "pause", "resume", "stop"]]
    requests += [("POST", "/" + op, b"{}", 405) for op in ["session", "report", "export"]]
    requests += [
        ("GET", path, b"", 400)
        for path in ["/session", "/session?id=", "/session?id=a&extra=b", "/report?x=1", "/export?x=1"]
    ]
    requests += [
        ("GET", "/report", b"{}", 400),
        ("POST", "/pause", b'{"id":"a","name":"x"}', 400),
        ("POST", "/start?x=1", json.dumps(base).encode(), 400),
    ]
    with running(app, fix, reference) as server:
        step(fix, reference, server, 1000000, 10000, "start", "a", "Work")
        original = fix.store.read_bytes()
        fix.clock(1001000, 11000)
        for method, path, body, code in requests:
            response = server.request(method, path, body)
            assert response.status == code and fix.store.read_bytes() == original, (
                path,
                response.status,
                response.body,
            )
        clocks = [b"null", b"true", b"{}", b"\xff", b" " * 257]
        for change in [
            {"wall_ms": -1},
            {"wall_ms": True},
            {"wall_ms": 4102444800000},
            {"mono_ms": -1},
            {"mono_ms": 9000000000000001},
            {"mono_ms": 1.5},
            {"mono_ms": 9999},
            {"extra": 1},
        ]:
            clocks.append(json.dumps({"wall_ms": 1001000, "mono_ms": 11000} | change).encode())
        for value in clocks:
            (fix.directory / "clock.json").write_bytes(value)
            assert call(server, "get", "a").status == 500 and fix.store.read_bytes() == original
        step(fix, reference, server, 1001000, 11000, "stop", "a")
    return len(requests) + len(clocks)


def corruption(app: Application, directory: Path) -> int:
    fix, reference = fixture(directory / "corruption"), Reference()
    with running(app, fix, reference) as server:
        step(fix, reference, server, 1000000, 10000, "start", "a", "Work")
        step(fix, reference, server, 1001000, 11000, "pause", "a")
        step(fix, reference, server, 1002000, 12000, "resume", "a")
    original = reference.state()
    states = []
    for key, value in [
        ("version", True),
        ("version", 2),
        ("clock_ms", -1),
        ("clock_ms", 999),
        ("mono_ms", -1),
        ("mono_ms", True),
        ("sessions", []),
        ("extra", 1),
    ]:
        states.append(original | {key: value})
    for key, value in [
        ("name", ""),
        ("status", "unknown"),
        ("created_ms", -1),
        ("updated_ms", 1000999),
        ("open_ms", None),
        ("open_ms", 1001000),
        ("stopped_ms", 1002000),
        ("total_ms", 999),
        ("total_ms", True),
        ("intervals", []),
        ("extra", 1),
    ]:
        changed = copy.deepcopy(original)
        changed["sessions"]["a"][key] = value
        states.append(changed)
    for key, value in [("start_ms", 1000001), ("end_ms", 999999), ("end_ms", 1002001), ("end_ms", True), ("extra", 1)]:
        changed = copy.deepcopy(original)
        changed["sessions"]["a"]["intervals"][0][key] = value
        states.append(changed)
    changed = copy.deepcopy(original)
    changed["sessions"]["bad/id"] = changed["sessions"].pop("a")
    states.append(changed)
    raw = [envelope(value) for value in states] + [b"{", b"\xff", b"x" * 8388609, b'{"state":{},"sha256":"bad"}']
    for data in raw:
        fix.store.write_bytes(data)
        result = app.run(fix.directory, fix.settings())
        assert result.returncode == 2 and fix.store.read_bytes() == data, result
    fix.store.write_bytes(envelope(original))
    settings = [
        {name: value}
        for name, values in {
            "TIMER_PORT": ["-1", "65536", "true"],
            "TIMER_SESSIONS": ["0", "129"],
            "TIMER_INTERVALS": ["0", "257"],
            "TIMER_FAULT": ["unknown"],
            "TIMER_PAUSE": ["unknown"],
            "TIMER_CLOCK": [str(fix.store), str(fix.store) + ".lock"],
        }.items()
        for value in values
    ]
    for extra in settings:
        assert app.run(fix.directory, fix.settings(**extra)).returncode == 2
        assert fix.store.read_bytes() == envelope(original)
    target = fix.directory / "preserved"
    fix.store.rename(target)
    fix.store.symlink_to(target)
    assert app.run(fix.directory, fix.settings()).returncode == 2 and target.read_bytes() == envelope(original)
    fix.store.unlink()
    os.link(target, fix.store)
    assert app.run(fix.directory, fix.settings()).returncode == 2 and target.read_bytes() == envelope(original)
    fix.store.unlink()
    os.mkfifo(fix.store)
    assert app.run(fix.directory, fix.settings()).returncode == 2
    return len(raw) + len(settings) + 3


def boundaries(app: Application, directory: Path) -> dict:
    fix, reference = fixture(directory / "bounds", 2, 2), Reference(2, 2)
    fix.clock(0, 0)
    with running(app, fix, reference) as server:
        for moment, op, key, name in [
            (0, "start", "X" * 32, "😀" * 32),
            (0, "pause", "X" * 32, ""),
            (1, "resume", "X" * 32, ""),
            (3, "pause", "X" * 32, ""),
            (4, "resume", "X" * 32, ""),
            (5, "stop", "X" * 32, ""),
            (5, "start", "b", "😀" * 32),
            (5, "start", "overflow", "Work"),
        ]:
            step(fix, reference, server, moment, moment, op, key, name)
        assert reference.record("X" * 32)["total_ms"] == 2
        step(fix, reference, server, 4102444799999, 6, "pause", "b")
        original = fix.store.read_bytes()
        fix.clock(4102444799999, 7)
        assert call(server, "report").status == 500 and fix.store.read_bytes() == original
        step(fix, reference, server, 4102444799999, 6, "stop", "b")
    maximum = fixture(directory / "maximum", 128, 256)
    reference = Reference(128, 256, 2000, 0)
    for index in range(128):
        events = []
        for interval in range(256):
            events += [("start" if interval == 0 else "resume", interval * 4), ("pause", interval * 4 + 1)]
        reference.history["X" + str(index).zfill(31)] = {"name": "😀" * 32, "events": events}
    maximum.store.write_bytes(envelope(reference.state()))
    maximum.clock(2000, 0)
    bounded = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    with running(bounded, maximum, reference) as server:
        step(maximum, reference, server, 2000, 0, "export")
        step(maximum, reference, server, 2000, 0, "start", "overflow", "Work")
        step(maximum, reference, server, 2000, 0, "resume", "X" + "0" * 31)
        step(maximum, reference, server, 2000, 0, "stop", "X" + "0" * 31)
    assert reference.report()["completed_ms"] == 32768
    return {
        "sessions": 128,
        "intervals_per_session": 256,
        "intervals": 32768,
        "name_bytes": 128,
        "identifier_characters": 32,
        "memory_limit": 268435456,
        "state_sha256": hashlib.sha256(maximum.store.read_bytes()).hexdigest(),
    }


def wait_for(path: Path, pattern: str, process: subprocess.Popen) -> re.Match:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        match = re.search(pattern, path.read_text())
        if match:
            return match
        assert process.poll() is None, path.read_text()
        time.sleep(0.01)
    raise AssertionError("missing process event " + pattern)


def disconnected(server: Server, operation: str, key: str) -> None:
    try:
        call(server, operation, key)
    except (OSError, http.client.HTTPException):
        return
    raise AssertionError("killed request returned a response")


def publication(app: Application, directory: Path) -> int:
    for operation in ["pause", "report"]:
        for boundary in ["before_commit", "after_commit"]:
            for kind in ["fault", "kill"]:
                fix, reference = fixture(directory / f"{operation}-{boundary}-{kind}"), Reference()
                with running(app, fix, reference) as server:
                    step(fix, reference, server, 1000000, 10000, "start", "a", "Work")
                original = fix.store.read_bytes()
                future = copy.deepcopy(reference)
                future.apply(1001000, 11000, operation, "a")
                expected = original if boundary == "before_commit" else envelope(future.state())
                if kind == "fault":
                    with app.server(fix.directory, fix.settings(TIMER_FAULT=boundary)) as server:
                        fix.clock(1001000, 11000)
                        assert call(server, operation, "a").status == 500
                        assert server.process.poll() is None
                else:
                    log = fix.directory / "paused.log"
                    with log.open("w") as output:
                        process = subprocess.Popen(
                            app.command,
                            cwd=fix.directory,
                            env=app.environment(fix.settings(TIMER_PAUSE=boundary)),
                            stdout=output,
                            stderr=subprocess.STDOUT,
                        )
                        try:
                            match = wait_for(log, r"LISTENING http://127\.0\.0\.1:(\d+)", process)
                            server = Server(int(match[1]), process=process)
                            fix.clock(1001000, 11000)
                            with ThreadPoolExecutor(max_workers=1) as pool:
                                pending = pool.submit(disconnected, server, operation, "a")
                                try:
                                    wait_for(log, "PAUSED " + boundary, process)
                                    assert app.run(fix.directory, fix.settings()).returncode == 2
                                    assert fix.store.read_bytes() == expected
                                finally:
                                    process.kill()
                                    process.wait(timeout=5)
                                pending.result(timeout=5)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.wait(timeout=5)
                assert fix.store.read_bytes() == expected
                reference = reference if boundary == "before_commit" else future
                fix.clock(1001000, 0)
                with running(app, fix, reference) as server:
                    step(fix, reference, server, 1001000, 0, "get", "a")
                    status = "paused" if operation == "pause" and boundary == "after_commit" else "running"
                    assert reference.record("a")["status"] == status
    fix, reference = fixture(directory / "io-failures"), Reference()
    with running(app, fix, reference) as server:
        step(fix, reference, server, 1000000, 10000, "start", "a", "Work")
        original = fix.store.read_bytes()
        fix.clock(1001000, 11000)
        assert os.geteuid() != 0, "permission checks require a non-root user"
        fix.directory.chmod(0o555)
        try:
            assert call(server, "pause", "a").status == 500
            assert call(server, "report").status == 500
            assert fix.store.read_bytes() == original
        finally:
            fix.directory.chmod(0o755)
        step(fix, reference, server, 1001000, 11000, "get", "a")
        original = fix.store.read_bytes()
        fix.store.write_bytes(b"{")
        assert call(server, "report").status == 500 and fix.store.read_bytes() == b"{"
        fix.store.write_bytes(original)
        target = fix.directory / "preserved"
        fix.store.rename(target)
        fix.store.symlink_to(target)
        assert call(server, "stop", "a").status == 500
        assert target.read_bytes() == original and fix.store.is_symlink()
    return 12


def concurrent_and_real_clock(app: Application, directory: Path) -> int:
    fix, reference = fixture(directory / "concurrent"), Reference()
    with running(app, fix, reference) as server:
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda index: call(server, "start", "parallel" + str(index), "Work"), range(24)))
        assert all(response.status == 201 for response in responses)
        for index in range(24):
            reference.apply(1000000, 10000, "start", "parallel" + str(index), "Work")
        assert fix.store.read_bytes() == envelope(reference.state())
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _index: call(server, "start", "same", "Work"), range(8)))
        assert sorted(response.status for response in responses) == [201] + [409] * 7
        reference.apply(1000000, 10000, "start", "same", "Work")
        fix.clock(1001000, 11000)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _index: call(server, "pause", "same"), range(8)))
        assert sorted(response.status for response in responses) == [200] + [409] * 7
        reference.apply(1001000, 11000, "pause", "same")
        step(fix, reference, server, 1001000, 11000, "export")
    live = fixture(directory / "real-clock")
    with app.server(live.directory, live.settings(TIMER_CLOCK="")) as server:
        before = int(time.time() * 1000)
        started = call(server, "start", "live", "Real clock")
        after = int(time.time() * 1000)
        assert started.status == 201 and before <= started.json()["session"]["created_ms"] <= after + 3
        time.sleep(0.04)
        paused = call(server, "pause", "live")
        assert paused.status == 200
        time.sleep(0.06)
        resumed = call(server, "resume", "live")
        assert resumed.status == 200
        time.sleep(0.04)
        stopped = call(server, "stop", "live")
        assert stopped.status == 200
        row = stopped.json()["session"]
        assert len(row["intervals"]) == 2 and row["elapsed_ms"] >= 60
        pause_ms = resumed.json()["session"]["updated_ms"] - paused.json()["session"]["updated_ms"]
        assert pause_ms >= 50
        assert row["stopped_ms"] - row["created_ms"] - pause_ms == row["elapsed_ms"]
        assert row["elapsed_seconds"] == row["elapsed_ms"] / 1000
    with app.server(live.directory, live.settings(TIMER_CLOCK="")) as server:
        restored = call(server, "get", "live")
        assert restored.status == 200 and restored.json()["session"] == row
    return 40


def check(app: Application, directory: Path) -> dict:
    traces = exercise(app, directory)
    return {
        **traces,
        "invalid_requests_and_clocks": invalid_requests(app, directory),
        "corrupt_states_and_settings": corruption(app, directory),
        "capacity": boundaries(app, directory),
        "publication_checks": publication(app, directory),
        "concurrent_requests": concurrent_and_real_clock(app, directory),
        "real_monotonic_and_wall_clock": True,
        "paused_time_excluded": True,
        "active_downtime_included_on_restart": True,
        "independent_event_history_oracle": True,
    }
