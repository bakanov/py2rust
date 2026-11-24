"""Independent jobs oracle and real process interruption/recovery checks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import random
import resource
import subprocess
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .common import Application


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expected(rows: list[dict], raw: bytes) -> dict:
    results = []
    for row in rows:
        text = unicodedata.normalize("NFC", unicodedata.normalize("NFC", row["text"]).casefold())
        samples = row["values"]
        words = text.split()
        results.append(
            {
                "id": row["id"],
                "normalized": text,
                "characters": len(text),
                "utf8_bytes": len(text.encode()),
                "words": len(words),
                "frequencies": dict(Counter(words)),
                "samples": len(samples),
                "sum": sum(samples),
                "minimum": min(samples) if samples else None,
                "maximum": max(samples) if samples else None,
            }
        )
    return {
        "version": 1,
        "binding": {"sha256": digest(raw), "input_bytes": len(raw), "jobs": len(rows), "transform": 1},
        "results": results,
        "summary": {
            "jobs": len(rows),
            **{
                key: sum(row[key] for row in results) for key in ["characters", "utf8_bytes", "words", "samples", "sum"]
            },
        },
    }


def sample_rows() -> list[dict]:
    return [
        {"id": "first", "text": " Hello HELLO\tworld ", "values": [5, -2, 9]},
        {"id": "unicode", "text": "Straße STRASSE café cafe\u0301 Σ σ ς", "values": [-1000000000, 1000000000]},
        {"id": "empty", "text": "", "values": []},
        {"id": "spaces", "text": "a\u001cb\u001dc\u001ed\u001fe\u0085f\u00a0g\u2003h\u2028i\u2029j", "values": [0]},
        {"id": "symbols", "text": '😀 😀 世界\x00quoted" line\nend \\ $1', "values": [-8, -8]},
    ]


@dataclass
class Fixture:
    root: Path
    rows: list[dict]
    raw: bytes
    config: dict

    @property
    def source(self) -> Path:
        return self.root / "jobs.jsonl"

    @property
    def configuration(self) -> Path:
        return self.root / "job.json"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def settings(self) -> dict[str, str]:
        return {"BATCH_CONFIG": str(self.configuration)}

    def save(self) -> None:
        self.configuration.write_bytes(canonical(self.config))
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def fixture(root: Path, rows: list[dict] | None = None, raw: bytes | None = None, batch: int = 2) -> Fixture:
    root.mkdir(parents=True)
    rows = sample_rows() if rows is None else rows
    data = b"".join(canonical(row) + b"\n" for row in rows) if raw is None else raw
    fix = Fixture(root, rows, data, {"version": 1, "input": "jobs.jsonl", "output": "output", "batch_size": batch})
    fix.source.write_bytes(data)
    fix.save()
    return fix


def state(fix: Fixture) -> dict:
    envelope = json.loads((fix.output / "state.json").read_bytes())
    assert set(envelope) == {"value", "sha256"}
    assert envelope["sha256"] == digest(canonical(envelope["value"]))
    return envelope["value"]


def verify(fix: Fixture, completed: int | None = None) -> dict:
    saved = state(fix)
    count = len(fix.rows) if completed is None else completed
    oracle = expected(fix.rows, fix.raw)
    prefix = expected(fix.rows[:count], fix.raw)
    assert saved == {
        "version": 1,
        "binding": oracle["binding"],
        "completed": count,
        "results": prefix["results"],
        "summary": prefix["summary"],
    }
    if completed is None:
        assert (fix.output / "report.json").read_bytes() == canonical(oracle) + b"\n"
        assert {p.name for p in fix.output.iterdir()} == {"state.json", "report.json"}
    else:
        assert not (fix.output / "report.json").exists()
    return saved


def invoke(app: Application, fix: Fixture, **settings: str) -> list[dict]:
    result = app.run(fix.root, dict(fix.settings, **settings), timeout=90)
    assert result.returncode == 0, result.stderr
    assert not result.stderr, result.stderr
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    assert rows and rows[-1]["status"] in {"complete", "paused", "cancelled"}
    previous = -1
    for row in rows:
        assert set(row) == {"status", "completed", "total", "summary"}
        assert previous <= row["completed"] <= row["total"] == len(fix.rows)
        assert row["summary"] == expected(fix.rows[: row["completed"]], fix.raw)["summary"]
        assert row["status"] in {"progress", "complete", "paused", "cancelled"}
        previous = row["completed"]
    return rows


def snapshot(root: Path) -> dict:
    if not root.exists():
        return {}
    found = {}
    for path in root.iterdir():
        info = path.lstat()
        if path.is_symlink():
            data = os.readlink(path)
        elif path.is_file():
            data = digest(path.read_bytes())
        else:
            data = "special"
        found[path.name] = (info.st_ino, info.st_mode, info.st_size, data)
    return found


def rejected(app: Application, fix: Fixture, preserve: bool = True, **settings: str) -> subprocess.CompletedProcess:
    before = snapshot(fix.output)
    result = app.run(fix.root, dict(fix.settings, **settings), timeout=30)
    assert result.returncode == 2 and result.stderr, (result.returncode, result.stdout, result.stderr)
    if preserve:
        assert snapshot(fix.output) == before
    return result


def semantics(app: Application, root: Path) -> dict:
    workloads = [[], sample_rows(), [{"id": "only", "text": " \t\r\n\u3000", "values": []}]]
    generator = random.Random(9090)
    tokens = ["café", "cafe\u0301", "Σ", "ς", "İ", "ﬃ", "ABC", "ß", "😀", "世界", "a\0b"]
    generated = [
        {
            "id": f"job_{i}",
            "text": " ".join(generator.choices(tokens, k=generator.randrange(30))),
            "values": [generator.randint(-1000000000, 1000000000) for _ in range(generator.randrange(20))],
        }
        for i in range(64)
    ]
    workloads.append(generated)
    hashes = []
    for index, rows in enumerate(workloads):
        reports = []
        for batch in [1, 2, 7, 64]:
            fix = fixture(root / f"case-{index}-{batch}", rows, batch=batch)
            emitted = invoke(app, fix)
            verify(fix)
            assert emitted[-1]["status"] == "complete"
            reports.append((fix.output / "report.json").read_bytes())
            before = snapshot(fix.output)
            fix.config["batch_size"] = 3
            fix.save()
            assert len(invoke(app, fix)) == 1
            assert snapshot(fix.output) == before
        assert len(set(reports)) == 1
        hashes.append(digest(reports[0]))
    for index, suffix in enumerate([b"", b"\n", b"\r\n"]):
        row = {"id": "line", "text": "one", "values": [1]}
        fix = fixture(root / f"line-{index}", [row], canonical(row) + suffix)
        invoke(app, fix)
        verify(fix)
    return {
        "workloads": 4,
        "batch_sizes": [1, 2, 7, 64],
        "generated_jobs": 64,
        "unchanged_completed_replay": True,
        "sha256": digest(canonical(hashes)),
    }


def paused(app: Application, fix: Fixture, label: str, **settings: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, BATCH_PAUSE=label, BATCH_RELEASE=str(fix.root / "release"), **settings)),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def read_lines() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    threading.Thread(target=read_lines, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=30)
            assert line is not None, f"exited before {label}"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def kill(process: subprocess.Popen) -> None:
    process.kill()
    assert process.wait(timeout=10) < 0
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def interruptions(app: Application, root: Path) -> dict:
    points = [("initial:0", None), ("staged:0", None), ("committed:0", 0)]
    previous = 0
    for completed in [2, 4, 5]:
        points.extend(
            [
                (f"computed:{completed}", previous),
                (f"staged:{completed}", previous),
                (f"committed:{completed}", completed),
            ]
        )
        previous = completed
    points.extend([("report-staged:5", 5), ("report-published:5", 5)])
    hashes = []
    for action in ["fault", "kill"]:
        for label, completed in points:
            fix = fixture(root / (action + "-" + label.replace(":", "-")))
            if action == "kill":
                kill(paused(app, fix, label))
            else:
                failure = rejected(app, fix, preserve=False, BATCH_FAULT=label)
                assert all(json.loads(line)["completed"] <= (completed or 0) for line in failure.stdout.splitlines())
            if completed is None:
                assert not (fix.output / "state.json").exists()
            else:
                saved = state(fix)
                assert saved["completed"] == completed
                assert len(saved["results"]) == completed
                assert saved["results"] == expected(fix.rows[:completed], fix.raw)["results"]
            assert (fix.output / "report.json").exists() == (label == "report-published:5")
            fix.config["batch_size"] = 3
            fix.save()
            invoke(app, fix)
            verify(fix)
            hashes.append(digest((fix.output / "report.json").read_bytes()))
    assert len(set(hashes)) == 1
    fix = fixture(root / "bounded")
    assert invoke(app, fix, BATCH_LIMIT="1")[-1]["status"] == "paused"
    verify(fix, 2)
    assert invoke(app, fix, BATCH_LIMIT="1")[-1]["completed"] == 4
    verify(fix, 4)
    invoke(app, fix)
    verify(fix)
    cancel = fixture(root / "cancel")
    stop = cancel.root / "stop"
    stop.touch()
    assert invoke(app, cancel, BATCH_STOP=str(stop))[-1]["status"] == "cancelled"
    verify(cancel, 0)
    stop.unlink()
    holder = paused(app, cancel, "committed:2", BATCH_STOP=str(stop))
    stop.touch()
    (cancel.root / "release").touch()
    assert holder.wait(timeout=20) == 0
    verify(cancel, 2)
    stop.unlink()
    invoke(app, cancel)
    verify(cancel)
    return {
        "boundaries": len(points),
        "actual_kills": len(points),
        "injected_failures": len(points),
        "cancellation_and_batch_limit": True,
        "sha256": hashes[0],
    }


def invalid(app: Application, root: Path) -> dict:
    configs = []
    for key, values in {
        "version": [0, 2, True, 1.0, "1"],
        "batch_size": [0, 65, -1, True, 1.5, None],
        "input": ["", "bad\0path", 1, None],
        "output": ["", "bad\0path", 1, None],
    }.items():
        configs.extend((key, value) for value in values)
    for index, (key, value) in enumerate(configs):
        fix = fixture(root / f"config-{index}")
        fix.config[key] = value
        fix.save()
        rejected(app, fix)
    for key in ["version", "input", "output", "batch_size"]:
        fix = fixture(root / ("missing-" + key))
        del fix.config[key]
        fix.save()
        rejected(app, fix)
    malformed = [b"", b"{", b"[]", b"null", b"\xff", b'{"version":1,"version":1}', b'{"extra":1}']
    for index, raw in enumerate(malformed):
        fix = fixture(root / f"malformed-config-{index}")
        fix.configuration.write_bytes(raw)
        rejected(app, fix)
    rows = []
    base = {"id": "one", "text": "text", "values": [1, 2]}
    for key, values in {
        "id": ["", "a" * 33, "é", "1bad", "bad space", None],
        "text": [None, [], {}, 3, "x" * 2049],
        "values": [None, {}, "", [True], [1.0], [1000000001], [-1000000001], [0] * 129],
    }.items():
        rows.extend([dict(base, **{key: value})] for value in values)
    rows.extend([[base, base], [dict(base, extra=1)], [{"id": "one", "values": []}], [base] * 257])
    for index, values in enumerate(rows):
        fix = fixture(root / f"invalid-job-{index}", values)
        rejected(app, fix)
    data = [
        b"\n",
        b"{}\n",
        b"null",
        b"[]",
        b"\xff",
        b'{"id":"x","id":"y"}',
        b'{"id":"x","text":"\\ud800","values":[]}',
        b'{"id":"x","text":"text","values":[9223372036854775808]}',
        canonical(base) + b"\n\n",
        canonical(base) + b" trailing",
    ]
    for index, raw in enumerate(data):
        rejected(app, fixture(root / f"invalid-data-{index}", raw=raw))
    for index, settings in enumerate(
        [
            {"BATCH_LIMIT": "-1"},
            {"BATCH_LIMIT": "257"},
            {"BATCH_LIMIT": "true"},
            {"BATCH_LIMIT": "1.0"},
            {"BATCH_LIMIT": "junk"},
        ]
    ):
        rejected(app, fixture(root / f"invalid-setting-{index}"), **settings)
    return {"configurations": len(configs) + 4 + len(malformed), "jobs": len(rows) + len(data), "settings": 5}


def write_state(fix: Fixture, value: dict) -> None:
    (fix.output / "state.json").write_bytes(canonical({"value": value, "sha256": digest(canonical(value))}) + b"\n")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def corruptions(app: Application, root: Path) -> dict:
    reference = fixture(root / "reference")
    invoke(app, reference, BATCH_LIMIT="1")
    original = state(reference)
    mutations = []
    for key, value in [
        ("version", 2),
        ("version", True),
        ("completed", -1),
        ("completed", 1),
        ("completed", 6),
        ("completed", True),
        ("results", []),
        ("summary", {}),
        ("extra", 0),
    ]:
        changed = copy.deepcopy(original)
        changed[key] = value
        mutations.append(changed)
    for key, value in [("sha256", "0" * 64), ("input_bytes", 0), ("jobs", 2), ("transform", 2)]:
        changed = copy.deepcopy(original)
        changed["binding"][key] = value
        mutations.append(changed)
    for key, value in [
        ("id", "wrong"),
        ("normalized", None),
        ("normalized", "x" * 8193),
        ("characters", 0),
        ("utf8_bytes", 0),
        ("words", 0),
        ("frequencies", {}),
        ("samples", -1),
        ("samples", 129),
        ("sum", 1000000000000),
        ("minimum", None),
        ("minimum", 1000000001),
        ("maximum", -1000000001),
    ]:
        changed = copy.deepcopy(original)
        changed["results"][0][key] = value
        mutations.append(changed)
    for index, changed in enumerate(mutations):
        fix = fixture(root / f"invalid-{index}")
        fix.output.mkdir()
        write_state(fix, changed)
        rejected(app, fix)
    for index, content in enumerate(
        [
            b"",
            b"{",
            b"[]",
            b"\xff",
            b'{"value":{},"sha256":"wrong"}',
            canonical({"value": original, "sha256": "0" * 64}),
        ]
    ):
        fix = fixture(root / f"malformed-{index}")
        fix.output.mkdir()
        (fix.output / "state.json").write_bytes(content)
        rejected(app, fix)
    for name in ["input-change", "raw-input-change", "report-before-complete", "bad-report", "report-without-state"]:
        fix = fixture(root / name)
        invoke(app, fix, BATCH_LIMIT="1" if name != "bad-report" else "0")
        if name == "input-change":
            rows = sample_rows()
            rows[0]["text"] = "changed"
            fix.source.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))
        elif name == "raw-input-change":
            fix.source.write_bytes(fix.raw.replace(b"\n", b"\r\n"))
        else:
            (fix.output / "report.json").write_bytes(b"{}\n")
            if name == "report-without-state":
                (fix.output / "state.json").unlink()
        rejected(app, fix)
    return {"rechecksummed_invalid_states": len(mutations), "malformed_states": 6, "binding_and_report_checks": 5}


def filesystem(app: Application, root: Path) -> dict:
    cases = [
        "source-symlink",
        "source-hardlink",
        "source-fifo",
        "config-symlink",
        "config-hardlink",
        "output-symlink",
        "unknown-output",
        "state-symlink",
        "state-hardlink",
        "state-directory",
        "temporary-symlink",
        "lock-symlink",
        "lock-hardlink",
        "lock-fifo",
        "source-is-config",
        "source-inside-output",
        "config-inside-output",
        "source-is-lock",
    ]
    for name in cases:
        fix = fixture(root / name)
        target = fix.root / "untouched"
        target.write_bytes(b"preserve this file")
        if name.startswith("source-") and name in ["source-symlink", "source-hardlink", "source-fifo"]:
            fix.source.unlink()
            if name == "source-symlink":
                fix.source.symlink_to(target)
            elif name == "source-hardlink":
                os.link(target, fix.source)
            else:
                os.mkfifo(fix.source)
        elif name.startswith("config-") and name in ["config-symlink", "config-hardlink"]:
            fix.configuration.unlink()
            if name == "config-symlink":
                fix.configuration.symlink_to(target)
            else:
                os.link(target, fix.configuration)
        elif name == "output-symlink":
            directory = fix.root / "other"
            directory.mkdir()
            fix.output.symlink_to(directory, target_is_directory=True)
        elif name in ["source-is-config", "source-inside-output", "config-inside-output", "source-is-lock"]:
            if name == "source-is-config":
                fix.config["input"] = "job.json"
            elif name == "source-is-lock":
                fix.config["output"] = "jobs.jsonl".removesuffix(".jsonl")
                fix.config["input"] = "jobs.lock"
                (fix.root / "jobs.lock").write_bytes(fix.raw)
            else:
                fix.config["output"] = "."
            fix.save()
        else:
            fix.output.mkdir()
            path = (
                fix.root / "output.lock"
                if name.startswith("lock-")
                else fix.output / ("control.tmp" if name.startswith("temporary-") else "state.json")
            )
            if name == "unknown-output":
                path = fix.output / "unrelated.txt"
                path.write_bytes(b"keep")
            elif name.endswith("symlink"):
                path.symlink_to(target)
            elif name.endswith("hardlink"):
                os.link(target, path)
            elif name.endswith("directory"):
                path.mkdir()
            else:
                os.mkfifo(path)
        rejected(app, fix)
        assert target.read_bytes() == b"preserve this file"
    for changed in ["input", "configuration"]:
        fix = fixture(root / ("during-" + changed))
        holder = paused(app, fix, "staged:2")
        try:
            path = fix.source if changed == "input" else fix.configuration
            with path.open("ab") as stream:
                stream.write(b" ")
            (fix.root / "release").touch()
            assert holder.wait(timeout=20) == 2
            assert state(fix)["completed"] == 0
            assert not (fix.output / "report.json").exists()
        finally:
            if holder.poll() is None:
                kill(holder)
    fix = fixture(root / "contenders")
    holder = paused(app, fix, "staged:2")
    try:
        for _ in range(8):
            rejected(app, fix)
    finally:
        kill(holder)
    invoke(app, fix)
    verify(fix)
    protected = fixture(root / "permission-denied")
    invoke(app, protected, BATCH_LIMIT="1")
    assert os.getuid() != 0, "permission checks require an ordinary user"
    protected.output.chmod(0o500)
    try:
        rejected(app, protected)
    finally:
        protected.output.chmod(0o700)
    verify(protected, 2)
    invoke(app, protected)
    verify(protected)
    for index, name in enumerate(["output/control.tmp", "output.lock", "jobs.jsonl", "job.json"]):
        fix = fixture(root / f"stop-alias-{index}")
        rejected(app, fix, BATCH_STOP=str(fix.root / name))
    return {
        "alias_and_ownership_cases": len(cases) + 4,
        "input_change_guards": 2,
        "rejected_competing_workers": 8,
        "permission_failure_recovered": True,
    }


def limits(app: Application, root: Path) -> dict:
    rows = [
        {
            "id": "j" + str(i).ljust(31, "x"),
            "text": "\x00" * 2048 if i == 0 else ("x" * 2048 if i % 2 else "a " * 1024),
            "values": [1000000000 if i % 2 else -1000000000] * 128,
        }
        for i in range(256)
    ]
    fix = fixture(root / "maximum", rows, batch=64)

    def memory_bound() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=120,
        preexec_fn=memory_bound,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    verify(fix)
    assert len(fix.raw) <= 1048576
    job = {"id": "line", "text": "text", "values": [1]}
    line = canonical(job)
    exact = fixture(root / "line-exact", [job], raw=line + b" " * (16384 - len(line)))
    invoke(app, exact)
    verify(exact)
    rejected(app, fixture(root / "line-over", [job], raw=line + b" " * (16385 - len(line))))
    rows = [{"id": "job" + str(i), "text": "text", "values": [i]} for i in range(64)]
    raw = b"".join(canonical(row).ljust(16383, b" ") + b"\n" for row in rows)
    assert len(raw) == 1048576
    full = fixture(root / "input-exact", rows, raw=raw, batch=64)
    config = full.configuration.read_bytes()
    full.configuration.write_bytes(config.ljust(65536, b" "))
    invoke(app, full)
    verify(full)
    for name, size in [("job.json", 65536), ("jobs.jsonl", 1048576)]:
        over = fixture(root / ("oversize-" + name))
        path = over.root / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        rejected(app, over)
    partial = fixture(root / "state-exact")
    invoke(app, partial, BATCH_LIMIT="1")
    path = partial.output / "state.json"
    path.write_bytes(path.read_bytes().ljust(8388608, b" "))
    invoke(app, partial)
    verify(partial)
    path.write_bytes(path.read_bytes().ljust(8388609, b" "))
    rejected(app, partial)
    return {
        "jobs": 256,
        "samples_per_job": 128,
        "text_bytes": 2048,
        "batch_size": 64,
        "job_line_bytes": 16384,
        "configuration_bytes": 65536,
        "input_bytes": 1048576,
        "checkpoint_bytes": 8388608,
        "memory_limit": 268435456,
        "maximum_report_sha256": digest((fix.output / "report.json").read_bytes()),
    }


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "interruptions": interruptions(app, directory / "interruptions"),
        "invalid": invalid(app, directory / "invalid"),
        "corruptions": corruptions(app, directory / "corruptions"),
        "filesystem": filesystem(app, directory / "filesystem"),
        "limits": limits(app, directory / "limits"),
        "independent_transform_and_checkpoint_oracle": True,
    }
