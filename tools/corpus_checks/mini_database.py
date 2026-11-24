"""Independent dictionary, binary framing and crash/restart oracles for database 060."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import selectors
import struct
import subprocess
import time
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .common import Application
from .csv_json import canonical

APPEND = [
    "header-part",
    "header-written",
    "body-part",
    "body-written",
    "body-synced",
    "commit-part",
    "commit-written",
    "commit-synced",
]
COMPACTION = [
    "snapshot-part",
    "snapshot-written",
    "snapshot-synced",
    "snapshot-published",
    "snapshot-directory",
    "journal-truncated",
    "journal-cleared",
]
INITIALIZATION = ["owner-prefix", "journal-created", "owner-complete"]
RECOVERY = ["recovery-truncated", "recovery-synced"]


def put(key: str, value: object) -> dict:
    return {"op": "SET", "key": key, "value": value}


def frame(sequence: int, record: dict, raw: bytes | None = None) -> bytes:
    payload = canonical(record).encode() if raw is None else raw
    serial = struct.pack(">Q", sequence)
    return (
        struct.pack(">8sIQ", b"PYDB060!", len(payload), sequence)
        + hashlib.sha256(serial + payload).digest()
        + payload
        + b"DONE060!"
        + serial
    )


def snapshot(sequence: int, values: dict, capacity: int = 16) -> bytes:
    state = {"version": 1, "capacity": capacity, "sequence": sequence, "values": values}
    envelope = {"state": state, "sha256": hashlib.sha256(canonical(state).encode()).hexdigest()}
    return (canonical(envelope) + "\n").encode()


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "database-job.json"

    @property
    def database(self) -> Path:
        return self.work / self.config["database"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def trace(self, commands: list) -> None:
        (self.work / self.config["trace"]).write_text(json.dumps(commands, ensure_ascii=False))
        return

    def settings(self, **extra: str) -> dict:
        return {"DB_CONFIG": str(self.path), "DB_FAIL": "", "DB_PAUSE": "", "DB_CONTINUE": "", **extra}


def fixture(directory: Path, name: str, commands: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"database": "database", "trace": "trace.json", "capacity": 16, **changes})
    fix.save()
    fix.trace(commands)
    return fix


def owner(fix: Fixture) -> bytes:
    return (
        canonical(
            {
                "format": "py2rust-mini-db-v1",
                "database": str(fix.database.resolve()),
                "capacity": fix.config["capacity"],
            }
        )
        + "\n"
    ).encode()


def seed(fix: Fixture, log: bytes = b"", state: bytes | None = None) -> None:
    fix.database.mkdir(exist_ok=True)
    (fix.database / "owner.json").write_bytes(owner(fix))
    (fix.database / "journal.bin").write_bytes(log)
    if state is not None:
        (fix.database / "state.json").write_bytes(state)
    return


def mutate(sequence: int, values: dict, record: dict) -> tuple[int, dict]:
    values = copy.deepcopy(values)
    if record["op"] == "SET":
        values[record["key"]] = copy.deepcopy(record["value"])
    else:
        assert record["op"] == "DELETE"
        values.pop(record["key"], None)
    return sequence + 1, values


def disk_state(fix: Fixture) -> tuple[int, dict, bytes, bytes | None, dict]:
    """Decode with struct/hashlib and an ordinary dictionary, without application imports."""
    state_path = fix.database / "state.json"
    snap = state_path.read_bytes() if state_path.exists() else None
    sequence, values = 0, {}
    if snap is not None:
        envelope = json.loads(snap)
        state = envelope["state"]
        assert envelope["sha256"] == hashlib.sha256(canonical(state).encode()).hexdigest()
        assert state["version"] == 1 and state["capacity"] == fix.config["capacity"]
        sequence, values = state["sequence"], copy.deepcopy(state["values"])
    log_path = fix.database / "journal.bin"
    log = log_path.read_bytes() if log_path.exists() else b""
    offset, replayed, previous = 0, 0, None
    while offset < len(log):
        if len(log) - offset < 52:
            break
        magic, length, serial = struct.unpack_from(">8sIQ", log, offset)
        assert magic == b"PYDB060!" and 1 <= length <= 8192
        assert 1 <= serial <= 10**9
        assert serial <= sequence + 1 if previous is None else serial == previous + 1
        end = offset + 68 + length
        if end > len(log):
            break
        payload = log[offset + 52 : end - 16]
        assert hashlib.sha256(struct.pack(">Q", serial) + payload).digest() == log[offset + 20 : offset + 52]
        assert log[end - 16 : end] == b"DONE060!" + struct.pack(">Q", serial)
        record = json.loads(payload)
        if serial > sequence:
            assert serial == sequence + 1
            sequence, values = mutate(sequence, values, record)
            replayed += 1
        previous, offset = serial, end
    opened = {
        "op": "OPEN",
        "sequence": sequence,
        "replayed": replayed,
        "trimmed_bytes": len(log) - offset,
        "discarded_snapshot": (fix.database / "snapshot.next").exists(),
    }
    return sequence, values, log[:offset], snap, opened


def expected(fix: Fixture, commands: list) -> tuple[list, bytes, bytes | None, dict]:
    sequence, values, log, snap, opened = disk_state(fix)
    responses = [opened]
    for request in commands:
        operation = request["op"]
        response = {"op": operation}
        if operation in ["SET", "DELETE", "GET"]:
            key = request["key"]
            response.update(key=key, found=key in values, value=copy.deepcopy(values.get(key)))
            if operation != "GET":
                sequence, values = mutate(sequence, values, request)
                log += frame(sequence, request)
                response["committed"] = True
        elif operation == "COMPACT":
            snap, log = snapshot(sequence, values, fix.config["capacity"]), b""
        elif operation == "DUMP":
            response["values"] = copy.deepcopy(values)
        else:
            assert operation == "INFO"
            response.update(keys=len(values), capacity=fix.config["capacity"], journal_bytes=len(log))
        response["sequence"] = sequence
        responses.append(response)
    return responses, log, snap, values


def success(app: Application, fix: Fixture) -> list:
    commands = json.loads((fix.work / fix.config["trace"]).read_bytes())
    wanted, log, snap, values = expected(fix, commands)
    result = app.run(fix.work, fix.settings(), timeout=90)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses == wanted, (fix.work, responses, wanted)
    assert result.stdout == "".join(canonical(row) + "\n" for row in wanted)
    assert (fix.database / "owner.json").read_bytes() == owner(fix)
    assert (fix.database / "journal.bin").read_bytes() == log
    assert not (fix.database / "snapshot.next").exists()
    snapshot_path = fix.database / "state.json"
    assert (snapshot_path.read_bytes() if snapshot_path.exists() else None) == snap
    assert disk_state(fix)[1] == values
    return responses


def files(directory: Path) -> dict:
    if not directory.exists():
        return {}
    return {
        path.name: (
            ("link", os.readlink(path))
            if path.is_symlink()
            else ("file", path.read_bytes()) if path.is_file() else ("directory", None)
        )
        for path in directory.iterdir()
    }


def failure(app: Application, fix: Fixture, text: str = "", unchanged: bool = True) -> list:
    before = files(fix.database)
    result = app.run(fix.work, fix.settings(), timeout=20)
    assert result.returncode == 2 and result.stderr, (fix.work, result)
    assert text in result.stderr, (fix.work, result.stderr, text)
    if unchanged:
        after = files(fix.database)
        # Creating the advisory-lock file is harmless even when recovery refuses the data.
        assert {k: v for k, v in before.items() if k != ".lock"} == {k: v for k, v in after.items() if k != ".lock"}, (
            fix.work,
            before,
            after,
        )
    return [json.loads(line) for line in result.stdout.splitlines()]


def traces(app: Application, directory: Path) -> tuple[int, str]:
    rng = random.Random(600060)
    samples = [
        [],
        [{"op": "COMPACT"}, {"op": "COMPACT"}, {"op": "DUMP"}, {"op": "INFO"}],
        [
            put("x", None),
            {"op": "GET", "key": "x"},
            put("x", False),
            {"op": "DELETE", "key": "x"},
            {"op": "DELETE", "key": "x"},
            {"op": "GET", "key": "x"},
        ],
        [
            put("世界", {"deep": [1.25, -0.0, True, None]}),
            put("nul\x00key", "line\nwith\ttabs"),
            put("é", 2**63 - 1),
            put("e\u0301", -(2**63)),
            {"op": "COMPACT"},
            {"op": "DUMP"},
        ],
    ]
    keys = ["one", "two", "three", "世界", "🙂", "", "\x00"]
    keys.remove("")
    for trial in range(24):
        commands = []
        for position in range(24 + trial):
            op = rng.choice(["SET", "SET", "DELETE", "GET", "DUMP", "INFO", "COMPACT"])
            command = {"op": op}
            if op in ["SET", "DELETE", "GET"]:
                command["key"] = rng.choice(keys)
            if op == "SET":
                command["value"] = rng.choice(
                    [
                        None,
                        True,
                        False,
                        position,
                        -position,
                        1.25,
                        [trial, position],
                        {"b": "世界", "a": [None, position]},
                    ]
                )
            commands.append(command)
        samples.append(commands + [{"op": "DUMP"}, {"op": "INFO"}])
    observations = []
    for number, commands in enumerate(samples):
        whole = fixture(directory, f"whole-{number}", commands)
        rows = success(app, whole)
        observations.append(rows)
        whole_log = (whole.database / "journal.bin").read_bytes()
        whole_snapshot = (
            (whole.database / "state.json").read_bytes() if (whole.database / "state.json").exists() else None
        )
        split = fixture(directory, f"split-{number}", [])
        joined = []
        cuts = sorted({0, len(commands) // 3, 2 * len(commands) // 3, len(commands)})
        for start, stop in pairwise(cuts):
            split.trace(commands[start:stop])
            joined += success(app, split)[1:]
        if not commands:
            success(app, split)
        assert joined == rows[1:]
        assert (split.database / "journal.bin").read_bytes() == whole_log
        assert (
            (split.database / "state.json").read_bytes() if (split.database / "state.json").exists() else None
        ) == whole_snapshot
        split.trace([{"op": "DUMP"}])
        assert success(app, split)[-1]["values"] == disk_state(whole)[1]
    return len(samples), hashlib.sha256(canonical(observations).encode()).hexdigest()


def paused(app: Application, fix: Fixture, point: str) -> tuple[subprocess.Popen, list]:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(DB_PAUSE=point)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = b""
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if not selector.select(timeout=1):
                    continue
                chunk = os.read(process.stdout.fileno(), 65536)
                assert chunk, (point, output)
                output += chunk
                lines = output.splitlines()
                if ("PAUSED " + point).encode() in lines:
                    acknowledgements = [json.loads(line) for line in lines if line.startswith(b"{")]
                    return process, acknowledgements
            raise AssertionError(("pause timeout", point, output))
    except BaseException:
        process.kill()
        process.communicate(timeout=5)
        raise


def kill(process: subprocess.Popen) -> None:
    process.kill()
    process.communicate(timeout=5)
    assert process.returncode != 0
    return


def faults(app: Application, directory: Path) -> dict:
    base = frame(1, put("acknowledged", "keep"))
    counts = {"append": 0, "compaction": 0, "initialization": 0, "recovery": 0, "lock": 0}
    for mechanism in ["failure", "kill"]:
        for index, label in enumerate(APPEND):
            fix = fixture(directory, f"{mechanism}-{label}", [put("new", {"opaque": [None, True, "世界"]})])
            seed(fix, base)
            point = label + ":2"
            if mechanism == "kill":
                process, acknowledgements = paused(app, fix, point)
                assert len(acknowledgements) == 1 and acknowledgements[0]["op"] == "OPEN"
                kill(process)
            else:
                result = app.run(fix.work, fix.settings(DB_FAIL=point))
                assert result.returncode == 2 and "injected failure" in result.stderr
                assert len(result.stdout.splitlines()) == 1
            before = disk_state(fix)
            assert before[0] == (2 if index >= 6 else 1)
            fix.trace([{"op": "DUMP"}, put("after", index), {"op": "COMPACT"}, {"op": "INFO"}])
            rows = success(app, fix)
            assert rows[1]["values"]["acknowledged"] == "keep"
            assert ("new" in rows[1]["values"]) == (index >= 6)
            fix.trace([{"op": "DUMP"}])
            success(app, fix)
            counts["append"] += 1
        for label in COMPACTION:
            fix = fixture(directory, f"{mechanism}-{label}", [{"op": "COMPACT"}])
            seed(fix, base + frame(2, put("new", [1, 2, 3])))
            point = label + ":2"
            if mechanism == "kill":
                process, acknowledgements = paused(app, fix, point)
                assert len(acknowledgements) == 1
                kill(process)
            else:
                result = app.run(fix.work, fix.settings(DB_FAIL=point))
                assert result.returncode == 2 and "injected failure" in result.stderr
            fix.trace([{"op": "DUMP"}, put("later", 3), {"op": "COMPACT"}])
            rows = success(app, fix)
            assert rows[1]["sequence"] == 2 and rows[1]["values"] == {"acknowledged": "keep", "new": [1, 2, 3]}
            fix.trace([{"op": "DUMP"}])
            success(app, fix)
            counts["compaction"] += 1
        for label in INITIALIZATION:
            fix = fixture(directory, f"{mechanism}-{label}", [put("x", 1)])
            point = label + ":0"
            if mechanism == "kill":
                process, acknowledgements = paused(app, fix, point)
                assert not acknowledgements
                kill(process)
            else:
                result = app.run(fix.work, fix.settings(DB_FAIL=point))
                assert result.returncode == 2 and not result.stdout
            success(app, fix)
            counts["initialization"] += 1
        for label in RECOVERY:
            fix = fixture(directory, f"{mechanism}-{label}", [{"op": "DUMP"}])
            seed(fix, base + frame(2, put("unfinished", 2))[:-1])
            point = label + ":1"
            if mechanism == "kill":
                process, acknowledgements = paused(app, fix, point)
                assert not acknowledgements
                kill(process)
            else:
                result = app.run(fix.work, fix.settings(DB_FAIL=point))
                assert result.returncode == 2 and not result.stdout
            assert (fix.database / "journal.bin").read_bytes() == base
            assert success(app, fix)[1]["values"] == {"acknowledged": "keep"}
            counts["recovery"] += 1
    for index, label in enumerate(APPEND):
        fix = fixture(directory, "delete-" + label, [{"op": "DELETE", "key": "acknowledged"}])
        seed(fix, base)
        process, acknowledgements = paused(app, fix, label + ":2")
        assert len(acknowledgements) == 1
        kill(process)
        fix.trace([{"op": "DUMP"}])
        rows = success(app, fix)
        assert rows[1]["values"] == ({} if index >= 6 else {"acknowledged": "keep"})
        counts["append"] += 1
    for label in COMPACTION:
        fix = fixture(directory, "replace-" + label, [{"op": "COMPACT"}])
        seed(fix, frame(2, put("new", 2)), snapshot(1, {"acknowledged": "keep"}))
        process, _ = paused(app, fix, label + ":2")
        kill(process)
        fix.trace([{"op": "DUMP"}, {"op": "COMPACT"}])
        assert success(app, fix)[1]["values"] == {"acknowledged": "keep", "new": 2}
        counts["compaction"] += 1
    # Earlier responses really were emitted by this process before it was killed.
    fix = fixture(directory, "ack-before-kill", [put("first", 1), put("second", 2), put("third", 3)])
    process, acknowledgements = paused(app, fix, "body-synced:3")
    assert [row["sequence"] for row in acknowledgements] == [0, 1, 2]
    assert acknowledgements[1]["committed"] and acknowledgements[2]["committed"]
    kill(process)
    fix.trace([{"op": "DUMP"}])
    assert success(app, fix)[1]["values"] == {"first": 1, "second": 2}
    counts["append"] += 1
    fix = fixture(directory, "lock", [put("hold", 1)])
    process, _ = paused(app, fix, "body-synced:1")
    try:
        failure(app, fix)
        counts["lock"] += 1
    finally:
        kill(process)
    success(app, fix)
    return counts


def tails(app: Application, directory: Path) -> int:
    prefix = frame(1, put("first", None))
    complete = frame(2, put("second", "世界🙂"))
    for cut in range(len(complete) + 1):
        fix = fixture(directory, f"cut-{cut}", [{"op": "DUMP"}])
        seed(fix, prefix + complete[:cut])
        rows = success(app, fix)
        assert rows[0]["trimmed_bytes"] == (0 if cut == len(complete) else cut)
        assert rows[1]["sequence"] == (2 if cut == len(complete) else 1)
        assert rows[1]["values"] == ({"first": None, "second": "世界🙂"} if cut == len(complete) else {"first": None})
    return len(complete) + 1


def invalid_inputs(app: Application, directory: Path) -> int:
    cases = [None, [], {}, {"op": "nope"}, {"op": 1}, {"op": True}, {"op": "get", "key": "a"}]
    for op in ["SET", "DELETE", "GET", "DUMP", "INFO", "COMPACT"]:
        command = {"op": op}
        if op in ["SET", "DELETE", "GET"]:
            command["key"] = "a"
        if op == "SET":
            command["value"] = None
        cases += [{**command, "extra": 1}]
        cases += [{key: value for key, value in command.items() if key != missing} for missing in command]
        if "key" in command:
            cases += [{**command, "key": key} for key in ["", "x" * 129, "🙂" * 129, None, True, 1, [], {}]]
    deep = None
    for _ in range(9):
        deep = [deep]
    cases += [put("a", "x" * 4095), put("a", deep)]
    for number, command in enumerate(cases):
        fix = fixture(directory, f"command-{number}", [put("saved", 1), command, put("never", 2)])
        responses = failure(app, fix, "command 2:", unchanged=False)
        assert len(responses) == 2 and responses[1]["committed"]
        fix.trace([{"op": "DUMP"}])
        assert success(app, fix)[1]["values"] == {"saved": 1}
    count = len(cases)
    changes = [{"capacity": n} for n in [0, 257, -1, True, 1.0, "2", None]]
    changes += [{"database": value} for value in ["", "\x00", 1, None]]
    changes += [{"trace": value} for value in ["", "\x00", 1, None]]
    changes += [{"extra": 1}]
    for number, change in enumerate(changes):
        fix = fixture(directory, f"config-{number}", [])
        fix.config.update(change)
        fix.save()
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and not result.stdout
        assert not (fix.work / "database").exists()
        count += 1
    for name in ["database", "trace", "capacity"]:
        fix = fixture(directory, "missing-" + name, [])
        del fix.config[name]
        fix.save()
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and not result.stdout and not (fix.work / "database").exists()
        count += 1
    for target in ["trace.json", "database-job.json"]:
        for number, raw in enumerate(
            [
                b"null",
                b"true",
                b"1",
                b'"text"',
                b"{}",
                b"[",
                b"\xff",
                b"[] trailing",
                b'{"duplicate":1,"duplicate":2}',
                b"[NaN]",
                b"[Infinity]",
            ]
        ):
            fix = fixture(directory, f"raw-{target}-{number}", [])
            (fix.work / target).write_bytes(raw)
            result = app.run(fix.work, fix.settings())
            assert result.returncode == 2 and not result.stdout, (target, raw, result)
            assert not fix.database.exists()
            count += 1
    return count


def corruption(app: Application, directory: Path) -> dict:
    base = frame(1, put("keep", 1))
    second = frame(2, put("new", 2))
    bad_logs = {
        "magic": b"X" + second[1:],
        "length-zero": second[:8] + struct.pack(">I", 0) + second[12:],
        "length-large": second[:8] + struct.pack(">I", 8193) + second[12:],
        "sequence-zero": second[:12] + bytes(8) + second[20:],
        "sequence-large": second[:12] + struct.pack(">Q", 10**9 + 1) + second[20:],
        "checksum": second[:20] + bytes(32) + second[52:],
        "payload": second[:52] + b"X" + second[53:],
        "marker": second[:-16] + b"X" + second[-15:],
        "marker-sequence": second[:-1] + b"\x03",
        "gap": frame(3, put("gap", 3)),
        "duplicate": frame(1, put("duplicate", 1)),
        "nonmutating": frame(2, {"op": "DUMP"}),
        "invalid-json": frame(2, {}, b"{"),
        "invalid-utf8": frame(2, {}, b"\xff"),
        "unknown-field": frame(2, {"op": "DELETE", "key": "keep", "extra": 1}),
        "bad-key": frame(2, put("", 1)),
        "large-value": frame(2, put("a", "x" * 4095)),
    }
    bad_logs["partial-bad-length"] = bad_logs["length-zero"][:12]
    bad_logs["partial-bad-sequence"] = bad_logs["sequence-zero"][:20]
    bad_logs["partial-bad-marker"] = second[:-16] + b"NO"
    for name, bad in bad_logs.items():
        fix = fixture(directory, "journal-" + name, [{"op": "DUMP"}])
        seed(fix, base + bad)
        (fix.database / "snapshot.next").write_bytes(b"keep orphan on validation failure")
        assert not failure(app, fix)
    # Even fully snapshot-covered records are validated before they may be skipped.
    fix = fixture(directory, "covered-corruption", [])
    seed(fix, base + bad_logs["checksum"], snapshot(2, {"keep": 1, "new": 2}))
    failure(app, fix, "checksum")
    state = {"version": 1, "capacity": 16, "sequence": 1, "values": {"keep": 1}}
    variants = []
    for key, options in {
        "version": [0, 2, True, 1.0],
        "capacity": [0, 17, True],
        "sequence": [-1, 10**9 + 1, True, 1.0, 0],
        "values": [[], None, {"": 1}, {"x" * 129: 1}, {"a": "x" * 4095}],
    }.items():
        variants += [{**state, key: value} for value in options]
    variants += [{key: value for key, value in state.items() if key != missing} for missing in state]
    variants += [{**state, "extra": 1}, {**state, "values": {"a": 1, "b": 2}}]
    for number, value in enumerate(variants):
        fix = fixture(directory, f"snapshot-{number}", [])
        raw = canonical({"state": value, "sha256": hashlib.sha256(canonical(value).encode()).hexdigest()}).encode()
        seed(fix, base, raw)
        failure(app, fix)
    for name, raw in {
        "bad-hash": canonical({"state": state, "sha256": "0" * 64}).encode(),
        "missing-hash": canonical({"state": state}).encode(),
        "invalid-json": b"{",
        "utf8": b"\xff",
        "extra": canonical({"state": state, "sha256": "0" * 64, "extra": None}).encode(),
    }.items():
        fix = fixture(directory, "envelope-" + name, [])
        seed(fix, base, raw)
        failure(app, fix)
    # A published snapshot with its old journal is a legal compaction interruption.
    fix = fixture(directory, "overlap", [{"op": "DUMP"}, put("after", 3)])
    seed(fix, base + second, snapshot(2, {"keep": 1, "new": 2}))
    rows = success(app, fix)
    assert rows[0]["replayed"] == 0 and rows[1]["sequence"] == 2
    fix.trace([{"op": "DUMP"}])
    assert success(app, fix)[0]["replayed"] == 1
    return {"journals": len(bad_logs) + 1, "snapshots": len(variants) + 5, "overlap": 1}


def paths(app: Application, directory: Path) -> int:
    count = 0
    for name in ["owner.json", "journal.bin", "state.json", "snapshot.next", ".lock"]:
        for kind in ["symlink", "hardlink", "directory"]:
            fix = fixture(directory, name + "-" + kind, [])
            seed(fix)
            path = fix.database / name
            if path.exists():
                path.unlink()
            protected = fix.work / "protected"
            protected.write_bytes(b"preserve")
            if kind == "symlink":
                path.symlink_to(protected)
            elif kind == "hardlink":
                os.link(protected, path)
            else:
                path.mkdir()
            failure(app, fix)
            assert protected.read_bytes() == b"preserve"
            count += 1
    for name in ["file", "symlink", "dangling"]:
        fix = fixture(directory, "database-" + name, [])
        protected = fix.work / "protected"
        protected.mkdir()
        (protected / "keep").write_bytes(b"preserve")
        if name == "file":
            fix.database.write_bytes(b"preserve")
        else:
            fix.database.symlink_to(protected if name == "symlink" else fix.work / "missing")
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and not result.stdout
        assert (protected / "keep").read_bytes() == b"preserve"
        count += 1
    for name in ["unknown", "foreign", "capacity", "missing-journal", "missing-owner", "partial-with-data"]:
        fix = fixture(directory, name, [])
        seed(fix)
        if name == "unknown":
            (fix.database / "user-file").write_bytes(b"preserve")
        elif name == "foreign":
            (fix.database / "owner.json").write_bytes(owner(fix).replace(b"py2rust", b"foreign"))
        elif name == "capacity":
            fix.config["capacity"] = 15
            fix.save()
        elif name == "missing-journal":
            (fix.database / "journal.bin").unlink()
        elif name == "missing-owner":
            (fix.database / "owner.json").unlink()
        else:
            (fix.database / "owner.json").write_bytes(owner(fix)[:8])
            (fix.database / "journal.bin").write_bytes(frame(1, put("keep", 1)))
        failure(app, fix)
        count += 1
    for name in ["trace.json", "database-job.json"]:
        fix = fixture(directory, "input-link-" + name, [])
        source = fix.work / name
        source.rename(fix.work / "original")
        source.symlink_to(fix.work / "original")
        failure(app, fix, "regular file")
        count += 1
        fix = fixture(directory, "overlap-" + name, [])
        fix.config["database"] = name
        fix.save()
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and "overlaps an input" in result.stderr
        count += 1
    # An empty or prefix owner can recover only an otherwise empty initialization.
    for length in [0, 1, 8]:
        fix = fixture(directory, "owner-prefix-" + str(length), [put("x", 1)])
        seed(fix)
        (fix.database / "owner.json").write_bytes(owner(fix)[:length])
        success(app, fix)
        count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    fix = fixture(directory, "capacity", [put(str(i), i) for i in range(256)], capacity=256)
    success(app, fix)
    fix.trace([put("new", 1)])
    failure(app, fix, "capacity reached")
    fix.trace([put("0", "replace"), {"op": "DELETE", "key": "1"}, put("new", None), {"op": "COMPACT"}])
    success(app, fix)
    fix = fixture(directory, "sequence", [{"op": "DUMP"}], capacity=1)
    seed(fix, state=snapshot(10**9, {"a": 1}, 1))
    success(app, fix)
    for command in [put("a", 2), {"op": "DELETE", "key": "missing"}]:
        fix.trace([command])
        failure(app, fix, "sequence limit")
    fix.trace([{"op": "COMPACT"}, {"op": "GET", "key": "a"}])
    success(app, fix)
    deep = None
    for _ in range(8):
        deep = [deep]
    fix = fixture(directory, "values", [put("🙂" * 128, "x" * 4094), put("depth", deep), {"op": "COMPACT"}])
    success(app, fix)
    fix = fixture(directory, "commands", [{"op": "GET", "key": "x"}] * 1024)
    success(app, fix)
    fix.trace([{"op": "GET", "key": "x"}] * 1025)
    failure(app, fix, "1024")
    for name, maximum in [("database-job.json", 65536), ("trace.json", 1048576)]:
        fix = fixture(directory, "size-" + name, [{"op": "DUMP"}])
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix)
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
    for name, maximum in [("state.json", 4194304), ("journal.bin", 16777216)]:
        fix = fixture(directory, "oversize-" + name, [])
        seed(fix)
        path = fix.database / name
        with path.open("wb") as stream:
            stream.truncate(maximum + 1)
        failure(app, fix, "limit" if name == "state.json" else "exceeds")
        path.unlink()
    fix = fixture(directory, "snapshot-maximum", [{"op": "DUMP"}])
    raw = snapshot(1, {"a": 1})
    seed(fix, state=raw + b" " * (4194304 - len(raw)))
    success(app, fix)
    (fix.database / "state.json").unlink()
    fix = fixture(directory, "record-maximum", [{"op": "DUMP"}])
    raw = canonical(put("a", 1)).encode()
    seed(fix, frame(1, {}, raw + b" " * (8192 - len(raw))))
    success(app, fix)
    # Independently create a completely committed 16 MiB journal, without thousands of fsyncs.
    fix = fixture(directory, "journal-maximum", [{"op": "DUMP"}], capacity=1)
    seed(fix)
    remaining, serial = 16777216, 0
    full = len(frame(1, put("a", "x" * 4094)))
    with (fix.database / "journal.bin").open("wb") as stream:
        while remaining > 2 * full:
            serial += 1
            data = frame(serial, put("a", "x" * 4094))
            stream.write(data)
            remaining -= len(data)
        minimum = len(frame(1, put("a", "")))
        for length in [remaining // 2, remaining - remaining // 2]:
            serial += 1
            data = frame(serial, put("a", "x" * (length - minimum)))
            assert len(data) == length
            stream.write(data)
    assert (fix.database / "journal.bin").stat().st_size == 16777216
    assert success(app, fix)[1]["sequence"] == serial
    fix.trace([put("a", "cannot fit")])
    failure(app, fix, "journal full")
    fix.trace([{"op": "COMPACT"}, put("a", "after compaction"), {"op": "DUMP"}])
    assert success(app, fix)[-1]["values"] == {"a": "after compaction"}
    return {
        "capacity": 256,
        "trace_commands": 1024,
        "key_characters": 128,
        "key_utf8_bytes": 512,
        "value_bytes": 4096,
        "value_depth": 8,
        "sequence": 10**9,
        "journal_bytes": 16777216,
        "journal_capacity_records": serial,
        "snapshot_bytes": 4194304,
        "record_bytes": 8192,
        "trace_bytes": 1048576,
        "config_bytes": 65536,
    }


def check(app: Application, directory: Path) -> dict:
    count, digest = traces(app, directory / "traces")
    print(app.engine + " mini database: dictionary oracle, exact bytes and split restarts passed", flush=True)
    interruptions = faults(app, directory / "faults")
    cuts = tails(app, directory / "tails")
    print(app.engine + " mini database: injected failures, process kills and every-byte tails passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    damaged = corruption(app, directory / "corruption")
    path_cases = paths(app, directory / "paths")
    bounds = limits(app, directory / "limits")
    print(app.engine + " mini database: corruption, ownership and capacity boundaries passed", flush=True)
    return {
        "traces": count,
        "generated_traces": 24,
        "split_restarts": count,
        "results_sha256": digest,
        "interruptions": interruptions,
        "tail_boundaries": cuts,
        "invalid_inputs": invalid,
        "corruption": damaged,
        "path_cases": path_cases,
        "limits": bounds,
    }
