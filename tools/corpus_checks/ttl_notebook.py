"""An independent record-list oracle checks HTTP expiration and durable state transitions."""

from __future__ import annotations

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
class Notebook:
    work: Path
    limits: dict[str, str] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return self.work / "state.json"

    def settings(self, **extra: str) -> dict:
        return {
            "TTL_STATE": str(self.path),
            "TTL_PORT": "0",
            "TTL_CLOCK": str(self.work / "clock.json"),
            "TTL_KEYS": "8",
            "TTL_VALUE_BYTES": "16384",
            "TTL_STATE_BYTES": "8388608",
            "TTL_FAULT": "",
            "TTL_PAUSE": "",
            **self.limits,
            **extra,
        }

    def clock(self, now: float) -> None:
        temporary = self.work / "clock.new"
        temporary.write_text(canonical(float(now)))
        temporary.replace(self.work / "clock.json")
        return  # noqa: PLR1711


def fixture(directory: Path, name: str, **limits: str) -> Notebook:
    work = directory / name
    work.mkdir(parents=True)
    fix = Notebook(work, limits)
    fix.clock(1000.0)
    return fix


@dataclass
class Reference:
    capacity: int = 8
    clock: float = 0.0
    records: list[dict] = field(default_factory=list)

    def state(self) -> dict:
        return {
            "version": 1,
            "clock": self.clock,
            "entries": {row["key"]: {k: v for k, v in row.items() if k != "key"} for row in self.records},
        }

    def apply(self, now: float, op: str, **args: object) -> tuple[int, dict]:
        moment = max(self.clock, float(now))
        # Deliberately derive deadlines from original write time and duration,
        # and retain physical rows independently from the live view.
        current = [row for row in self.records if row["written"] + row["ttl"] > moment]
        match = next((row for row in current if row["key"] == args.get("key")), None)
        result: dict = {"clock": moment}
        status = 200
        if op == "put":
            if match is None and len(current) == self.capacity:
                return 507, {"error": "live key storage is full"}
            row = {
                "key": args["key"],
                "value": copy.deepcopy(args["value"]),
                "written": moment,
                "ttl": args["ttl"],
                "expires": moment + args["ttl"],
            }
            self.records = [item for item in current if item["key"] != args["key"]] + [row]
            result["entry"] = row
            status = 200 if match else 201
        elif op == "get":
            if match:
                result["entry"] = match
            else:
                status = 404
                result["error"] = "key is absent or expired"
        elif op == "delete":
            result["deleted"] = match is not None
            self.records = [row for row in self.records if row["key"] != args["key"]]
        elif op == "sweep":
            result["removed"] = len(self.records) - len(current)
            self.records = current
        else:
            matches = sorted(
                [row for row in current if row["key"].startswith(args.get("prefix", ""))], key=lambda row: row["key"]
            )
            start, end = args.get("offset", 0), args.get("offset", 0) + args.get("limit", 100)
            result.update(entries=matches[start:end], count=len(matches), more=end < len(matches))
        self.clock = moment
        return status, copy.deepcopy(result)


def call(server: Server, op: str, **args: object):
    if op == "put":
        return server.request("PUT", "/entry", json.dumps(args, ensure_ascii=False).encode())
    if op in {"get", "delete"}:
        return server.request("GET" if op == "get" else "DELETE", "/entry?" + urlencode(args))
    if op == "sweep":
        return server.request("POST", "/sweep")
    return server.request("GET", "/entries?" + urlencode(args))


def step(fix: Notebook, reference: Reference, server: Server, now: float, op: str, **args: object) -> dict:
    fix.clock(now)
    expected_status, expected = reference.apply(now, op, **args)
    response = call(server, op, **args)
    assert response.status == expected_status, (op, args, response.status, response.body, expected_status)
    assert response.json() == expected, (op, args, response.json(), expected)
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"] == "application/json"
    assert fix.path.read_bytes() == envelope(reference.state()), (op, fix.path.read_text(), reference.state())
    return {"status": response.status, "body": response.json()}


