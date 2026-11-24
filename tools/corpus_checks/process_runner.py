"""Independent native command fixtures, output assertions, suite reports and cleanup evidence."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import queue
import random
import re
import resource
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .process_fixture import gone, ready
from .runner_fixture import build_runner_fixture


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expectation(data: bytes | None = b"") -> dict:
    return (
        {"mode": "ignore", "value": ""}
        if data is None
        else {"mode": "base64", "value": base64.b64encode(data).decode()}
    )


def case(
    name: str,
    arguments: list[str],
    data: bytes = b"",
    output: bytes | None = b"",
    error: bytes | None = b"",
    code: int = 0,
    timeout: int = 2000,
    limit: int = 65536,
) -> dict:
    return {
        "id": name,
        "argv": ["FIXTURE", *arguments],
        "cwd": ".",
        "environment": {},
        "stdin": {"encoding": "base64", "data": base64.b64encode(data).decode()},
        "timeout_ms": timeout,
        "max_output": limit,
        "expect": {"exit_code": code, "stdout": expectation(output), "stderr": expectation(error)},
    }


@dataclass
class Fixture:
    root: Path
    helper: Path
    config: dict

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def source(self) -> Path:
        return self.root / "suite.json"

    @property
    def settings(self) -> dict[str, str]:
        return {"RUNNER_CONFIG": str(self.source)}

    def save(self) -> None:
        self.source.write_bytes(canonical(self.config))
        return  # noqa: PLR1711 - explicit repository returns


def fixture(root: Path, helper: Path, cases: list[dict]) -> Fixture:
    root.mkdir(parents=True)
    cases = copy.deepcopy(cases)
    for row in cases:
        if row["argv"] and row["argv"][0] == "FIXTURE":
            row["argv"][0] = os.path.relpath(helper, root)
    fix = Fixture(root, helper, {"version": 1, "output": "output", "environment": {}, "tests": cases})
    fix.save()
    return fix


def matches(data: bytes, rule: dict) -> bool:
    mode, value = rule["mode"], rule["value"]
    if mode == "ignore":
        return True
    if mode == "utf8":
        return data == value.encode()
    if mode == "base64":
        return data == base64.b64decode(value)
    if mode == "contains":
        return value.encode() in data
    try:
        return re.fullmatch(value, data.decode(), re.ASCII) is not None
    except UnicodeDecodeError:
        return False


def stream(name: str, data: bytes) -> dict:
    try:
        preview = data.decode()[:512]
    except UnicodeDecodeError:
        preview = None
    return {"file": name, "bytes": len(data), "sha256": digest(data), "utf8_preview": preview}


def outcome(kind: str = "exited", code: int | None = 0, signum: int = 0) -> dict:
    return {"kind": kind, "returncode": code, "interrupt_signal": signum}


def verify(fix: Fixture, expected: list[tuple[dict, bytes, bytes] | None]) -> dict:
    records = []
    files: dict[str, bytes] = {}
    signum = 0
    for row, observed in zip(fix.config["tests"], expected, strict=True):
        name = row["id"]
        if observed is None:
            records.append(
                {
                    "id": name,
                    "status": "skipped",
                    "outcome": None,
                    "failed_checks": [],
                    "error": "suite interrupted",
                    "argv": row["argv"],
                    "cwd": row["cwd"],
                    "stdout": None,
                    "stderr": None,
                }
            )
            continue
        meta, stdout, stderr = observed
        failures = [] if meta["kind"] == "exited" else [meta["kind"]]
        if meta["returncode"] != row["expect"]["exit_code"]:
            failures.append("exit_code")
        for channel, data in [("stdout", stdout), ("stderr", stderr)]:
            if not matches(data, row["expect"][channel]):
                failures.append(channel)
            files[name + "." + channel] = data
        signum = max(signum, meta["interrupt_signal"])
        records.append(
            {
                "id": name,
                "status": "failed" if failures else "passed",
                "outcome": meta,
                "failed_checks": failures,
                "error": "",
                "argv": row["argv"],
                "cwd": row["cwd"],
                "stdout": stream(name + ".stdout", stdout),
                "stderr": stream(name + ".stderr", stderr),
            }
        )
    summary = {
        "total": len(records),
        "executed": sum(row["status"] != "skipped" for row in records),
        "passed": sum(row["status"] == "passed" for row in records),
        "failed": sum(row["status"] == "failed" for row in records),
        "skipped": sum(row["status"] == "skipped" for row in records),
        "captured_bytes": sum(len(data) for data in files.values()),
        "interrupt_signal": signum,
    }
    status = "interrupted" if signum else ("failed" if summary["failed"] else "passed")
    report = {"version": 1, "status": status, "summary": summary, "tests": records}
    assert (fix.output / "report.json").read_bytes() == canonical(report) + b"\n"
    for name, data in files.items():
        assert (fix.output / name).read_bytes() == data
    text = (fix.output / "report.txt").read_text()
    assert text.startswith("Process test runner: " + status + "\n")
    for record in records:
        assert f'{record["id"]}: {record["status"]} ' in text
    manifest = json.loads((fix.output / "manifest.json").read_bytes())
    assert set(manifest) == set(files) | {"report.json", "report.txt"}
    assert {p.name for p in fix.output.iterdir()} == set(manifest) | {"manifest.json"}
    for name, entry in manifest.items():
        data = (fix.output / name).read_bytes()
        assert entry == {"bytes": len(data), "sha256": digest(data)}
    return report


def run(app: Application, fix: Fixture, expected: list[tuple[dict, bytes, bytes] | None]) -> dict:
    result = app.run(fix.root, fix.settings, timeout=30)
    report = verify(fix, expected)
    code = (
        128 + report["summary"]["interrupt_signal"]
        if report["status"] == "interrupted"
        else int(report["status"] == "failed")
    )
    assert result.returncode == code and not result.stderr, (result.returncode, result.stdout, result.stderr)
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[-1] == report["summary"]
    assert events[:-1] == [
        {"id": row["id"], "status": row["status"], "outcome": row["outcome"]}
        for row in report["tests"]
        if row["status"] != "skipped"
    ]
    return report


def mixed(helper: Path, root: Path) -> tuple[Fixture, list[tuple[dict, bytes, bytes]]]:
    cases, expected = [], []

    def add(row: dict, data: bytes = b"", error: bytes = b"", kind: str = "exited", code: int | None = 0) -> None:
        cases.append(row)
        expected.append((outcome(kind, code), data, error))
        return  # noqa: PLR1711 - explicit repository returns

    add(case("binary", ["copy"], b"hello\0\xff", b"hello\0\xff"), b"hello\0\xff")
    args = ["", "a b", "$HOME", "*", "世界😀"]
    data = b"".join(value.encode().hex().encode() + b"\n" for value in args)
    add(case("arguments", ["args", *args], output=data), data)
    data = bytes(range(256))
    add(
        case("expected-nonzero", ["emit", "256", "17", "7"], output=data, error=b"e" * 17, code=7),
        data,
        b"e" * 17,
        code=7,
    )
    add(case("bad-exit", ["exit", "8"]), code=8)
    add(case("bad-stdout", ["copy"], b"actual", b"expected"), b"actual")
    add(case("bad-stderr", ["emit", "0", "5"], error=b"wrong"), error=b"e" * 5)
    row = case("regular-expression", ["copy"], b"hello\n")
    row["expect"]["stdout"] = {"mode": "regex", "value": "hello\\n"}
    add(row, b"hello\n")
    row = case("invalid-utf8-regex", ["copy"], b"\xff")
    row["expect"]["stdout"] = {"mode": "regex", "value": ".*"}
    add(row, b"\xff")
    row = case("contains", ["copy"], b"\xff needle \0")
    row["expect"]["stdout"] = {"mode": "contains", "value": "needle"}
    add(row, b"\xff needle \0")
    row = case("environment", ["env", "ONLY"], output="café".encode())
    row["environment"] = {"ONLY": "café"}
    add(row, "café".encode())
    add(case("no-inheritance", ["env", "HOME"], output=b"<unset>"), b"<unset>")
    add(case("directory", ["cwd"], output=str(root).encode()), str(root).encode())
    row = case("missing", [])
    row["argv"] = ["missing-executable"]
    add(row, kind="spawn_error", code=None)
    add(case("signal-exit", ["signal", "15"], code=-15), code=-15)
    add(
        case("timeout", ["prefix-hold", "timeout.pids"], output=b"ready\0\xff", error=b"waiting", timeout=500),
        b"ready\0\xff",
        b"waiting",
        "timeout",
        None,
    )
    add(
        case("output-limit", ["flood-hold", "flood.pids"], output=b"x" * 17, limit=17),
        b"x" * 17,
        kind="output_limit",
        code=None,
    )
    add(case("orphan", ["orphan", "orphan.pids"]))
    add(case("continued", ["copy"], b"continued", b"continued"), b"continued")
    fix = fixture(root, helper, cases)
    fix.config["environment"] = {"ONLY": "default"}
    fix.save()
    return fix, expected


def semantics(app: Application, directory: Path, helper: Path) -> dict:
    fix, expected = mixed(helper, directory / "mixed")
    report = run(app, fix, expected)
    assert report["summary"]["failed"] == 7
    for name in ["timeout", "flood", "orphan"]:
        gone(fix.root / (name + ".pids"), minimum=2)
    run(app, fixture(directory / "empty", helper, []), [])
    generator = random.Random(91091)
    checks = []
    for batch in range(2):
        cases, expected = [], []
        for index in range(32):
            data = bytes(generator.randrange(256) for _ in range(generator.randrange(4096)))
            cases.append(case(f"job{index}", ["copy"], data, data))
            expected.append((outcome(), data, b""))
        fix = fixture(directory / f"generated-{batch}", helper, cases)
        run(app, fix, expected)
        checks.append(digest(b"".join(value[1] for value in expected)))
    return {
        "explicit_tests": 18,
        "expected_failures": 7,
        "generated_tests": 64,
        "empty_suite": True,
        "sha256": digest(canonical(checks)),
    }


def rejected(app: Application, fix: Fixture, **settings: str) -> None:
    before = {p.name: p.read_bytes() for p in fix.output.iterdir()} if fix.output.is_dir() else None
    result = app.run(fix.root, dict(fix.settings, **settings), timeout=15)
    assert result.returncode == 2 and result.stderr, (result.returncode, result.stdout, result.stderr)
    if before is None:
        assert not fix.output.exists()
    else:
        assert before == {p.name: p.read_bytes() for p in fix.output.iterdir()}
    assert not (fix.root / "marker.pids").exists()
    return  # noqa: PLR1711 - explicit repository returns


def invalid(app: Application, directory: Path, helper: Path) -> dict:
    base = case("valid", ["record", "marker.pids"])
    changes = []
    for key, values in {
        "id": ["", "a" * 33, "bad space", "é", True],
        "argv": [[], [], [""], ["x\0y"], [7]],
        "cwd": ["", "missing", str(helper), 1],
        "environment": [{"BAD=KEY": "x"}, {"A": 3}, {"A": "\0"}],
        "timeout_ms": [0, 60001, True, 1.0],
        "max_output": [-1, 1048577, True, 1.0],
        "stdin": [
            {"encoding": "wrong", "data": ""},
            {"encoding": "base64", "data": "AB=="},
            {"encoding": "utf8", "data": 3},
        ],
    }.items():
        changes.extend((key, value) for value in values)
    for index, (key, value) in enumerate(changes):
        row = copy.deepcopy(base)
        row[key] = value
        fix = fixture(directory / f"case-{index}", helper, [row])
        rejected(app, fix)
    for index, rule in enumerate(
        [
            {"mode": "unknown", "value": ""},
            {"mode": "ignore", "value": "x"},
            {"mode": "regex", "value": "("},
            {"mode": "regex", "value": "(?=x)"},
            {"mode": "base64", "value": "!"},
            {"mode": "utf8", "value": 1},
            {"mode": "utf8", "value": "x" * 65537},
            {"mode": "regex", "value": "x" * 4097},
        ]
    ):
        row = copy.deepcopy(base)
        row["expect"]["stdout"] = rule
        rejected(app, fixture(directory / f"rule-{index}", helper, [row]))
    for index, code in enumerate([-65, 256, True, 0.0]):
        row = copy.deepcopy(base)
        row["expect"]["exit_code"] = code
        rejected(app, fixture(directory / f"exit-{index}", helper, [row]))
    configurations = [[], [base, base], [dict(base, id=f"j{i}") for i in range(33)]]
    for index, cases in enumerate(configurations):
        fix = fixture(directory / f"whole-{index}", helper, cases)
        if index == 0:
            fix.config["version"] = True
            fix.save()
        rejected(app, fix)
    for index, data in enumerate([b"", b"{", b"[]", b"null", b"\xff", b'{"version":1,"version":1}']):
        fix = fixture(directory / f"json-{index}", helper, [base])
        fix.source.write_bytes(data)
        rejected(app, fix)
    for index, key in enumerate(["argv", "cwd", "environment", "stdin", "expect"]):
        fix = fixture(directory / f"missing-{index}", helper, [base])
        del fix.config["tests"][0][key]
        fix.save()
        rejected(app, fix)
    for index, (key, amount) in enumerate([("timeout_ms", 60000), ("max_output", 1048576)]):
        rows = [dict(base, id=f"job{i}", **{key: amount}) for i in range(3 if index == 0 else 9)]
        rejected(app, fixture(directory / f"budget-{index}", helper, rows))
    late = fixture(directory / "late-invalid", helper, [base, dict(base, id="later")])
    late.config["tests"][-1]["stdin"]["encoding"] = "invalid"
    late.save()
    rejected(app, late)
    return {
        "invalid_fields": len(changes),
        "output_expectations": 8,
        "exit_codes": 4,
        "whole_suites": 3,
        "malformed_json": 6,
        "missing_fields": 5,
        "aggregate_budgets": 2,
        "no_commands_before_complete_validation": True,
    }


def interruptions(app: Application, directory: Path, helper: Path) -> dict:
    for number in [signal.SIGINT, signal.SIGTERM]:
        cases = [
            case("active", ["prefix-hold", "active.pids"], output=b"ready\0\xff", error=b"waiting", timeout=10000),
            case("never", ["record", "marker.pids"]),
            case("later", ["exit", "0"]),
        ]
        fix = fixture(directory / str(number), helper, cases)
        process = subprocess.Popen(
            app.command,
            cwd=fix.root,
            env=app.environment(fix.settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            ready(fix.root / "active.pids", process)
            time.sleep(0.05)
            os.kill(process.pid, number)
            output, error = process.communicate(timeout=10)
            assert process.returncode == 128 + number and not error, (output, error)
            report = verify(fix, [(outcome("interrupted", None, number), b"ready\0\xff", b"waiting"), None, None])
            assert report["summary"]["skipped"] == 2
            assert not (fix.root / "marker.pids").exists()
            gone(fix.root / "active.pids", minimum=2)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    return {
        "parent_signals": [2, 15],
        "partial_capture_reported": True,
        "remaining_tests_skipped": True,
        "owned_groups_terminated": True,
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, RUNNER_PAUSE=label, RUNNER_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def consume() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return  # noqa: PLR1711 - explicit repository returns

    threading.Thread(target=consume, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=20)
            assert line is not None, "exited before publication hook"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, directory: Path, helper: Path) -> dict:
    rows = [case("pass", ["copy"], b"captured", b"captured")]
    expected = [(outcome(), b"captured", b"")]
    for action in ["fault", "kill"]:
        for label in ["staged", "published"]:
            fix = fixture(directory / (action + "-" + label), helper, rows)
            if action == "fault":
                result = app.run(fix.root, dict(fix.settings, RUNNER_FAULT=label))
                assert result.returncode == 2
            else:
                process = paused(app, fix, label)
                process.kill()
                assert process.wait(timeout=5) < 0
            assert fix.output.exists() == (label == "published")
            if label == "published":
                verify(fix, expected)
                rejected(app, fix)
            else:
                run(app, fix, expected)
    fix = fixture(directory / "changed-input", helper, rows)
    process = paused(app, fix, "staged")
    try:
        with fix.source.open("ab") as output:
            output.write(b" ")
        (fix.root / "release").touch()
        assert process.wait(timeout=10) == 2
        assert not fix.output.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
    fix = fixture(directory / "race", helper, rows)
    contenders = [
        subprocess.Popen(
            app.command,
            cwd=fix.root,
            env=app.environment(fix.settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    codes = []
    try:
        for process in contenders:
            process.communicate(timeout=20)
            codes.append(process.returncode)
    finally:
        for process in contenders:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    assert codes.count(0) == 1 and set(codes) <= {0, 2}, codes
    verify(fix, expected)
    return {
        "fault_and_kill_boundaries": 4,
        "changed_input_rejected": True,
        "concurrent_publishers": 8,
        "successful_publications": 1,
    }


def limits(app: Application, directory: Path, helper: Path) -> dict:
    rows = [
        case("j" + str(index).ljust(31, "x"), ["emit", "262144", "0"], output=None, limit=262144) for index in range(32)
    ]
    fix = fixture(directory / "capture-maximum", helper, rows)

    def memory_limit() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return  # noqa: PLR1711 - explicit repository returns

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=120,
        preexec_fn=memory_limit,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = bytes(range(256)) * 1024
    report = verify(fix, [(outcome(), data, b"")] * 32)
    assert report["summary"]["captured_bytes"] == 8388608
    data = bytes(range(256)) * 4096
    full = fixture(directory / "stdin-maximum", helper, [case("copy", ["copy"], data, None, limit=1048576)])
    full.source.write_bytes(full.source.read_bytes().ljust(2097152, b" "))
    run(app, full, [(outcome(), data, b"")])
    for index, rows in enumerate(
        [
            [case("wide", ["exit", "0", *([""] * 125)], limit=0)],
            [
                case("deadline1", ["exit", "0"], timeout=60000, limit=0),
                case("deadline2", ["exit", "0"], timeout=60000, limit=0),
            ],
        ]
    ):
        run(app, fixture(directory / f"other-{index}", helper, rows), [(outcome(), b"", b"")] * len(rows))
    for name in ["config-over", "input-over", "total-input-over"]:
        row = case("record", ["record", "marker.pids"])
        fix = fixture(directory / name, helper, [row])
        if name == "config-over":
            fix.source.write_bytes(fix.source.read_bytes().ljust(2097153, b" "))
        elif name == "input-over":
            fix.config["tests"][0]["stdin"] = {"encoding": "utf8", "data": "x" * 1048577}
            fix.save()
        else:
            fix.config["tests"][0]["stdin"] = {"encoding": "utf8", "data": "x" * 524289}
            fix.config["tests"].append(dict(copy.deepcopy(fix.config["tests"][0]), id="second"))
            fix.save()
        rejected(app, fix)
    return {
        "tests": 32,
        "id_characters": 32,
        "arguments": 128,
        "per_command_capture": 1048576,
        "total_capture": 8388608,
        "stdin_bytes": 1048576,
        "configuration_bytes": 2097152,
        "total_timeout_ms": 120000,
        "memory_limit": 268435456,
        "maximum_capture_sha256": digest(data),
    }


def filesystem(app: Application, directory: Path, helper: Path) -> dict:
    names = [
        "source-symlink",
        "source-hardlink",
        "source-fifo",
        "source-unreadable",
        "output-symlink",
        "output-file",
        "output-fifo",
        "output-existing",
    ]
    for name in names:
        fix = fixture(directory / name, helper, [case("marker", ["record", "marker.pids"])])
        target = fix.root / "untouched"
        target.write_bytes(b"preserve this data")
        if name.startswith("source-"):
            if name == "source-unreadable":
                fix.source.chmod(0)
            else:
                fix.source.unlink()
                if name == "source-symlink":
                    fix.source.symlink_to(target)
                elif name == "source-hardlink":
                    os.link(target, fix.source)
                else:
                    os.mkfifo(fix.source)
            guarded = fix.source
        else:
            if name == "output-symlink":
                fix.output.symlink_to(target)
            elif name == "output-file":
                fix.output.write_bytes(b"keep this output")
            elif name == "output-fifo":
                os.mkfifo(fix.output)
            else:
                fix.output.mkdir()
                (fix.output / "sentinel").write_bytes(b"keep this directory")
            guarded = fix.output
        before = guarded.lstat()
        try:
            result = app.run(fix.root, fix.settings, timeout=10)
            assert result.returncode == 2 and result.stderr and not result.stdout
            assert guarded.lstat().st_ino == before.st_ino and guarded.lstat().st_mode == before.st_mode
            assert not (fix.root / "marker.pids").exists()
            assert target.read_bytes() == b"preserve this data"
        finally:
            if name == "source-unreadable":
                fix.source.chmod(0o600)
    fix = fixture(directory / "publication-permission", helper, [case("pass", ["copy"], b"data", b"data")])
    assert os.getuid() != 0, "permission checks require an ordinary user"
    fix.root.chmod(0o500)
    try:
        result = app.run(fix.root, fix.settings, timeout=10)
        assert result.returncode == 2 and result.stderr and not fix.output.exists()
        assert json.loads(result.stdout)["status"] == "passed"
    finally:
        fix.root.chmod(0o700)
    run(app, fix, [(outcome(), b"data", b"")])
    return {"alias_and_control_cases": len(names), "publication_permission_failure_recovered": True}


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    helper = build_runner_fixture(directory)
    return {
        "semantics": semantics(app, directory / "semantics", helper),
        "invalid": invalid(app, directory / "invalid", helper),
        "interruptions": interruptions(app, directory / "interruptions", helper),
        "publication": publication(app, directory / "publication", helper),
        "limits": limits(app, directory / "limits", helper),
        "filesystem": filesystem(app, directory / "filesystem", helper),
        "independent_native_fixture_and_report_oracle": True,
    }
