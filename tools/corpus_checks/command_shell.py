"""Independent quoting, native argv/pipe fixtures, failure recovery and lifecycle checks for 076."""

# ruff: noqa: PLR1711 - explicit repository returns
from __future__ import annotations

import hashlib
import json
import os
import random
import shlex
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical
from .process_fixture import build_fixture, gone, ready


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "shell-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "run") -> dict:
        return {"SHELL_CONFIG": str(self.path), "SHELL_MODE": mode}


def job(name: str, command: str, source: str = "", **environment: str) -> dict:
    return {"name": name, "command": command, "input": source, "environment": environment}


def fixture(directory: Path, name: str, helper: Path, initial_jobs: list[dict], **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(
        work,
        {
            "version": 1,
            "cwd": ".",
            "output": "captured",
            "environment": {"PATH": str(helper.parent), "LANG": "C.UTF-8"},
            "timeout_ms": 3000,
            "max_output": 1048576,
            "pipefail": True,
            "jobs": initial_jobs,
            **changes,
        },
    )
    fix.save()
    return fix


def captured(fix: Fixture, report: dict) -> dict[str, bytes]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    expected = {"report.json", "job.json", "manifest.json"}
    size = 0
    for row in report["jobs"]:
        if row["state"] == "finished":
            expected.add(row["stdout"])
            expected.update(row["stderr"])
            size += len(files[row["stdout"]]) + sum(len(files[name]) for name in row["stderr"])
    assert set(files) == expected
    assert files["job.json"] == fix.path.read_bytes()
    assert files["report.json"] == (canonical(report) + "\n").encode()
    assert size == report["captured_bytes"]
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in files.items()
            if name != "manifest.json"
        },
    }
    assert not list(fix.output.parent.glob(".shell-*"))
    return files


def run(app: Application, fix: Fixture, code: int = 0) -> tuple[dict, dict[str, bytes]]:
    result = app.run(fix.work, fix.settings(), timeout=90)
    assert result.returncode == code and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert report["status"] == code and result.stdout == canonical(report) + "\n"
    return report, captured(fix, report)


def quoting(app: Application, directory: Path, helper: Path) -> dict:
    fragments = [
        "''",
        '""',
        "plain",
        "'two words'",
        '"two words"',
        "two\\ words",
        "'x'\"y\"z",
        "'世界😀'",
        "'|'",
        '"|"',
        "\\|",
        "'\\'",
        '"a\\qb"',
        '"a\\\\b"',
        "'a\"b'",
        '"a\\"b"',
        "'$HOME'",
        "'*?[abc]'",
        "'#literal'",
        "'semi; <&>`'",
        "'line\nnext'",
        '"tab\there"',
    ]
    rng = random.Random(760076)
    all_arguments = []
    for batch in range(4):
        jobs = []
        expected = []
        for index in range(32):
            command = "process-fixture args " + " ".join(rng.choices(fragments, k=rng.randrange(1, 12)))
            arguments = shlex.split(command, comments=False, posix=True)[2:]
            jobs.append(job("q" + str(index), command))
            expected.append(arguments)
        fix = fixture(directory, "quotes-" + str(batch), helper, jobs)
        plan = app.run(fix.work, fix.settings("plan"))
        assert plan.returncode == 0 and not plan.stderr and not fix.output.exists(), plan
        details = json.loads(plan.stdout)
        assert details["cwd"] == str(fix.work)
        for row, arguments in zip(details["jobs"], expected, strict=True):
            assert row["argv"] == [[str(helper), "args", *arguments]]
            assert row["environment"] == fix.config["environment"] and row["input_bytes"] == 0
        report, files = run(app, fix)
        for row, arguments in zip(report["jobs"], expected, strict=True):
            assert row["stages"] == [0] and row["status"] == 0
            assert files[row["stdout"]] == "".join(value.encode().hex() + "\n" for value in arguments).encode()
            assert files[row["stderr"][0]] == b""
        all_arguments.extend(expected)
    fix = fixture(directory, "max-argv", helper, [job("args", "process-fixture args " + "'' " * 126)])
    report, files = run(app, fix)
    assert files["args.stdout"] == b"\n" * 126 and report["jobs"][0]["stages"] == [0]
    return {
        "shlex_generated_commands": len(all_arguments),
        "arguments_sha256": hashlib.sha256(canonical(all_arguments).encode()).hexdigest(),
        "maximum_arguments": 128,
    }


