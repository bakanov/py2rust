"""Independent record, raw-quarantine and restart-boundary checks for JSONL jobs."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import selectors
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def hashed(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def strict(value: object, depth: int = 0) -> None:
    assert depth <= 64
    if type(value) is int:
        assert -(2**63) <= value < 2**63
    elif type(value) is float:
        assert math.isfinite(value)
    elif isinstance(value, str):
        value.encode()
    elif isinstance(value, list):
        for item in value:
            strict(item, depth + 1)
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode()
            strict(item, depth + 1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def equal(left: object, right: object) -> bool:
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(equal(left[key], right[key]) for key in left)
    return left == right


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def source(self) -> Path:
        return self.work / "input.jsonl"

    @property
    def root(self) -> Path:
        return self.work / "job"

    @property
    def settings_path(self) -> Path:
        return self.work / "transform.json"

    def settings(self, **extra: str) -> dict[str, str]:
        return {"JSONL_CONFIG": str(self.settings_path), **extra}

    def save(self) -> None:
        self.settings_path.write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def fixture(directory: Path, name: str, data: bytes | None = None, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "input": "input.jsonl",
        "output": "job",
        "select": ["id", "value"],
        "where": {"kind": "keep"},
        "chunk_bytes": 11,
        "max_line_bytes": 128,
        "batch_rows": 3,
        "batch_bytes": 1024,
    }
    config.update(changes)
    fix = Fixture(work, config)
    if data is None:
        data = b"".join(
            [
                '{"id":1,"kind":"keep","value":"Hello, 世界"}\r\n'.encode(),
                b"broken\xff JSON\n",
                b'{"kind":"drop","ignored":true}\n',
                b"x" * 300 + b"\n",
                b'{"kind":"keep","id":2,"value":{"nested":[1,null,true]}}\n',
                b'{"kind":"keep","id":3}\n',
                b"\n",
                b"[]\n",
                b'{"id":4,"kind":"keep","value":-0.0,"extra":"drop"}\n',
                b'{"id":5,"kind":"keep","value":"last without LF"}',
            ]
        )
    fix.source.write_bytes(data)
    fix.save()
    return fix


def oracle(fix: Fixture, data: bytes | None = None) -> dict:
    source = fix.source.read_bytes() if data is None else data
    accepted, rejected = [], []
    quarantine = bytearray()
    counts = {"lines": 0, "accepted": 0, "filtered": 0, "rejected": 0, "offset": len(source)}
    offset = 0
    for number, raw in enumerate(io.BytesIO(source), 1):
        reason = ""
        value = None
        if len(raw) > fix.config["max_line_bytes"]:
            reason = "line exceeds byte limit"
        else:
            try:
                value = json.loads(raw.decode())
                strict(value)
            except (ValueError, UnicodeError, AssertionError, RecursionError):
                reason = "invalid JSON or UTF-8"
            else:
                if not isinstance(value, dict):
                    reason = "expected JSON object"
        if not reason and any(
            key not in value or not equal(value[key], target) for key, target in fix.config["where"].items()
        ):
            counts["filtered"] += 1
        else:
            if not reason:
                missing = [key for key in fix.config["select"] if key not in value]
                if missing:
                    reason = "missing selected field: " + missing[0]
            if reason:
                rejected.append(
                    {
                        "line": number,
                        "offset": offset,
                        "length": len(raw),
                        "raw_offset": len(quarantine),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "reason": reason,
                    }
                )
                quarantine.extend(raw)
                counts["rejected"] += 1
            else:
                accepted.append({key: value[key] for key in fix.config["select"]})
                counts["accepted"] += 1
        counts["lines"] += 1
        offset += len(raw)
    return {
        "accepted.jsonl": "".join(canonical(row) + "\n" for row in accepted).encode(),
        "quarantine.bin": bytes(quarantine),
        "rejected.jsonl": "".join(canonical(row) + "\n" for row in rejected).encode(),
        "counts": counts,
    }


def checkpoint(fix: Fixture) -> dict:
    envelope = json.loads((fix.root / "checkpoint.json").read_bytes())
    assert set(envelope) == {"checksum", "state"}
    assert envelope["checksum"] == hashlib.sha256(canonical(envelope["state"]).encode()).hexdigest()
    return envelope["state"]


def snapshot(root: Path) -> dict:
    if not os.path.lexists(root):
        return {}
    result = {}
    for path in [root, *root.iterdir()] if root.is_dir() and not root.is_symlink() else [root]:
        info = path.lstat()
        name = path.name
        if stat.S_ISLNK(info.st_mode):
            result[name] = ("symlink", os.readlink(path), info.st_ino)
        elif stat.S_ISREG(info.st_mode):
            result[name] = (
                info.st_dev,
                info.st_ino,
                info.st_size,
                info.st_mode,
                info.st_nlink,
                info.st_mtime_ns,
                info.st_ctime_ns,
                hashed(path),
            )
        else:
            result[name] = (info.st_ino, info.st_mode)
    return result


def invoke(app: Application, fix: Fixture, code: int = 0, timeout: int = 30, **extra: str) -> dict:
    result = app.run(fix.work, fix.settings(**extra), timeout=timeout)
    assert result.returncode == code, result.stderr
    state = checkpoint(fix)
    assert json.loads(result.stdout) == state
    return state


def verify(fix: Fixture, expected: dict, phase: str = "complete") -> dict:
    state = checkpoint(fix)
    assert state["phase"] == phase and state["version"] == 1
    assert all(state[key] == value for key, value in expected["counts"].items()), state
    with fix.source.open("rb") as stream:
        prefix = stream.read(state["offset"])
    assert state["source_sha256"] == hashlib.sha256(prefix).hexdigest()
    for name in ["accepted.jsonl", "quarantine.bin", "rejected.jsonl"]:
        data = (fix.root / name).read_bytes()
        assert data == expected[name], name
        assert state["outputs"][name]["size"] == len(data)
        assert state["outputs"][name]["sha256"] == hashlib.sha256(data).hexdigest()
    return state


def complete(app: Application, fix: Fixture, expected: dict | None = None, timeout: int = 30) -> dict:
    expected = oracle(fix) if expected is None else expected
    source = hashed(fix.source)
    invoke(app, fix, timeout=timeout)
    state = verify(fix, expected)
    before = snapshot(fix.root)
    assert invoke(app, fix, timeout=timeout) == state
    assert snapshot(fix.root) == before and hashed(fix.source) == source
    return state


def reject(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    before = snapshot(fix.root)
    source = hashed(fix.source) if fix.source.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=30)
    assert result.returncode != 0 and message in result.stderr, result.stderr
    assert snapshot(fix.root) == before
    assert source is None or hashed(fix.source) == source
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def pause(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(
            fix.settings(
                JSONL_PAUSE=point, JSONL_CONTINUE=str(fix.work / "continue"), JSONL_CANCEL=str(fix.work / "cancel")
            )
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(15), "JSONL process did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def release(process: subprocess.Popen, fix: Fixture) -> subprocess.CompletedProcess:
    (fix.work / "continue").touch()
    output, error = process.communicate(timeout=30)
    return subprocess.CompletedProcess(process.args, process.returncode, output, error)


def check_basics(app: Application, directory: Path) -> int:
    for index, changes in enumerate(
        [
            {},
            {"chunk_bytes": 1},
            {"chunk_bytes": 65536},
            {"batch_rows": 1},
            {"batch_bytes": 1},
            {"batch_rows": 1000, "batch_bytes": 16777216},
        ]
    ):
        complete(app, fixture(directory, f"basic-{index}", **changes))
    cases = [
        b"",
        b"\n",
        b"\r\n",
        b" ",
        b"{}",
        b'{"id":1,"value":"x"}\r',
        b'{"id":1,"value":"a\\nb\\r"}\n',
        b"NaN\n",
        b'{"id":1,"value":9223372036854775808}\n',
        b'{"id":1,"value":"\\ud800"}\n',
        b"\xef\xbb\xbf{}\n",
    ]
    for index, data in enumerate(cases):
        complete(app, fixture(directory, f"encoding-{index}", data, where={}))
    data = b"".join(
        json.dumps({"id": i, "value": None, "choice": value}, ensure_ascii=False).encode() + b"\n"
        for i, value in enumerate([1, 1.0, True, "1", None, [1], [True], {"x": 1}, {"x": True}])
    )
    for index, target in enumerate([1, True, None, [1], {"x": 1}]):
        complete(app, fixture(directory, f"filter-{index}", data, where={"choice": target}, max_line_bytes=256))
    return 6 + len(cases) + 5


def check_interruptions(app: Application, directory: Path) -> int:
    points = ["stage:0", "initialized:0", "published:0", "row:1", "row:2", "row:3", "row:4", "row:10", "spill:4"]
    points += [f"{label}:{number}" for label in ["before_sync", "after_sync", "checkpoint"] for number in range(1, 5)]
    for index, point in enumerate(points):
        fix = fixture(directory, f"failure-{index}")
        result = app.run(fix.work, fix.settings(JSONL_FAIL=point))
        assert result.returncode != 0 and "injected failure: " + point in result.stderr, result.stderr
        assert not list(fix.work.glob(".jsonl-init-*"))
        complete(app, fix)
    for point in ["stage:0", "initialized:0", "row:2", "spill:4", "after_sync:1", "checkpoint:1", "checkpoint:4"]:
        fix = fixture(directory, "killed-" + point.replace(":", "-"))
        process = pause(app, fix, point)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode == -9
        for stage in fix.work.glob(".jsonl-init-*"):
            assert not fix.root.exists()
            shutil.rmtree(stage)
        complete(app, fix)
    return len(points) + 7


def check_cancellation(app: Application, directory: Path) -> int:
    fix = fixture(directory, "cancel-before")
    cancel = fix.work / "cancel"
    cancel.touch()
    state = invoke(app, fix, code=75, JSONL_CANCEL=str(cancel))
    assert state["offset"] == state["lines"] == state["batches"] == 0
    verify(fix, oracle(fix, b""), phase="paused")
    cancel.unlink()
    complete(app, fix)
    for point, lines in [("row:2", 2), ("spill:4", 3)]:
        fix = fixture(directory, "cancel-" + point.replace(":", "-"))
        process = pause(app, fix, point)
        try:
            (fix.work / "cancel").touch()
            result = release(process, fix)
            assert result.returncode == 75, result.stderr
            prefix = b"".join(list(io.BytesIO(fix.source.read_bytes()))[:lines])
            state = verify(fix, oracle(fix, prefix), phase="paused")
            assert state["lines"] == lines
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        (fix.work / "cancel").unlink()
        complete(app, fix)
    return 3


def partial(app: Application, fix: Fixture) -> dict:
    result = app.run(fix.work, fix.settings(JSONL_FAIL="checkpoint:1"))
    assert result.returncode != 0 and "injected failure" in result.stderr
    return checkpoint(fix)


def check_conflicts(app: Application, directory: Path) -> int:
    kinds = [
        "source",
        "source-append",
        "config",
        "checksum",
        "counter",
        "outputs",
        "missing",
        "short",
        "changed",
        "inode",
        "symlink",
        "hardlink",
    ]
    for kind in kinds:
        fix = fixture(directory, "conflict-" + kind)
        partial(app, fix)
        target = fix.root / "accepted.jsonl"
        if kind == "source":
            fix.source.write_bytes(fix.source.read_bytes().replace(b"Hello", b"HELLO"))
        elif kind == "source-append":
            with fix.source.open("ab") as stream:
                stream.write(b"\n")
        elif kind == "config":
            fix.config["batch_rows"] = 4
            fix.save()
        elif kind in {"checksum", "counter", "outputs"}:
            path = fix.root / "checkpoint.json"
            envelope = json.loads(path.read_bytes())
            if kind == "checksum":
                envelope["checksum"] = "bad"
            else:
                if kind == "counter":
                    envelope["state"]["offset"] = -1
                else:
                    envelope["state"]["outputs"]["../foreign"] = envelope["state"]["outputs"].pop("accepted.jsonl")
                envelope["checksum"] = hashlib.sha256(canonical(envelope["state"]).encode()).hexdigest()
            path.write_text(json.dumps(envelope))
        elif kind == "missing":
            target.unlink()
        elif kind == "short":
            target.write_bytes(target.read_bytes()[:-1])
        elif kind == "changed":
            target.write_bytes(b"X" + target.read_bytes()[1:])
            with (fix.root / "quarantine.bin").open("ab") as stream:
                stream.write(b"uncommitted tail must remain on failure")
        elif kind in {"inode", "symlink"}:
            target.rename(fix.work / "old")
            if kind == "inode":
                target.write_bytes((fix.work / "old").read_bytes())
            else:
                target.symlink_to(fix.work / "old")
        else:
            os.link(target, fix.work / "link")
        reject(app, fix)
    fix = fixture(directory, "uncommitted-tails")
    partial(app, fix)
    for name in ["accepted.jsonl", "quarantine.bin", "rejected.jsonl"]:
        with (fix.root / name).open("ab") as stream:
            stream.write(b"partial uncommitted bytes\xff")
    complete(app, fix)
    fix = fixture(directory, "complete-tail")
    complete(app, fix)
    with (fix.root / "accepted.jsonl").open("ab") as stream:
        stream.write(b"unexpected")
    reject(app, fix, "unexpected tail")
    fix = fixture(directory, "lock-contention")
    process = pause(app, fix, "row:1")
    try:
        reject(app, fix)
        result = release(process, fix)
        assert result.returncode == 0, result.stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    verify(fix, oracle(fix))
    return len(kinds) + 3


def check_invalid(app: Application, directory: Path) -> int:
    changes = [
        {"chunk_bytes": 0},
        {"chunk_bytes": 65537},
        {"chunk_bytes": True},
        {"max_line_bytes": 0},
        {"max_line_bytes": 1048577},
        {"batch_rows": 0},
        {"batch_rows": 1001},
        {"batch_bytes": 0},
        {"batch_bytes": 16777217},
        {"batch_rows": 1.5},
        {"select": []},
        {"select": [""]},
        {"select": ["x", "x"]},
        {"select": ["x" * 257]},
        {"select": [1]},
        {"where": []},
        {"where": {str(i): True for i in range(65)}},
        {"select": [str(i) for i in range(65)]},
        {"extra": True},
        {"input": "missing"},
        {"output": "missing/child"},
        {"input": ""},
        {"output": "/"},
    ]
    for index, change in enumerate(changes):
        fix = fixture(directory, f"invalid-{index}")
        fix.config.update(change)
        fix.save()
        reject(app, fix)
    for index, data in enumerate([b"[]", b"{bad", b"\xff", b"{}" + b" " * 65536]):
        fix = fixture(directory, f"invalid-document-{index}")
        fix.settings_path.write_bytes(data)
        reject(app, fix)
    for kind in ["existing", "symlink", "input-symlink", "input-fifo"]:
        fix = fixture(directory, "invalid-path-" + kind)
        if kind == "existing":
            fix.root.mkdir()
            (fix.root / "keep").write_bytes(b"unchanged")
        elif kind == "symlink":
            fix.root.symlink_to(fix.work)
        else:
            fix.source.rename(fix.work / "original")
            if kind == "input-symlink":
                fix.source.symlink_to("original")
            else:
                os.mkfifo(fix.source)
        reject(app, fix)
    return len(changes) + 8


def check_permissions(app: Application, directory: Path) -> int:
    assert os.getuid() != 0
    for point in ["stage:0", "row:2"]:
        fix = fixture(directory, "permission-" + point.replace(":", "-"))
        process = pause(app, fix, point)
        path = next(fix.work.glob(".jsonl-init-*")) if point.startswith("stage") else fix.root
        try:
            path.chmod(0o500)
            result = release(process, fix)
            assert result.returncode != 0 and "Permission denied" in result.stderr, result.stderr
        finally:
            if path.exists():
                path.chmod(0o700)
            if process.poll() is None:
                process.kill()
                process.communicate()
        assert not list(fix.work.glob(".jsonl-init-*"))
        complete(app, fix)
    return 2


def verify_large(fix: Fixture, state: dict) -> None:
    assert state["phase"] == "complete" and state["offset"] == fix.source.stat().st_size
    assert state["source_sha256"] == hashed(fix.source)
    for name, entry in state["outputs"].items():
        assert entry["size"] == (fix.root / name).stat().st_size
        assert entry["sha256"] == hashed(fix.root / name)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    line = '{"id":1,"kind":"keep","value":"é 😀"}\r\n'.encode()
    for adjustment in [0, -1]:
        fix = fixture(
            directory, f"line-boundary-{adjustment}", line, max_line_bytes=len(line) + adjustment, chunk_bytes=2
        )
        complete(limited, fix)
    many = fixture(
        directory, "large-stream", b"", max_line_bytes=32768, chunk_bytes=65536, batch_rows=1000, batch_bytes=16777216
    )
    with many.source.open("wb") as stream:
        for index in range(6000):
            stream.write(
                json.dumps(
                    {"id": index, "kind": "keep", "value": "ok", "padding": "x" * 30000}, separators=(",", ":")
                ).encode()
                + b"\n"
            )
    assert many.source.stat().st_size > 134217728
    state = invoke(limited, many, timeout=180)
    assert state["lines"] == state["accepted"] == 6000 and state["filtered"] == state["rejected"] == 0
    verify_large(many, state)
    with (many.root / "accepted.jsonl").open("rb") as stream:
        for index in range(6000):
            assert json.loads(stream.readline()) == {"id": index, "value": "ok"}
        assert stream.read(1) == b""
    assert invoke(limited, many, timeout=180) == state
    huge = fixture(
        directory, "oversized-line", b"", max_line_bytes=4096, chunk_bytes=65536, batch_rows=2, batch_bytes=16777216
    )
    first = b'{"id":1,"kind":"keep","value":"before"}\r\n'
    last = b'{"id":2,"kind":"keep","value":"after"}'
    digest = hashlib.sha256()
    block = bytes([0, 255]) * 32768
    with huge.source.open("wb") as stream:
        stream.write(first)
        for _ in range(2560):
            stream.write(block)
            digest.update(block)
        stream.write(b"\r\n" + last)
        digest.update(b"\r\n")
    state = invoke(limited, huge, timeout=180)
    assert state["lines"] == 3 and state["accepted"] == 2 and state["rejected"] == 1 and state["filtered"] == 0
    verify_large(huge, state)
    assert (huge.root / "quarantine.bin").stat().st_size == 167772162
    assert hashed(huge.root / "quarantine.bin") == digest.hexdigest()
    rows = [json.loads(line) for line in (huge.root / "accepted.jsonl").read_bytes().splitlines()]
    assert rows == [{"id": 1, "value": "before"}, {"id": 2, "value": "after"}]
    records = [json.loads(line) for line in (huge.root / "rejected.jsonl").read_bytes().splitlines()]
    assert records == [
        {
            "line": 2,
            "offset": len(first),
            "length": 167772162,
            "raw_offset": 0,
            "sha256": digest.hexdigest(),
            "reason": "line exceeds byte limit",
        }
    ]
    assert invoke(limited, huge, timeout=180) == state
    return {
        "memory_limit": 134217728,
        "valid_stream_bytes": many.source.stat().st_size,
        "valid_rows": 6000,
        "quarantined_line_bytes": 167772162,
    }


def check(app: Application, directory: Path) -> dict:
    basics = check_basics(app, directory)
    interruptions = check_interruptions(app, directory)
    cancellation = check_cancellation(app, directory)
    conflicts = check_conflicts(app, directory)
    invalid = check_invalid(app, directory)
    permissions = check_permissions(app, directory)
    limits = check_limits(app, directory)
    return {
        "record_cases": basics,
        "interruption_cases": interruptions,
        "cancellation_cases": cancellation,
        "conflict_cases": conflicts,
        "invalid_configurations": invalid,
        "permission_failures": permissions,
        "limits": limits,
    }
