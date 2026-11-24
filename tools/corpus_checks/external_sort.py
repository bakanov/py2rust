"""Independent in-memory sort oracle, bounded-memory proof and interrupted-run checks."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import hashlib
import json
import os
import random
import selectors
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "sort-job.json"

    @property
    def output(self) -> Path:
        return self.work / "sorted-run"

    @property
    def workspace(self) -> Path:
        return self.work / "sort-work"

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, **extra: str) -> dict:
        return {
            "SORT_CONFIG": str(self.path),
            "SORT_MODE": "sort",
            "SORT_FAIL": "",
            "SORT_PAUSE": "",
            "SORT_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, rows: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    (work / "records.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    config = {
        "inputs": ["records.jsonl"],
        "field": "key",
        "kind": "integer",
        "chunk_bytes": 4096,
        "record_bytes": 4096,
        "fan_in": 2,
        "max_rows": 1000000,
        "memory_mib": 128,
        "output": "sorted-run",
        "workspace": "sort-work",
        **changes,
    }
    fix = Fixture(work, config)
    fix.save()
    return fix


def sample() -> list:
    return [
        {"key": key, "id": number, "payload": ["世界", True, None, {"decimal": 1.25}]}
        for number, key in enumerate([3, -1, 3, 0, -1, 3, 2, -1, 2])
    ]


def reference(fix: Fixture) -> tuple[bytes, list[dict]]:
    # This oracle loads complete datasets and uses CPython's stable sort. It does
    # not import application code or reproduce the application's runs or heap.
    records = []
    inputs = []
    for position, name in enumerate(fix.config["inputs"]):
        raw = (fix.work / name).read_bytes()
        rows = [json.loads(line) for line in raw.splitlines()]
        records.extend(rows)
        inputs.append({"input_index": position, "rows": len(rows), "bytes": len(raw)})
    ordered = sorted(records, key=lambda row: row[fix.config["field"]])
    return "".join(canonical(row) + "\n" for row in ordered).encode(), inputs


def clean(fix: Fixture) -> None:
    assert sorted(path.name for path in fix.workspace.iterdir()) == [".lock", "owner.json"]
    owner = {
        "format": "external-sort-v1",
        "workspace": str(fix.workspace),
        "output": str(fix.output),
        "config": str(fix.path),
    }
    assert (fix.workspace / "owner.json").read_bytes() == (canonical(owner) + "\n").encode()
    return


def outputs(fix: Fixture, expected: bytes, inputs: list[dict], recovered: int = 0) -> dict:
    assert sorted(path.name for path in fix.output.iterdir()) == ["report.json", "sorted.jsonl"]
    assert (fix.output / "sorted.jsonl").read_bytes() == expected
    report = json.loads((fix.output / "report.json").read_bytes())
    assert set(report) == {
        "rows",
        "inputs",
        "peak_batch_bytes",
        "initial_runs",
        "merge_passes",
        "output_bytes",
        "output_sha256",
        "memory_limit_bytes",
        "recovered_files",
    }
    assert report["inputs"] == inputs
    assert report["rows"] == sum(item["rows"] for item in inputs)
    assert report["output_bytes"] == len(expected)
    assert report["output_sha256"] == hashlib.sha256(expected).hexdigest()
    assert 0 <= report["peak_batch_bytes"] <= fix.config["chunk_bytes"]
    assert report["memory_limit_bytes"] == fix.config["memory_mib"] * 1048576
    assert report["recovered_files"] == recovered
    runs = report["initial_runs"]
    assert (runs == 0) == (report["rows"] == 0) and 0 <= runs <= min(4096, report["rows"])
    passes = 0
    while runs > 1:
        runs = (runs + fix.config["fan_in"] - 1) // fix.config["fan_in"]
        passes += 1
    assert report["merge_passes"] == passes
    clean(fix)
    return report


def success(app: Application, fix: Fixture, recovered: int = 0) -> dict:
    expected, inputs = reference(fix)
    paths = [fix.path, *(fix.work / name for name in fix.config["inputs"])]
    before = [path.read_bytes() for path in paths]
    result = app.run(fix.work, fix.settings(), timeout=120)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    report = outputs(fix, expected, inputs, recovered)
    assert json.loads(result.stdout) == report and (fix.output / "report.json").read_text() == result.stdout
    assert [path.read_bytes() for path in paths] == before
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    saved = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=120)
    assert result.returncode == 2 and message in result.stderr and result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if saved is not None:
        assert fix.output.read_bytes() == saved
    return


def valid_cases(app: Application, directory: Path) -> tuple[int, str]:
    rng = random.Random(57057)
    cases = [([], "integer"), (sample(), "integer")]
    cases.append(([{"id": i, "key": k} for i, k in enumerate([-(2**63), 2**63 - 1, 0, -(2**63)])], "integer"))
    strings = ["", "世界", "ß", "ss", "café", "cafe\u0301", "😀", "\x00", "\n", 'quote"', "\\", "a", "A"]
    cases.append(([{"id": i, "key": k} for i, k in enumerate(strings * 2)], "string"))
    for trial in range(24):
        kind = "integer" if trial % 2 == 0 else "string"
        rows = [
            {
                "key": rng.randrange(-20, 21) if kind == "integer" else rng.choice(strings),
                "id": i,
                "payload": {"unicode": rng.choice(strings), "padding": "a" * rng.randrange(1, 90)},
            }
            for i in range(rng.randrange(10, 180))
        ]
        cases.append((rows, kind))
    evidence = []
    for number, (rows, kind) in enumerate(cases):
        fix = fixture(
            directory,
            f"case-{number}",
            rows,
            kind=kind,
            chunk_bytes=[4096, 8192, 16384][number % 3],
            record_bytes=[4096, 512, 1024][number % 3],
            fan_in=[2, 3, 8][number % 3],
        )
        if number % 4 == 0:
            # Empty files, repeated inputs and stable ties across file boundaries.
            raw = (fix.work / "records.jsonl").read_bytes()
            (fix.work / "second.jsonl").write_bytes(raw.replace(b"\n", b"\r\n").removesuffix(b"\r\n"))
            (fix.work / "empty.jsonl").write_bytes(b"")
            fix.config["inputs"] = ["records.jsonl", "empty.jsonl", "second.jsonl", "records.jsonl"]
            fix.save()
        report = success(app, fix)
        evidence.append(report)
        if number < 8:
            single = fixture(directory, f"single-{number}", [], kind=kind, chunk_bytes=4194304, record_bytes=65536)
            single.config["inputs"] = [str(fix.work / name) for name in fix.config["inputs"]]
            single.save()
            other = success(app, single)
            assert (single.output / "sorted.jsonl").read_bytes() == (fix.output / "sorted.jsonl").read_bytes()
            assert other["initial_runs"] in [0, 1]
    # The row-count cap also bounds tiny object overhead even when the byte budget is large.
    many = fixture(
        directory, "small-rows", [{"key": i % 5} for i in range(4100)], chunk_bytes=4194304, record_bytes=256
    )
    assert success(app, many)["initial_runs"] == 2
    duplicate = fixture(directory, "duplicate-object-key", [])
    (duplicate.work / "records.jsonl").write_bytes(b'{"key":9,"key":-1,"id":0}\n{"key":0,"id":1}\n')
    evidence.append(success(app, duplicate))
    return len(cases) + 8 + 2, hashlib.sha256(canonical(evidence).encode()).hexdigest()


def invalid_cases(app: Application, directory: Path) -> int:
    count = 0
    for field, values in {
        "inputs": [[], ["records.jsonl"] * 17, "records.jsonl", [None], [""], ["\x00"]],
        "field": ["", None, 3, "a" * 129],
        "kind": ["float", "INTEGER", None],
        "chunk_bytes": [4095, 4194305, True, 1.0],
        "record_bytes": [255, 4097, False, 256.0],
        "fan_in": [1, 9, None, True],
        "max_rows": [0, 1000001, True, "1"],
        "memory_mib": [127, 1025, True, 128.0],
        "output": ["", "\x00", None],
        "workspace": ["", "\x00", None, "records.jsonl", "sort-job.json", "sorted-run", "."],
    }.items():
        for value in values:
            failure(app, fixture(directory, f"config-{count}", sample(), **{field: value}))
            count += 1
    base = fixture(directory, "base", []).config
    for field in base:
        fix = fixture(directory, f"missing-{field}", [])
        del fix.config[field]
        fix.save()
        failure(app, fix, "unexpected configuration fields")
        count += 1
    for raw in [b"[]", b"null", b"{", b"\xff", b" " * 65537]:
        fix = fixture(directory, f"config-root-{count}", [])
        fix.path.write_bytes(raw)
        failure(app, fix)
        count += 1
    for raw in [
        b"\n",
        b" \n",
        b"{}\n",
        b"[]\n",
        b"null\n",
        b"{\n",
        b"\xff\n",
        b'{"key":true}\n',
        b'{"key":null}\n',
        b'{"key":"1"}\n',
        b'{"key":1.0}\n',
        b'{"key":9223372036854775808}\n',
        b'{"key":-9223372036854775809}\n',
        b'{"key":NaN}\n',
        b'\xef\xbb\xbf{"key":1}\n',
    ]:
        fix = fixture(directory, f"row-{count}", [{"key": 0}])
        with (fix.work / "records.jsonl").open("ab") as stream:
            stream.write(raw)
        failure(app, fix, "line 2:")
        clean(fix)
        count += 1
    failure(app, fixture(directory, "string-type", [{"key": 3}], kind="string"), "line 1:")
    failure(app, fixture(directory, "row-cap", sample(), max_rows=2), "line 3: row limit exceeded")
    failure(app, fixture(directory, "mode", []), "invalid sorter mode", SORT_MODE="bad")
    fix = fixture(directory, "oversized-record", [{"key": 1, "padding": "x" * 300}], record_bytes=256)
    failure(app, fix, "physical record exceeds byte limit")
    fix = fixture(directory, "canonical-growth", [], record_bytes=256)
    (fix.work / "records.jsonl").write_bytes(b'{"key":1,"v":[' + b",".join([b"0.1"] * 20) + b"]}\n")
    failure(app, fix, "canonical record exceeds byte limit")
    fix = fixture(directory, "input-size", [])
    with (fix.work / "records.jsonl").open("wb") as stream:
        stream.truncate(1073741825)
    failure(app, fix, "inputs exceed 1 GiB")
    (fix.work / "records.jsonl").unlink()
    return count + 6


def paused(app: Application, fix: Fixture, point: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(SORT_PAUSE=point, SORT_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(30))
    if not ready or process.stdout.readline() != "PAUSED " + point + "\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    limits = Path(f"/proc/{process.pid}/limits").read_text()
    line = next(line for line in limits.splitlines() if line.startswith("Max address space"))
    assert line.split()[3] == str(fix.config["memory_mib"] * 1048576), line
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def recovery_cases(app: Application, directory: Path) -> int:
    points = ["run-open", "run-written", "runs-ready", "merge-open", "merge-written", "pass:1", "ready", "published"]
    for point in points:
        fix = fixture(directory, "fault-" + point.replace(":", "-"), sample())
        result = app.run(fix.work, fix.settings(SORT_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout, result
        clean(fix)
        if point == "published":
            outputs(fix, *reference(fix))
        else:
            assert not fix.output.exists()
            success(app, fix)
    for point in points:
        fix = fixture(directory, "kill-" + point.replace(":", "-"), sample())
        process = paused(app, fix, point)
        stop(process)
        remaining = sum(
            path.is_file() and path.name not in [".lock", "owner.json"] for path in fix.workspace.rglob("*")
        )
        assert remaining > 0
        if point == "published":
            result = app.run(fix.work, fix.settings(SORT_MODE="cleanup"))
            assert result.returncode == 0 and json.loads(result.stdout) == {"removed_files": remaining}, result
            outputs(fix, *reference(fix))
        else:
            assert not fix.output.exists()
            success(app, fix, recovered=remaining)
    fix = fixture(directory, "lock", sample())
    process = paused(app, fix, "runs-ready")
    try:
        before = {path.name: path.read_bytes() for path in fix.workspace.iterdir()}
        failure(app, fix)
        failure(app, fix, SORT_MODE="cleanup")
        assert before == {path.name: path.read_bytes() for path in fix.workspace.iterdir()}
        (fix.work / "continue").touch()
        output, error = process.communicate(timeout=30)
        assert process.returncode == 0 and not error
        assert json.loads(output) == outputs(fix, *reference(fix))
    finally:
        stop(process)
    # Cleanup never needs input contents and preserves already published output.
    saved = (fix.output / "sorted.jsonl").read_bytes()
    (fix.work / "records.jsonl").unlink()
    result = app.run(fix.work, fix.settings(SORT_MODE="cleanup"))
    assert result.returncode == 0 and json.loads(result.stdout) == {"removed_files": 0}
    assert (fix.output / "sorted.jsonl").read_bytes() == saved
    return len(points) * 2 + 3


def mutation_cases(app: Application, directory: Path) -> int:
    cases = ["run-bytes", "run-truncate", "run-symlink", "input", "configuration", "destination"]
    for name in cases:
        fix = fixture(directory, name, sample())
        point = "runs-ready" if name.startswith("run-") else "ready"
        process = paused(app, fix, point)
        try:
            if name.startswith("run-"):
                target = min(fix.workspace.glob("run-*.jsonl"))
                raw = target.read_bytes()
                if name == "run-bytes":
                    target.write_bytes(raw.replace(b"decimal", b"Decimal"))
                    assert target.stat().st_size == len(raw)
                elif name == "run-truncate":
                    target.write_bytes(raw[:-1])
                else:
                    target.unlink()
                    target.symlink_to(fix.work / "records.jsonl")
            elif name == "input":
                with (fix.work / "records.jsonl").open("ab") as stream:
                    stream.write(b"{}\n")
            elif name == "configuration":
                with fix.path.open("ab") as stream:
                    stream.write(b" ")
            else:
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=30)
            assert process.returncode == 2 and error and not output, (name, output, error)
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert not fix.output.exists()
            if name == "run-symlink":
                assert target.is_symlink()
                target.unlink()  # Test-owned corruption only; the application correctly refused it.
                result = app.run(fix.work, fix.settings(SORT_MODE="cleanup"))
                assert result.returncode == 0
            clean(fix)
        finally:
            stop(process)
    return len(cases)


def workspace_cases(app: Application, directory: Path) -> int:
    count = 0
    for name in ["file", "directory", "symlink", "dangling", "input", "config"]:
        fix = fixture(directory, "destination-" + name, sample())
        if name == "file":
            fix.output.write_bytes(b"keep")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"keep")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("records.jsonl" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = "records.jsonl" if name == "input" else "sort-job.json"
            fix.save()
        failure(app, fix, "output already exists")
        count += 1
    for name in ["input", "config", "workspace"]:
        fix = fixture(directory, "symlink-" + name, sample())
        path = {"input": fix.work / "records.jsonl", "config": fix.path, "workspace": fix.workspace}[name]
        target = fix.work / "real"
        if name == "workspace":
            target.mkdir()
        else:
            path.rename(target)
        path.symlink_to(target)
        before = target.read_bytes() if target.is_file() else None
        failure(app, fix)
        assert path.is_symlink()
        if before is not None:
            assert target.read_bytes() == before
        count += 1
    # A marker may be repaired after a crash during first initialization, but an
    # unknown/foreign file is never removed to make the workspace look empty.
    for name in [
        "empty-owner",
        "prefix-owner",
        "foreign-owner",
        "unknown",
        "hardlink-owner",
        "symlink-owner",
        "unknown-bundle",
        "symlink-run",
        "directory-run",
        "unowned",
        "hardlink-lock",
        "symlink-lock",
    ]:
        fix = fixture(directory, name, sample())
        if name != "unowned":
            result = app.run(fix.work, fix.settings(SORT_MODE="cleanup"))
            assert result.returncode == 0, result
        else:
            fix.workspace.mkdir()
        owner = fix.workspace / "owner.json"
        marker = owner.read_bytes() if owner.exists() else b""
        if name == "empty-owner":
            owner.write_bytes(b"")
        elif name == "prefix-owner":
            owner.write_bytes(marker[: len(marker) // 2])
        elif name == "foreign-owner":
            owner.write_bytes(b'{"belongs":"elsewhere"}')
        elif name in ["unknown", "unowned"]:
            (fix.workspace / "keep").write_bytes(b"do not remove")
        elif name == "hardlink-owner":
            os.link(owner, fix.work / "owner-link")
        elif name == "symlink-owner":
            owner.rename(fix.work / "owner-real")
            owner.symlink_to(fix.work / "owner-real")
        elif name == "unknown-bundle":
            (fix.workspace / "bundle").mkdir()
            (fix.workspace / "bundle/keep").write_bytes(b"keep")
        elif name == "symlink-run":
            (fix.workspace / "run-0.jsonl").symlink_to(fix.work / "records.jsonl")
        elif name == "directory-run":
            (fix.workspace / "run-0.jsonl").mkdir()
        elif name == "hardlink-lock":
            os.link(fix.workspace / ".lock", fix.work / "lock-link")
        elif name == "symlink-lock":
            (fix.workspace / ".lock").rename(fix.work / "lock-real")
            (fix.workspace / ".lock").symlink_to(fix.work / "lock-real")
        if name in ["empty-owner", "prefix-owner", "hardlink-lock"]:
            success(app, fix)
            if name == "hardlink-lock":
                assert (fix.work / "lock-link").read_bytes() == b""
                assert (fix.work / "lock-link").stat().st_ino == (fix.workspace / ".lock").stat().st_ino
        else:
            before = {
                str(path.relative_to(fix.work)): path.read_bytes() for path in fix.work.rglob("*") if path.is_file()
            }
            failure(app, fix)
            assert all((fix.work / path).read_bytes() == raw for path, raw in before.items())
        count += 1
    # Exercise the exact run-count boundary, followed by one record too many.
    rows = [{"key": i % 13, "id": i} for i in range(4096)]
    fix = fixture(directory, "run-cap", rows)
    assert success(app, fix)["initial_runs"] == 4096
    fix = fixture(directory, "run-overflow", rows + [{"key": 0}])
    failure(app, fix, "initial run count exceeds 4096")
    clean(fix)
    return count + 2


def large_file(app: Application, directory: Path) -> dict:
    fix = fixture(directory, "larger-than-memory", [], chunk_bytes=262144, record_bytes=32768, fan_in=8)
    # Shared immutable payloads keep the independent oracle small. It still
    # sorts the complete record list with CPython's built-in stable sort.
    padding = "x" * 16384
    records = [{"key": (index * 997) % 271, "id": index, "payload": padding} for index in range(10240)]
    input_path = fix.work / "records.jsonl"
    with input_path.open("wb") as stream:
        for row in records:
            stream.write((canonical(row) + "\n").encode())
    expected = hashlib.sha256()
    output_bytes = 0
    for row in sorted(records, key=lambda item: item["key"]):
        raw = (canonical(row) + "\n").encode()
        expected.update(raw)
        output_bytes += len(raw)
    input_bytes = input_path.stat().st_size
    assert input_bytes > fix.config["memory_mib"] * 1048576
    try:
        # /usr/bin/time observes this child only. RLIMIT_AS itself is applied by
        # the application, and separately read from /proc in every paused check.
        timed = Application(["/usr/bin/time", "-f", "%M", "-o", str(fix.work / "rss-kib"), *app.command], app.engine)
        result = timed.run(fix.work, fix.settings(), timeout=900)
        assert result.returncode == 0 and not result.stderr, result
        peak_rss = int((fix.work / "rss-kib").read_text()) * 1024
        assert 0 < peak_rss < fix.config["memory_mib"] * 1048576, peak_rss
        observed = hashlib.sha256()
        count = 0
        with (fix.output / "sorted.jsonl").open("rb") as stream:
            for raw in stream:
                observed.update(raw)
                count += 1
        assert count == len(records) and observed.digest() == expected.digest()
        report = json.loads(result.stdout)
        assert report == json.loads((fix.output / "report.json").read_bytes())
        assert report["rows"] == len(records) and report["output_bytes"] == output_bytes
        assert report["output_sha256"] == expected.hexdigest() and report["memory_limit_bytes"] == 134217728
        assert report["peak_batch_bytes"] <= 262144 and report["initial_runs"] > 500 and report["merge_passes"] >= 3
        assert report["inputs"] == [{"input_index": 0, "rows": len(records), "bytes": input_bytes}]
        clean(fix)
        measured = {
            "engine": app.engine,
            "peak_rss_bytes": peak_rss,
            "input_bytes": input_bytes,
            "address_space_limit_bytes": 134217728,
            "output_sha256": expected.hexdigest(),
        }
        (directory / "large-file-measurement.json").write_text(json.dumps(measured, indent=2) + "\n")
        return {
            "rows": len(records),
            "input_bytes": input_bytes,
            "limit_bytes": 134217728,
            "output_sha256": expected.hexdigest(),
            "peak_rss_below_limit": True,
            "initial_runs": report["initial_runs"],
            "merge_passes": report["merge_passes"],
        }
    finally:
        # These are this check's generated 160 MiB fixtures, never user data.
        # Retain measurements without accumulating hundreds of MiB per engine.
        shutil.rmtree(fix.work)


def check(app: Application, directory: Path) -> dict:
    traces, digest = valid_cases(app, directory / "valid")
    print(app.engine + " external sort: reference cases passed", flush=True)
    invalid = invalid_cases(app, directory / "invalid")
    recovery = recovery_cases(app, directory / "recovery")
    mutations = mutation_cases(app, directory / "mutation")
    workspaces = workspace_cases(app, directory / "workspace")
    print(app.engine + " external sort: rejection and recovery checks passed", flush=True)
    large = large_file(app, directory)
    print(app.engine + " external sort: larger-than-memory dataset passed", flush=True)
    return {
        "reference_cases": traces,
        "results_sha256": digest,
        "invalid_inputs": invalid,
        "recovery_cases": recovery,
        "mutation_cases": mutations,
        "workspace_cases": workspaces,
        "large_file": large,
    }