def streams(app: Application, directory: Path, helper: Path) -> dict:
    commands = [
        job("pipeline", "process-fixture emit 1048576 131072 | process-fixture copy | process-fixture copy"),
        job("binary", "process-fixture copy | process-fixture upper", "input.bin"),
        job("eight", " | ".join(["process-fixture copy"] * 8), "input.bin"),
        job("override", "process-fixture env LABEL", LABEL="世界 value"),
        job("absent", "process-fixture env HOME"),
        job("cwd", "process-fixture cwd"),
        job("early", "process-fixture emit 1048576 0 | process-fixture take 16"),
        job("failed", "process-fixture exit 7 | process-fixture exit 3 | process-fixture exit 0"),
        job("signal", "process-fixture signal 15"),
        job("last", shlex.quote(str(helper)) + " copy", "input.bin"),
    ]
    fix = fixture(directory, "streams", helper, commands, max_output=1179648)
    data = bytes(range(256)) * 1024
    (fix.work / "input.bin").write_bytes(data)
    report, files = run(app, fix)
    assert files["pipeline.stdout"] == bytes(range(256)) * 4096
    assert files["pipeline.0.stderr"] == b"e" * 131072
    assert files["binary.stdout"] == data.upper() and files["eight.stdout"] == data and files["last.stdout"] == data
    assert files["override.stdout"] == "世界 value".encode() and files["absent.stdout"] == b"<unset>"
    assert files["cwd.stdout"] == str(fix.work).encode()
    assert [row["stages"] for row in report["jobs"]] == [
        [0, 0, 0],
        [0, 0],
        [0] * 8,
        [0],
        [0],
        [0],
        [-13, 0],
        [7, 3, 0],
        [-15],
        [0],
    ]
    assert [row["status"] for row in report["jobs"]] == [0, 0, 0, 0, 0, 0, 141, 3, 143, 0]
    fix = fixture(
        directory,
        "last-status",
        helper,
        [job("status", "process-fixture exit 7 | process-fixture exit 0")],
        pipefail=False,
        max_output=0,
    )
    report, _files = run(app, fix)
    assert report["jobs"][0]["stages"] == [7, 0] and report["jobs"][0]["status"] == 0
    fix = fixture(directory, "exit-status", helper, [job("status", "process-fixture exit 9")], max_output=0)
    report, _files = run(app, fix, 9)
    assert report["jobs"][0]["stages"] == [9]
    return {
        "stream_cases": len(commands) + 2,
        "binary_bytes": len(data),
        "concurrent_stdout_bytes": 1048576,
        "concurrent_stderr_bytes": 131072,
        "pipefail_and_signal_statuses": True,
    }


