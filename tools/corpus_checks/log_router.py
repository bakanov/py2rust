"""Exercise actual files, independent expected records, rotation and interrupted appends."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
from __future__ import annotations

import hashlib
import json
import os
import queue
import resource
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .common import Application

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def envelope(path: Path, value: dict) -> None:
    path.write_text(canonical({"value": value, "sha256": digest(canonical(value).encode())}) + "\n")
    return


def saved(path: Path) -> dict:
    document = json.loads(path.read_text())
    assert set(document) == {"value", "sha256"}
    assert document["sha256"] == digest(canonical(document["value"]).encode())
    return document["value"]


@dataclass
class Fixture:
    root: Path
    job: dict

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def settings(self) -> dict:
        return {"ROUTER_CONFIG": str(self.root / "job.json"), "ROUTER_INTERVAL_MS": "10"}

    def configure(self) -> None:
        (self.root / "job.json").write_text(canonical(self.job))
        return

    def input(self, key: str) -> Path:
        return self.root / f"{key}.log"

    def append(self, key: str, data: bytes) -> None:
        with self.input(key).open("ab") as stream:
            stream.write(data)
        return


def fixture(root: Path, batch: int = 64, sources: int = 3) -> Fixture:
    root.mkdir(parents=True)
    keys = ["alpha", "beta", "gamma", "delta"][:sources]
    for key in keys:
        (root / f"{key}.log").write_bytes(b"")
    job = {
        "version": 1,
        "sources": [{"id": key, "path": f"{key}.log"} for key in keys],
        "routes": [
            {"id": "general", "sources": keys[:2], "minimum": "INFO", "contains": ""},
            {"id": "alerts", "sources": keys, "minimum": "ERROR", "contains": ""},
            {"id": "pinned", "sources": keys, "minimum": "DEBUG", "contains": "pin"},
            {"id": "unicode", "sources": ["alpha"], "minimum": "DEBUG", "contains": "世界"},
        ],
        "output": "output",
        "segment_bytes": 4096,
        "segments": 8,
        "batch_lines": batch,
    }
    result = Fixture(root, job)
    result.configure()
    return result


def run(app: Application, fix: Fixture, code: int = 0, **settings: str) -> subprocess.CompletedProcess:
    result = app.run(fix.root, dict(fix.settings, **settings))
    assert result.returncode == code, (result.returncode, result.stdout, result.stderr)
    return result


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def records(key: str, data: bytes, start: int = 1, generation: int = 0, offset: int = 0) -> list[dict]:
    result = []
    for index, raw in enumerate(data.splitlines(keepends=True), start):
        assert raw.endswith(b"\n")
        level, message = raw.decode().removesuffix("\n").removesuffix("\r").split(" ", 1)
        result.append(
            {
                "source": key,
                "line": index,
                "generation": generation,
                "offset": offset,
                "level": level,
                "message": message,
            }
        )
        offset += len(raw)
    return result


def inspect(fix: Fixture, expected: list[dict]) -> dict:
    state = saved(fix.output / "state.json")
    assert not (fix.output / "pending.json").exists()
    all_files, matched = {}, set()
    for rule in fix.job["routes"]:
        selected = [
            row
            for row in expected
            if row["source"] in rule["sources"]
            and LEVELS.index(row["level"]) >= LEVELS.index(rule["minimum"])
            and rule["contains"] in row["message"]
        ]
        matched.update((row["source"], row["line"]) for row in selected)
        segments = sorted(fix.output.glob(rule["id"] + ".*.jsonl"))
        assert len(segments) <= fix.job["segments"]
        assert [p.name for p in segments] == [f'{rule["id"]}.{i}.jsonl' for i in range(len(segments))]
        actual, prior_size = [], 0
        for index, path in enumerate(segments):
            data = path.read_bytes()
            lines = data.splitlines(keepends=True)
            assert 0 < len(data) <= fix.job["segment_bytes"]
            if index:
                assert prior_size + len(lines[0]) > fix.job["segment_bytes"], "premature segment rotation"
            prior_size = len(data)
            for line in lines:
                row = json.loads(line)
                assert line == (canonical(row) + "\n").encode()
                actual.append(row)
            all_files[path.name] = {"bytes": len(data), "records": len(lines), "sha256": digest(data)}
        assert actual == selected, (rule["id"], actual, selected)
        assert state["segments"][rule["id"]] == max(0, len(segments) - 1)
    assert state["files"] == all_files
    assert state["filtered"] == len(expected) - len(matched)
    assert sum(cursor["lines"] for cursor in state["sources"].values()) == len(expected)
    for source in fix.job["sources"]:
        cursor = state["sources"][source["id"]]
        candidates = [
            p
            for p in fix.root.iterdir()
            if p.is_file() and f"{p.stat().st_dev}:{p.stat().st_ino}" == cursor["identity"]
        ]
        assert len(candidates) == 1
        prefix = candidates[0].read_bytes()[: cursor["offset"]]
        assert len(prefix) == cursor["offset"] and digest(prefix) == cursor["sha256"]
    return state


def trace(app: Application, root: Path) -> dict:
    fix = fixture(root, batch=2)
    alpha = b"INFO hello\nDEBUG hidden\nWARNING pin this\n"
    beta = "INFO beta\nERROR pin 世界\r\n".encode()
    gamma = b"DEBUG ignored\nCRITICAL system down\n"
    fix.append("alpha", alpha + b"ERROR partial ")
    fix.append("beta", beta)
    fix.append("gamma", gamma)
    expected = records("alpha", b"INFO hello\nDEBUG hidden\n") + records("beta", beta) + records("gamma", gamma)
    run(app, fix)
    inspect(fix, expected)
    expected += records("alpha", b"WARNING pin this\n", 3, offset=len(b"INFO hello\nDEBUG hidden\n"))
    run(app, fix)
    inspect(fix, expected)
    before = snapshot(fix.output)
    run(app, fix)
    assert before == snapshot(fix.output), "partial tail advanced state"
    fix.append("alpha", "世界\n".encode())
    expected += records("alpha", "ERROR partial 世界\n".encode(), 4, offset=len(alpha))
    run(app, fix)
    inspect(fix, expected)
    old_size = fix.input("alpha").stat().st_size
    remaining = b"ERROR old one\nWARNING old two\nINFO old three\n"
    fix.append("alpha", remaining)
    fix.input("alpha").rename(root / "alpha.log.1")
    fresh = b"INFO new one\nCRITICAL new two\n"
    fix.input("alpha").write_bytes(fresh)
    run(app, fix)
    expected += records("alpha", b"ERROR old one\nWARNING old two\n", 5, offset=old_size)
    inspect(fix, expected)
    run(app, fix)
    expected += records("alpha", b"INFO old three\n", 7, offset=old_size + len(b"ERROR old one\nWARNING old two\n"))
    state = inspect(fix, expected)
    assert state["sources"]["alpha"]["offset"] == 0 and len(state["sources"]["alpha"]["past"]) == 1
    run(app, fix)
    expected += records("alpha", fresh, 8, 1)
    inspect(fix, expected)
    fix.append("beta", b"ERROR gap complete\nINFO unfinished")
    fix.input("beta").rename(root / "beta.log.1")
    run(app, fix)
    expected += records("beta", b"ERROR gap complete\n", 3, offset=len(beta))
    inspect(fix, expected)
    before = snapshot(fix.output)
    run(app, fix)
    assert before == snapshot(fix.output)
    with (root / "beta.log.1").open("ab") as stream:
        stream.write(b"\n")
    fix.input("beta").write_bytes(b"WARNING beta replacement\n")
    run(app, fix)
    expected += records("beta", b"INFO unfinished\n", 4, offset=len(beta) + len(b"ERROR gap complete\n"))
    inspect(fix, expected)
    run(app, fix)
    expected += records("beta", b"WARNING beta replacement\n", 5, 1)
    state = inspect(fix, expected)
    before = snapshot(fix.output)
    run(app, fix, ROUTER_POLLS="3")
    assert before == snapshot(fix.output)
    # Old unrelated hard links in the directory must not prevent locating a rotated source.
    (root / "unrelated").write_bytes(b"unrelated")
    os.link(root / "unrelated", root / "unrelated-alias")
    fix.input("gamma").rename(root / "gamma.log.1")
    fix.input("gamma").write_bytes(b"")
    run(app, fix)
    inspect(fix, expected)
    return {
        "input_records": len(expected),
        "records_sha256": digest(canonical(expected).encode()),
        "filtered": state["filtered"],
    }


def publication(app: Application, root: Path) -> int:
    labels = [
        "planned",
        "partial-0",
        "file-0",
        "partial-1",
        "file-1",
        "partial-2",
        "file-2",
        "partial-3",
        "file-3",
        "state",
        "cleared",
    ]
    count = 0
    for label in labels:
        for kill in [False, True]:
            fix = fixture(root / f"{label}-{kill}")
            baseline = b"INFO baseline\n"
            fix.append("alpha", baseline)
            run(app, fix)
            extra = ("ERROR pin 世界 " + "λ" * 40 + "\n").encode()
            fix.append("alpha", extra)
            if kill:
                process, lines = paused(app, fix, label)
                before = snapshot(fix.output)
                run(app, fix, 2)
                assert snapshot(fix.output) == before, "second writer modified locked outputs"
                process.kill()
                process.communicate(timeout=5)
                assert not lines.empty() or process.returncode != 0
            else:
                run(app, fix, 2, ROUTER_FAULT=label)
            run(app, fix)
            expected = records("alpha", baseline + extra)
            inspect(fix, expected)
            before = snapshot(fix.output)
            run(app, fix)
            assert snapshot(fix.output) == before, "recovery was not idempotent"
            count += 1
    # The saved plan can finish without rereading uncommitted source bytes.
    fix = fixture(root / "source-changed-after-plan")
    fix.append("alpha", b"INFO baseline\n")
    run(app, fix)
    original = b"INFO baseline\nERROR pin original\n"
    fix.input("alpha").write_bytes(original)
    run(app, fix, 2, ROUTER_FAULT="partial-1")
    fix.input("alpha").write_bytes(original.replace(b"original", b"modified"))
    run(app, fix, 2)
    assert not (fix.output / "pending.json").exists()
    assert saved(fix.output / "state.json")["sources"]["alpha"]["sha256"] == digest(original)
    fix.input("alpha").write_bytes(original)
    run(app, fix)
    inspect(fix, records("alpha", original))
    count += 1
    return count


def paused(app: Application, fix: Fixture, label: str) -> tuple[subprocess.Popen, queue.Queue]:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, ROUTER_PAUSE=label)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=10)
            assert line is not None, "process exited before pause"
            if line.strip() == "PAUSED " + label:
                return process, lines
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def rejected_inputs(app: Application, root: Path) -> int:
    cases = [
        b"\n",
        b"INFO\n",
        b"TRACE nope\n",
        b"info nope\n",
        b" INFO nope\n",
        b"INFO\tx\n",
        b"INFO \x00\n",
        b"INFO \x01\n",
        b"INFO \x7f\n",
        b"INFO \xff\n",
        b"INFO bad\rbody\n",
        b"INFO " + b"x" * 1019 + b"\n",
        b"INFO " + b"x" * 1020,
    ]
    for index, data in enumerate(cases):
        fix = fixture(root / f"line-{index}")
        run(app, fix)
        before = snapshot(fix.output)
        fix.append("alpha", b"INFO must not commit\n")
        fix.append("beta", data)
        run(app, fix, 2)
        assert snapshot(fix.output) == before, "invalid batch partially committed"
    mutations = [
        "edit",
        "truncate",
        "missing",
        "symlink",
        "hardlink",
        "reused",
        "unknown-output",
        "corrupt-output",
        "extra-output",
        "truncate-output",
    ]
    for name in mutations:
        fix = fixture(root / name)
        fix.append("alpha", b"INFO committed\n")
        run(app, fix)
        output = fix.output / "general.0.jsonl"
        if name == "edit":
            fix.input("alpha").write_bytes(b"INFO xommitted\n")
        elif name == "truncate":
            fix.input("alpha").write_bytes(b"")
        elif name == "missing":
            fix.input("alpha").unlink()
        elif name in ["symlink", "hardlink"]:
            path = fix.input("alpha")
            path.rename(fix.root / "old")
            if name == "symlink":
                path.symlink_to(fix.root / "old")
            else:
                os.link(fix.root / "old", path)
        elif name == "reused":
            fix.input("alpha").rename(fix.root / "old")
            fix.input("alpha").write_bytes(b"")
            run(app, fix)
            fix.input("alpha").rename(fix.root / "new")
            (fix.root / "old").rename(fix.input("alpha"))
        elif name == "unknown-output":
            (fix.output / "foreign.txt").write_bytes(b"preserve")
        elif name == "corrupt-output":
            output.write_bytes(output.read_bytes().replace(b"committed", b"xommitted"))
        elif name == "extra-output":
            output.write_bytes(output.read_bytes() + b"unexpected\n")
        else:
            output.write_bytes(b"")
        before = snapshot(fix.output)
        run(app, fix, 2)
        assert snapshot(fix.output) == before
    return len(cases) + len(mutations)


def invalid_settings(app: Application, root: Path) -> int:
    cases = [
        ("version", 2),
        ("version", True),
        ("segment_bytes", 4095),
        ("segment_bytes", 16385),
        ("segment_bytes", 4096.0),
        ("segments", 0),
        ("segments", 9),
        ("batch_lines", 0),
        ("batch_lines", 65),
        ("sources", []),
        ("routes", []),
        ("output", ""),
        ("output", "job.json"),
        ("output", "alpha.log"),
        ("extra", 1),
    ]
    for index, (key, value) in enumerate(cases):
        fix = fixture(root / str(index))
        fix.job[key] = value
        fix.configure()
        inputs = {p: p.read_bytes() for p in fix.root.glob("*.log")}
        run(app, fix, 2)
        assert all(p.read_bytes() == data for p, data in inputs.items())
        assert not fix.output.exists()
    extra = [
        "duplicate-source",
        "alias-source",
        "unknown-source",
        "duplicate-selector",
        "level",
        "id",
        "contains",
        "source-extra",
        "route-extra",
        "too-many",
    ]
    for name in extra:
        fix = fixture(root / name)
        if name == "duplicate-source":
            fix.job["sources"].append(fix.job["sources"][0])
        elif name == "alias-source":
            fix.job["sources"][1]["path"] = "alpha.log"
        elif name == "unknown-source":
            fix.job["routes"][0]["sources"] = ["unknown"]
        elif name == "duplicate-selector":
            fix.job["routes"][0]["sources"] = ["alpha", "alpha"]
        elif name == "level":
            fix.job["routes"][0]["minimum"] = "TRACE"
        elif name == "id":
            fix.job["routes"][0]["id"] = "../escape"
        elif name == "contains":
            fix.job["routes"][0]["contains"] = "λ" * 65
        elif name == "source-extra":
            fix.job["sources"][0]["extra"] = 1
        elif name == "route-extra":
            fix.job["routes"][0]["extra"] = 1
        else:
            fix.job["routes"].append(fix.job["routes"][0])
        fix.configure()
        run(app, fix, 2)
        assert not fix.output.exists()
    return len(cases) + len(extra)


def corrupt_controls(app: Application, root: Path) -> int:
    changes = [
        lambda s: s.update(version=2),
        lambda s: s.update(extra=True),
        lambda s: s.update(filtered=-1),
        lambda s: s.update(filtered=2),
        lambda s: s["policy"].update(batch_lines=1),
        lambda s: s["sources"].update(unknown=s["sources"]["alpha"]),
        lambda s: s["sources"]["alpha"].update(offset=-1),
        lambda s: s["sources"]["alpha"].update(offset=67108865),
        lambda s: s["sources"]["alpha"].update(lines=False),
        lambda s: s["sources"]["alpha"].update(sha256="invalid"),
        lambda s: s["sources"]["alpha"].update(identity="invalid"),
        lambda s: s["sources"]["alpha"].update(past=["1:1"] * 33),
        lambda s: s["sources"]["beta"].update(identity=s["sources"]["alpha"]["identity"]),
        lambda s: s["segments"].update(general=8),
        lambda s: s["segments"].update(general=1),
        lambda s: s["files"]["general.0.jsonl"].update(bytes=0),
        lambda s: s["files"]["general.0.jsonl"].update(records=0),
        lambda s: s["files"]["general.0.jsonl"].update(sha256="0" * 64),
    ]
    for index, change in enumerate(changes):
        fix = fixture(root / str(index))
        fix.append("alpha", b"INFO once\n")
        run(app, fix)
        path = fix.output / "state.json"
        state = saved(path)
        change(state)
        envelope(path, state)
        before = snapshot(fix.output)
        run(app, fix, 2)
        assert snapshot(fix.output) == before
    for name in [
        "checksum",
        "broken-json",
        "pending-hash",
        "pending-extra",
        "pending-mismatch",
        "planned-prefix",
        "planned-suffix",
        "unknown-file",
    ]:
        fix = fixture(root / name)
        fix.append("alpha", b"INFO baseline\n")
        run(app, fix)
        fix.append("alpha", b"ERROR pin pending\n")
        run(app, fix, 2, ROUTER_FAULT="partial-1")
        path = fix.output / "pending.json"
        if name == "checksum":
            state_path = fix.output / "state.json"
            document = json.loads(state_path.read_text())
            document["sha256"] = "0" * 64
            state_path.write_text(canonical(document))
        elif name == "broken-json":
            path.write_text("{")
        elif name == "pending-hash":
            document = json.loads(path.read_text())
            document["sha256"] = "0" * 64
            path.write_text(canonical(document))
        elif name in ["pending-extra", "pending-mismatch"]:
            plan = saved(path)
            if name == "pending-extra":
                plan["append"]["../escape"] = "text"
            else:
                plan["before"]["sources"]["alpha"]["lines"] += 1
            envelope(path, plan)
        elif name in ["planned-prefix", "planned-suffix"]:
            output = fix.output / "general.0.jsonl"
            data = bytearray(output.read_bytes())
            data[0 if name == "planned-prefix" else -1] ^= 1
            output.write_bytes(data)
        else:
            (fix.output / "unexpected").write_text("preserve")
        before = snapshot(fix.output)
        run(app, fix, 2)
        assert snapshot(fix.output) == before, "recovery modified files before validating all outputs"
    return len(changes) + 8


def capacity(app: Application, root: Path) -> dict:
    fix = fixture(root, sources=4)
    fix.job["segment_bytes"] = 16384
    fix.job["routes"] = [
        {"id": f"route{i}", "sources": ["alpha", "beta", "gamma", "delta"], "minimum": "DEBUG", "contains": ""}
        for i in range(4)
    ]
    fix.configure()
    # Exactly 1024 physical bytes per line, with Unicode and JSON escaping.
    line = ("INFO " + "λ" * 500 + '"' * 18 + "\n").encode()
    assert len(line) == 1024
    expected = []
    for key in ["alpha", "beta", "gamma", "delta"]:
        fix.append(key, line * 28)
        expected.extend(records(key, line * 28))

    def limited() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=30,
        preexec_fn=limited,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    state = inspect(fix, expected)
    assert len(state["files"]) == 32 and all(index == 7 for index in state["segments"].values())
    before = snapshot(fix.output)
    fix.append("alpha", line * 64)
    run(app, fix, 2)
    assert snapshot(fix.output) == before, "capacity failure advanced positions"
    return {
        "sources": 4,
        "routes": 4,
        "segments": 32,
        "input_records": len(expected),
        "line_bytes": 1024,
        "memory_limit": 268435456,
        "output_sha256": digest(canonical(state["files"]).encode()),
    }


def daemon(app: Application, root: Path) -> int:
    fix = fixture(root)
    stop = root / "stop"
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment(dict(fix.settings, ROUTER_POLLS="0", ROUTER_STOP=str(stop))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 10
        while not (fix.output / "state.json").exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        fix.append("alpha", b"INFO live\n")
        while not (fix.output / "general.0.jsonl").exists():
            assert process.poll() is None and time.monotonic() < deadline
            time.sleep(0.01)
        stop.write_text("stop")
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, (stdout, stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
    inspect(fix, records("alpha", b"INFO live\n"))
    # A leftover control staging file is safe to overwrite after a process crash.
    (fix.output / "control.tmp").write_bytes(b"part of a control snapshot")
    fix.append("alpha", b"INFO next\n")
    run(app, fix)
    inspect(fix, records("alpha", b"INFO live\nINFO next\n"))
    return 2


def boundaries(app: Application, root: Path) -> dict:
    fix = fixture(root / "batch", sources=4)
    expected = []
    for key in ["alpha", "beta", "gamma", "delta"]:
        fix.append(key, b"INFO bounded\n" * 65)
        expected += records(key, b"INFO bounded\n" * 64)
    run(app, fix)
    inspect(fix, expected)
    for key in ["alpha", "beta", "gamma", "delta"]:
        expected += records(key, b"INFO bounded\n", 65, offset=64 * len(b"INFO bounded\n"))
    run(app, fix)
    inspect(fix, expected)
    fix = fixture(root / "bytes", batch=1)
    with fix.input("alpha").open("wb") as stream:
        stream.write(b"INFO large file\n")
        stream.truncate(67108864)
    run(app, fix)
    before = snapshot(fix.output)
    with fix.input("alpha").open("ab") as stream:
        stream.write(b"x")
    run(app, fix, 2)
    assert snapshot(fix.output) == before
    fix = fixture(root / "config-size")
    config = fix.root / "job.json"
    original = config.read_bytes()
    config.write_bytes(original + b" " * (65536 - len(original)))
    run(app, fix)
    before = snapshot(fix.output)
    config.write_bytes(config.read_bytes() + b" ")
    run(app, fix, 2)
    assert snapshot(fix.output) == before
    fix = fixture(root / "rotations")
    run(app, fix)
    for index in range(32):
        fix.input("alpha").rename(fix.root / f"old-{index}")
        fix.input("alpha").write_bytes(b"")
        run(app, fix)
    state = inspect(fix, [])
    assert len(state["sources"]["alpha"]["past"]) == 32
    fix.input("alpha").rename(fix.root / "old-32")
    fix.input("alpha").write_bytes(b"")
    before = snapshot(fix.output)
    run(app, fix, 2)
    assert snapshot(fix.output) == before
    fix = fixture(root / "directory")
    run(app, fix)
    fix.input("alpha").rename(fix.root / "old-alpha")
    fix.input("alpha").write_bytes(b"")
    for index in range(256 - len(list(fix.root.iterdir()))):
        (fix.root / f"extra-{index}").write_bytes(b"")
    assert len(list(fix.root.iterdir())) == 256
    run(app, fix)
    fix.input("alpha").rename(fix.root / "old-alpha-two")
    fix.input("alpha").write_bytes(b"")
    before = snapshot(fix.output)
    run(app, fix, 2)
    assert snapshot(fix.output) == before
    fix = fixture(root / "filter")
    fix.job["routes"][2]["contains"] = "λ" * 64
    fix.job["routes"][2]["id"] = "route_1234567890"
    fix.configure()
    line = ("INFO \t" + "λ" * 64 + "\r\n").encode()
    fix.append("alpha", line[:-3])
    run(app, fix)
    inspect(fix, [])
    fix.append("alpha", line[-3:])
    run(app, fix)
    inspect(fix, records("alpha", line))
    alias_checks = 0
    for name in ["state.json", "pending.json", "control.tmp", "general.0.jsonl"]:
        for kind in ["symbolic", "hard"]:
            fix = fixture(root / f"{name}-{kind}")
            fix.append("alpha", b"INFO safe\n")
            run(app, fix)
            path, target = fix.output / name, fix.root / "preserved"
            if path.exists():
                path.rename(target)
            else:
                target.write_bytes(b"preserve this")
            if kind == "symbolic":
                path.symlink_to(target)
            else:
                os.link(target, path)
            before = snapshot(fix.output)
            preserved = target.read_bytes()
            run(app, fix, 2)
            assert snapshot(fix.output) == before and target.read_bytes() == preserved
            alias_checks += 1
    for setting, value in [
        ("ROUTER_POLLS", "-1"),
        ("ROUTER_POLLS", "100001"),
        ("ROUTER_POLLS", "true"),
        ("ROUTER_INTERVAL_MS", "9"),
        ("ROUTER_INTERVAL_MS", "60001"),
    ]:
        fix = fixture(root / f"{setting}-{value}")
        run(app, fix, 2, **{setting: value})
        assert not fix.output.exists()
    return {
        "batch_records": 256,
        "maximum_source_bytes": 67108864,
        "configuration_bytes": 65536,
        "retired_identities": 32,
        "scan_entries": 256,
        "filter_bytes": 128,
        "alias_checks": alias_checks,
        "invalid_poll_settings": 5,
    }


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "trace": trace(app, directory / "trace"),
        "publication_checks": publication(app, directory / "publication"),
        "invalid_batches_and_files": rejected_inputs(app, directory / "rejected"),
        "invalid_settings": invalid_settings(app, directory / "settings"),
        "corrupt_controls": corrupt_controls(app, directory / "corrupt"),
        "capacity": capacity(app, directory / "capacity"),
        "daemon_checks": daemon(app, directory / "daemon"),
        "boundaries": boundaries(app, directory / "boundaries"),
        "independent_record_oracle": True,
    }