def exercise(app: Application, directory: Path) -> tuple[int, str]:
    fix, reference = fixture(directory, "traces"), Reference()
    observations = []
    unicode_key = "Заметки/世界? 😀"
    with app.server(fix.work, fix.settings()) as server:
        observations.append(step(fix, reference, server, 1000.0, "put", key=unicode_key, value=None, ttl=10))
        observations.append(step(fix, reference, server, 1000.0, "get", key=unicode_key))
        observations.append(step(fix, reference, server, 1000.0, "get", key="absent"))
        observations.append(step(fix, reference, server, 1009.9999999999999, "get", key=unicode_key))
        observations.append(
            step(fix, reference, server, 1009.0, "put", key=unicode_key, value={"new": [1, True, None]}, ttl=20)
        )
    # The replacement gets the retained high-water time, even while the source clock rolls back.
    with app.server(fix.work, fix.settings()) as server:
        observations.append(step(fix, reference, server, 1010.0, "get", key=unicode_key))
        deadline = reference.records[0]["expires"]
        observations.append(step(fix, reference, server, deadline, "get", key=unicode_key))
        observations.append(step(fix, reference, server, deadline, "list"))
        assert len(reference.records) == 1  # Reads filter expiration without an implicit sweep.
    with app.server(fix.work, fix.settings()) as server:
        observations.append(step(fix, reference, server, 900.0, "get", key=unicode_key))
        observations.append(step(fix, reference, server, 900.0, "sweep"))
        observations.append(step(fix, reference, server, 900.0, "sweep"))
        observations.append(step(fix, reference, server, 900.0, "put", key=unicode_key, value=False, ttl=1))
        observations.append(step(fix, reference, server, reference.clock + 1.0, "delete", key=unicode_key))
    rng = random.Random(52007)
    values = [None, False, 0, -1, 1.5, -0.0, "é😀\n", [], {}, {"nested": [True, None, {"n": 2**63 - 1}]}]
    keys = ["k" + str(index) for index in range(12)] + [unicode_key, "\x00", "😀" * 32, "a&b=c+#"]
    now = 1100.0
    for _restart in range(4):
        with app.server(fix.work, fix.settings()) as server:
            for _index in range(160):
                now += rng.choice([-2.0, 0.0, 0.01, 0.5, 1.0, 8.0])
                op = rng.choices(["put", "get", "delete", "sweep", "list"], [6, 4, 2, 1, 2])[0]
                args = {}
                if op in {"put", "get", "delete"}:
                    args["key"] = rng.choice(keys)
                if op == "put":
                    args.update(value=rng.choice(values), ttl=rng.choice([1, 2, 10, 100, 86400]))
                elif op == "list":
                    args.update(prefix=rng.choice(["", "k", "Заметки", "missing"]), offset=rng.randrange(5), limit=3)
                observations.append(step(fix, reference, server, now, op, **args))
    return len(observations), hashlib.sha256(canonical(observations).encode()).hexdigest()


def invalid_requests(app: Application, directory: Path) -> int:
    fix = fixture(directory, "invalid-requests")
    good = {"key": "key", "value": None, "ttl": 10}
    nested = None
    for _level in range(17):
        nested = [nested]
    invalid = [None, [], {}, {**good, "extra": 0}]
    invalid += [{**good, "key": value} for value in [None, True, 1, "", "😀" * 33]]
    invalid += [{**good, "ttl": value} for value in [None, True, 0, -1, 86401, 1.5, "2"]]
    invalid += [{**good, "value": value} for value in [nested, "😀" * 4096, 2**63]]
    requests = [("PUT", "/entry", json.dumps(value).encode(), 400) for value in invalid]
    requests += [("PUT", "/entry", value, 400) for value in [b"{", b"\xff", b'{"key":"x","ttl":2,"value":NaN}']]
    requests += [("PUT", "/entry", b"x" * (16384 * 6 + 4097), 413)]
    requests += [
        ("GET", path, b"", 400)
        for path in [
            "/entry",
            "/entry?key=",
            "/entry?key=x&unexpected=y",
            "/entries?limit=0",
            "/entries?limit=257",
            "/entries?limit=true",
            "/entries?limit=1.5",
            "/entries?offset=-1",
            "/entries?offset=257",
            "/entries?offset=null",
            "/entries?unexpected=x",
            "/entries?" + urlencode({"prefix": "😀" * 33}),
        ]
    ]
    requests += [("GET", "/entries", b"{}", 400), ("POST", "/sweep?key=x", b"", 400)]
    requests += [("POST", "/entry", b"", 405), ("PUT", "/entries", b"{}", 405), ("GET", "/sweep", b"", 405)]
    requests += [("GET", "/unknown", b"", 404), ("PUT", "/entry?key=x", json.dumps(good).encode(), 400)]
    with app.server(fix.work, fix.settings()) as server:
        assert call(server, "put", **good).status == 201
        before = fix.path.read_bytes()
        fix.clock(2000.0)
        for method, path, body, status in requests:
            response = server.request(method, path, body)
            assert response.status == status, (method, path, body[:100], response.status, response.body)
            assert fix.path.read_bytes() == before
        # A bad clock fails a valid read rather than silently using zero or returning stale data.
        bad_clocks = [b"null", b"true", b"-1", b"253402214401", b"NaN", b"\xff", b"0" * 129]
        for content in bad_clocks:
            (fix.work / "clock.json").write_bytes(content)
            assert call(server, "get", key="key").status == 500
            assert fix.path.read_bytes() == before
        fix.clock(2000.0)
        assert call(server, "get", key="key").status == 404
    return len(requests) + len(bad_clocks)