def recovery(app: Application, directory: Path, helper: Path) -> dict:
    fix = fixture(
        directory,
        "recovery",
        helper,
        [
            job("missing", "missing-program"),
            job("spawn", "process-fixture hold spawn.pids | ./bad-executable"),
            job("timeout", "process-fixture hold timeout.pids"),
            job("output", "process-fixture emit 20000 20000"),
            job("orphan", "process-fixture orphan orphan.pids"),
            job("failed-pipeline", "process-fixture hold failed-pipeline.pids | process-fixture exit 7"),
            job("recovered", "process-fixture args recovered"),
        ],
        timeout_ms=250,
        max_output=1024,
    )
    (fix.work / "bad-executable").write_text("not an executable image")
    (fix.work / "bad-executable").chmod(0o700)
    report, files = run(app, fix)
    assert [row["status"] for row in report["jobs"]] == [125, 125, 124, 125, 0, 124, 0]
    assert [row["error"] for row in report["jobs"][:4]] == [
        "executable not found: missing-program",
        "pipeline spawn failed at stage 1",
        "pipeline deadline exceeded",
        "pipeline output limit exceeded",
    ]
    assert files["recovered.stdout"] == b"7265636f7665726564\n"
    for name, minimum in [("spawn", 0), ("timeout", 2), ("orphan", 2), ("failed-pipeline", 2)]:
        gone(fix.work / (name + ".pids"), minimum=minimum)
    for number in [signal.SIGINT, signal.SIGTERM]:
        fix = fixture(
            directory,
            "signal-" + str(number),
            helper,
            [
                job("hold", "process-fixture hold signal.pids"),
                job("skipped", "process-fixture record should-not-exist"),
            ],
            timeout_ms=10000,
            max_output=0,
        )
        process = subprocess.Popen(
            app.command,
            cwd=fix.work,
            env=app.environment(fix.settings()),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            ready(fix.work / "signal.pids", process)
            os.kill(process.pid, number)
            output, error = process.communicate(timeout=5)
            assert process.returncode == 128 + number and not error
            report = json.loads(output)
            assert report["cancelled"] and report["jobs"] == [
                {
                    "name": "hold",
                    "state": "error",
                    "status": 128 + number,
                    "error": f"pipeline interrupted by signal {number}",
                },
                {"name": "skipped", "state": "skipped", "status": 128 + number},
            ]
            captured(fix, report)
            assert not (fix.work / "should-not-exist").exists()
            gone(fix.work / "signal.pids", minimum=2)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    return {"recovered_failures": 5, "orphan_cleanup": True, "interrupts": [2, 15], "cancelled_jobs_not_started": True}


def invalid(app: Application, directory: Path, helper: Path) -> dict:
    cases = []
    commands = [
        "",
        " ",
        "|a",
        "a|",
        "a||b",
        "a | | b",
        "'unterminated",
        '"unterminated',
        "a\\",
        "a\x00b",
        "a;b",
        "a&b",
        "a>b",
        "a<b",
        "`a`",
        "a\nb",
        "a\rb",
        "|".join(["a"] * 9),
        "a " + "'' " * 128,
        "x" * 8193,
    ]
    for command in commands:
        cases.append({"jobs": [job("first", "process-fixture record unexpected"), job("invalid", command)]})
    cases += [
        {"jobs": []},
        {"jobs": [job("a" + str(i), "process-fixture copy") for i in range(65)]},
        {"jobs": [job("same", "a"), job("same", "b")]},
    ]
    for name in ["", "../escape", "a/b", "世界", "x" * 65, "1first"]:
        cases.append({"jobs": [job(name, "a")]})
    for change in [
        {"extra": True},
        {"version": 2},
        {"version": True},
        {"pipefail": "yes"},
        {"timeout_ms": 0},
        {"timeout_ms": 60001},
        {"max_output": -1},
        {"max_output": 16777217},
        {"cwd": "missing"},
        {"cwd": "shell-job.json"},
        {"output": ""},
        {"environment": []},
        {"environment": {"": "value"}},
        {"environment": {"NAME": 1}},
        {"environment": {"NAME": "\0"}},
        {"environment": {"A" * 129: ""}},
        {"environment": {"0bad": ""}},
        {"environment": {"世界": ""}},
        {"environment": {"A": "x" * 65534}},
        {"environment": {"E" + str(i): "" for i in range(257)}},
    ]:
        cases.append(change)
    cases += [
        {"jobs": [dict(job("bad", "a"), extra=True)]},
        {"jobs": [job("bad", "a", "absent.bin")]},
        {"jobs": [job("bad", "a", "oversized.bin")]},
        {"jobs": [dict(job("bad", "a"), environment={"N": "\0"})]},
        {"jobs": [dict(job("bad", "a"), input=None)]},
    ]
    for index, changes in enumerate(cases):
        fix = fixture(
            directory,
            "invalid-" + str(index),
            helper,
            [job("unexpected", "process-fixture record unexpected")],
            **changes,
        )
        if any(row.get("input") == "oversized.bin" for row in fix.config["jobs"]):
            with (fix.work / "oversized.bin").open("wb") as stream:
                stream.truncate(16777217)
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and result.stderr and not result.stdout, (index, changes, result)
        assert not (fix.work / "captured").exists() and not (fix.work / "unexpected").exists()
        assert not list(fix.work.glob(".shell-*"))
    for mode in ["wrong", ""]:
        fix = fixture(directory, "mode-" + str(len(mode)), helper, [job("valid", "process-fixture copy")])
        result = app.run(fix.work, fix.settings(mode))
        assert result.returncode == 2 and "invalid shell mode" in result.stderr and not fix.output.exists()
    for index, environment in enumerate(
        [
            {},
            {"PATH": ""},
            {"PATH": "."},
            {"PATH": str(helper.parent) + ":"},
            {"PATH": "/missing"},
            {"PATH": ":".join([str(helper.parent)] * 33)},
        ]
    ):
        fix = fixture(
            directory, "lookup-" + str(index), helper, [job("bad", "process-fixture copy")], environment=environment
        )
        report, _files = run(app, fix, 125)
        assert report["jobs"][0]["state"] == "error"
    for kind in ["file", "directory", "symlink", "dangling"]:
        fix = fixture(directory, "exists-" + kind, helper, [job("bad", "process-fixture record unexpected")])
        if kind == "file":
            fix.output.write_text("preserve")
        elif kind == "directory":
            fix.output.mkdir()
        else:
            fix.output.symlink_to(fix.path if kind == "symlink" else fix.work / "absent")
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and "output already exists" in result.stderr
        assert not (fix.work / "unexpected").exists()
        if kind == "file":
            assert fix.output.read_text() == "preserve"
        if kind in ["symlink", "dangling"]:
            assert fix.output.is_symlink()
    return {"invalid_inputs": len(cases), "invalid_modes": 2, "lookup_failures": 6, "existing_outputs_preserved": 4}


def check(app: Application, directory: Path) -> dict:
    helper = build_fixture(directory / "native-fixture")
    result = quoting(app, directory, helper)
    result.update(streams(app, directory, helper))
    result.update(recovery(app, directory, helper))
    result.update(invalid(app, directory, helper))
    return result