def recovery_validation(app: Application, directory: Path) -> int:
    fix = fixture(directory, "corruption")
    with app.server(fix.work, fix.settings()) as server:
        assert call(server, "put", key="key", value={"a": None}, ttl=10).status == 201
    original = json.loads(fix.path.read_bytes())["state"]
    cases = []
    for field_name, value in [
        ("version", 2),
        ("version", True),
        ("clock", -1),
        ("clock", True),
        ("clock", 999),
        ("clock", 253402214401),
        ("entries", []),
        ("entries", None),
    ]:
        cases.append({**original, field_name: value})
    for field_name, value in [
        ("written", -1),
        ("written", 1001),
        ("written", None),
        ("ttl", 0),
        ("ttl", True),
        ("ttl", 86401),
        ("expires", 1009),
        ("expires", None),
        ("value", "x" * 16383),
    ]:
        bad = copy.deepcopy(original)
        bad["entries"]["key"][field_name] = value
        cases.append(bad)
    for bad_key in ["", "😀" * 33]:
        cases.append({**original, "entries": {bad_key: original["entries"]["key"]}})
    for target in ["root", "entry"]:
        for change in ["missing", "extra"]:
            bad = copy.deepcopy(original)
            obj = bad if target == "root" else bad["entries"]["key"]
            if change == "missing":
                obj.pop(next(iter(obj)))
            else:
                obj["extra"] = None
            cases.append(bad)
    cases.append({**original, "entries": {str(i): original["entries"]["key"] for i in range(9)}})
    data_cases = [envelope(value) for value in cases]
    data_cases += [b"{", b"\xff", b"[]", b"null", b"{}", b'{"state":{},"sha256":"bad"}']
    bad_digest = json.loads(envelope(original))
    bad_digest["state"]["entries"]["key"]["value"] = "tampered"
    data_cases.append(json.dumps(bad_digest).encode())
    for data in data_cases:
        fix.path.write_bytes(data)
        result = app.run(fix.work, fix.settings())
        assert result.returncode != 0, data[:200]
        assert fix.path.read_bytes() == data
    fix.path.write_bytes(envelope(original))
    settings_cases = [
        {name: value}
        for name, values in {
            "TTL_PORT": ["-1", "65536", "true"],
            "TTL_KEYS": ["0", "257"],
            "TTL_VALUE_BYTES": ["1", "16385"],
            "TTL_STATE_BYTES": ["255", "16777217"],
            "TTL_FAULT": ["unknown"],
            "TTL_PAUSE": ["unknown"],
            "TTL_CLOCK": [str(fix.path), str(fix.path) + ".lock"],
        }.items()
        for value in values
    ]
    for extra in settings_cases:
        assert app.run(fix.work, fix.settings(**extra)).returncode != 0, extra
        assert fix.path.read_bytes() == envelope(original)
    target = fix.work / "untouched"
    fix.path.rename(target)
    fix.path.symlink_to(target)
    assert app.run(fix.work, fix.settings()).returncode != 0
    assert target.read_bytes() == envelope(original)
    fix.path.unlink()
    fix.path.mkdir()
    assert app.run(fix.work, fix.settings()).returncode != 0
    fix.path.rmdir()
    os.mkfifo(fix.path)
    assert app.run(fix.work, fix.settings()).returncode != 0
    fix.path.unlink()
    # Reject a sparse oversized snapshot before trying to allocate/read it.
    with fix.path.open("wb") as stream:
        stream.truncate(2**30)
    assert app.run(fix.work, fix.settings()).returncode != 0
    assert fix.path.stat().st_size == 2**30
    return len(data_cases) + len(settings_cases) + 4


def bounds(app: Application, directory: Path) -> int:
    fix, reference = fixture(directory, "capacity", TTL_KEYS="2"), Reference(2)
    with app.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 1000, "put", key="first", value=None, ttl=1)
        step(fix, reference, server, 1000, "put", key="second", value=None, ttl=100)
        step(fix, reference, server, 1000.5, "put", key="full", value=None, ttl=2)
        assert reference.clock == 1000
        step(fix, reference, server, 1001, "put", key="third", value=None, ttl=100)
        assert "first" not in reference.state()["entries"]
        step(fix, reference, server, 1001, "put", key="second", value="replacement", ttl=1)
        step(fix, reference, server, 1002, "sweep")
    # Exact canonical byte budgets, including quotes and UTF-8 rather than character count.
    fix = fixture(directory, "value-bound", TTL_VALUE_BYTES="10")
    with app.server(fix.work, fix.settings()) as server:
        assert call(server, "put", key="k", value="😀😀", ttl=1).status == 201
        before = fix.path.read_bytes()
        assert call(server, "put", key="k", value="😀😀x", ttl=1).status == 400
        assert fix.path.read_bytes() == before
    fix = fixture(directory, "depth-bound")
    value = None
    for _level in range(16):
        value = [value]
    with app.server(fix.work, fix.settings()) as server:
        assert call(server, "put", key="k", value=value, ttl=86400).status == 201
        before = fix.path.read_bytes()
        assert call(server, "put", key="k", value=[value], ttl=1).status == 400
        assert fix.path.read_bytes() == before
    fix, reference = fixture(directory, "snapshot-bound"), Reference()
    with app.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 1000, "put", key="k", value="x" * 150, ttl=1)
    prior = fix.path.read_bytes()
    future = copy.deepcopy(reference.state())
    future["clock"] = 1001.0
    exact = max(len(prior), len(envelope(future)))
    with app.server(fix.work, fix.settings(TTL_STATE_BYTES=str(exact))) as server:
        fix.clock(1001)
        assert call(server, "get", key="k").status == 404
        assert fix.path.read_bytes() == envelope(future)
        # Even a read must fail if its new watermark cannot fit; no expiry claim escapes.
        fix.clock(1001.123456789)
        assert len(envelope({**future, "clock": 1001.123456789})) > exact
        assert call(server, "get", key="k").status == 507
        assert fix.path.read_bytes() == envelope(future)
        fix.clock(1001)
        assert call(server, "put", key="k", value="x" * 500, ttl=1).status == 507
        assert fix.path.read_bytes() == envelope(future)
        assert call(server, "sweep").json() == {"clock": 1001, "removed": 1}
    fix = fixture(directory, "maximum", TTL_KEYS="256")
    with app.server(fix.work, fix.settings()) as server:
        for index in range(256):
            assert call(server, "put", key=str(index), value=index, ttl=1).status == 201
        assert call(server, "put", key="overflow", value=0, ttl=1).status == 507
        page = call(server, "list", limit=256).json()
        assert page["count"] == len(page["entries"]) == 256 and not page["more"]
        assert [row["key"] for row in page["entries"]] == sorted(str(index) for index in range(256))
        fix.clock(1001)
        assert call(server, "list", limit=256).json()["count"] == 0
        assert call(server, "put", key="fresh", value=None, ttl=1).status == 201
        assert len(json.loads(fix.path.read_bytes())["state"]["entries"]) == 1
    return 20


def disconnected(server: Server, op: str, **args: object) -> None:
    try:
        call(server, op, **args)
    except (OSError, http.client.HTTPException):
        return
    raise AssertionError("interrupted request unexpectedly returned a response")


def wait_for(log: Path, pattern: str, process: subprocess.Popen) -> re.Match:
    until = time.monotonic() + 10
    while time.monotonic() < until:
        found = re.search(pattern, log.read_text())
        if found:
            return found
        assert process.poll() is None, log.read_text()
        time.sleep(0.01)
    raise AssertionError("missing process event: " + pattern + "\n" + log.read_text())


def publication(app: Application, directory: Path) -> int:
    for operation in ["put", "get"]:
        for boundary in ["before_commit", "after_commit"]:
            for interruption in ["fault", "kill"]:
                fix = fixture(directory, f"{operation}-{boundary}-{interruption}")
                reference = Reference()
                with app.server(fix.work, fix.settings()) as server:
                    step(fix, reference, server, 1000, "put", key="k", value="old", ttl=1)
                original = fix.path.read_bytes()
                fix.clock(1001)
                args = {"key": "k"}
                if operation == "put":
                    args.update(value="new", ttl=20)
                reference.apply(1001, operation, **args)
                expected = original if boundary == "before_commit" else envelope(reference.state())
                if interruption == "fault":
                    with app.server(fix.work, fix.settings(TTL_FAULT=boundary)) as server:
                        assert call(server, operation, **args).status == 500
                        assert server.process.poll() is None
                else:
                    log = fix.work / "paused.log"
                    with log.open("w") as stream:
                        process = subprocess.Popen(
                            app.command,
                            cwd=fix.work,
                            env=app.environment(fix.settings(TTL_PAUSE=boundary)),
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            text=True,
                        )
                        try:
                            found = wait_for(log, r"LISTENING http://127\.0\.0\.1:(\d+)", process)
                            server = Server(int(found[1]), process=process)
                            with ThreadPoolExecutor(max_workers=1) as pool:
                                pending = pool.submit(disconnected, server, operation, **args)
                                try:
                                    wait_for(log, "PAUSED " + boundary, process)
                                    # A second writer cannot initialize or serve while the lock is held.
                                    assert app.run(fix.work, fix.settings()).returncode != 0
                                    assert fix.path.read_bytes() == expected
                                finally:
                                    process.kill()
                                    process.wait(timeout=5)
                                pending.result(timeout=5)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.wait(timeout=5)
                assert fix.path.read_bytes() == expected
                # An unacknowledged post-commit update is retained. A pre-commit read made no expiry claim.
                fix.clock(999)
                with app.server(fix.work, fix.settings()) as server:
                    response = call(server, "get", key="k")
                    if boundary == "before_commit":
                        assert response.status == 200 and response.json()["entry"]["value"] == "old"
                    elif operation == "put":
                        assert response.status == 200 and response.json()["entry"]["value"] == "new"
                    else:
                        assert response.status == 404
    fix = fixture(directory, "io-failure")
    with app.server(fix.work, fix.settings()) as server:
        assert call(server, "put", key="k", value="old", ttl=1).status == 201
        original = fix.path.read_bytes()
        fix.clock(1001)
        assert os.geteuid() != 0, "permission failure must be checked as a non-root user"
        fix.work.chmod(0o555)
        try:
            assert call(server, "put", key="k", value="new", ttl=10).status == 500
            assert call(server, "get", key="k").status == 500
            assert fix.path.read_bytes() == original
        finally:
            fix.work.chmod(0o755)
        assert call(server, "get", key="k").status == 404
        target = fix.work / "preserved.json"
        fix.path.rename(target)
        preserved = target.read_bytes()
        fix.path.symlink_to(target)
        assert call(server, "put", key="k", value="new", ttl=10).status == 500
        assert target.read_bytes() == preserved and fix.path.is_symlink()
    return 11


def network_clock(app: Application, directory: Path) -> int:
    fix = fixture(directory, "concurrent", TTL_KEYS="64")
    with app.server(fix.work, fix.settings()) as server:

        def put(index: int) -> None:
            response = call(server, "put", key="並行/" + str(index), value={"index": index}, ttl=10)
            assert response.status == 201, response.body
            return  # noqa: PLR1711

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(put, range(48)))
        page = call(server, "list").json()
        assert page["count"] == len(page["entries"]) == 48
        assert {row["key"]: row["value"] for row in page["entries"]} == {
            "並行/" + str(index): {"index": index} for index in range(48)
        }
        state = json.loads(fix.path.read_bytes())["state"]
        assert fix.path.read_bytes() == envelope(state)
        fix.clock(1010)
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda index: call(server, "get", key="並行/" + str(index)), range(48)))
        assert all(response.status == 404 for response in responses)
        assert call(server, "sweep").json() == {"clock": 1010, "removed": 48}
    # Exercise the production wall clock too; deterministic fixtures alone would
    # not catch accidentally ignoring unix_time() in the default configuration.
    fix = fixture(directory, "wall-clock")
    with app.server(fix.work, fix.settings(TTL_CLOCK="")) as server:
        before = time.time()
        response = call(server, "put", key="live", value=None, ttl=2)
        after = time.time()
        assert response.status == 201
        entry = response.json()["entry"]
        assert before <= entry["written"] <= after and entry["expires"] == entry["written"] + 2
        assert call(server, "get", key="live").status == 200
        time.sleep(max(0, entry["expires"] - time.time()) + 0.02)
        assert call(server, "get", key="live").status == 404
    return 99


def check(app: Application, directory: Path) -> dict:
    count, digest = exercise(app, directory)
    return {
        "oracle_requests": count,
        "trace_sha256": digest,
        "invalid_requests_and_clocks": invalid_requests(app, directory),
        "corrupt_snapshots_and_settings": recovery_validation(app, directory),
        "bounds": bounds(app, directory),
        "publication_checks": publication(app, directory),
        "concurrent_and_wall_clock_requests": network_clock(app, directory),
        "restart_and_clock_rollback": True,
    }
