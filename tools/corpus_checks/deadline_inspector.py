"""Independent datetime/timedelta oracle for exact deadline and publication semantics."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
from __future__ import annotations

import copy
import csv
import datetime as dt
import hashlib
import io
import json
import os
import queue
import random
import resource
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .common import Application

UTC = dt.timezone.utc
COLUMNS = [
    "id",
    "label",
    "status",
    "deadline",
    "grace_seconds",
    "cutoff",
    "completed_at",
    "lateness_us",
    "observed_events",
    "future_events",
    "duplicate_events",
]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def timestamp(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.upper().replace("Z", "+00:00")).astimezone(UTC)


def iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds")


def offset(value: dt.datetime, minutes: int, digits: int = 6) -> str:
    local = value.astimezone(dt.timezone(dt.timedelta(minutes=minutes)))
    text = local.isoformat(timespec="microseconds")
    if digits == 0:
        return text[:19] + text[-6:]
    return text[: 20 + digits] + text[-6:]


def microseconds(value: dt.timedelta) -> int:
    return value.days * 86400000000 + value.seconds * 1000000 + value.microseconds


def job(key: str, deadline: str, grace: int = 0, label: str = "Inspect job") -> dict:
    return {"id": key, "label": label, "deadline": deadline, "grace_seconds": grace}


def event(key: str, completed: str) -> dict:
    return {"job": key, "completed_at": completed}


def examples() -> tuple[str, list[dict], list[dict]]:
    observed = "2024-03-01T00:00:00Z"
    jobs = [
        job("early", "2024-02-29T12:00:00Z", label='Backup, "世界"\nSecond line'),
        job("exact", "2024-02-29T17:00:00+05:00"),
        job("grace", "2024-02-29T06:30:00-05:30", 60),
        job("late", "2024-02-29T12:00:00Z", 60),
        job("missing", observed),
        job("pending", "2024-03-01T00:00:00.000001Z"),
        job("retry", "2024-02-29T12:00:00Z"),
        job("future", "2024-03-01T00:00:00Z"),
    ]
    events = [
        event("early", "2024-02-29T11:59:59.999999Z"),
        event("exact", "2024-02-29T06:30:00-05:30"),
        event("grace", "2024-02-29T12:01:00Z"),
        event("late", "2024-02-29T12:01:00.000001Z"),
        event("retry", "2024-02-29T12:00:00.000001Z"),
        event("retry", "2024-02-29t12:00:00z"),
        event("retry", "2024-02-29T17:00:00.000000+05:00"),
        event("future", "2024-03-01T00:00:00.000001Z"),
        event("future", "2024-03-01T05:00:00.000001+05:00"),
    ]
    return observed, jobs, events


@dataclass
class Fixture:
    root: Path
    config: dict
    jobs: list[dict]
    events: list[dict]
    filename: str = "job.json"

    @property
    def output(self) -> Path:
        return self.root / self.config["output"]

    @property
    def settings(self) -> dict:
        return {"DEADLINE_CONFIG": str(self.root / self.filename)}

    def write(self) -> None:
        for name, value in [(self.filename, self.config), ("jobs.json", self.jobs), ("events.json", self.events)]:
            (self.root / name).write_text(canonical(value))
        return


def fixture(
    root: Path, observed: str | None = None, jobs: list[dict] | None = None, events: list[dict] | None = None
) -> Fixture:
    default_observed, default_jobs, default_events = examples()
    root.mkdir(parents=True)
    config = {
        "version": 1,
        "observed_at": observed or default_observed,
        "jobs": "jobs.json",
        "events": "events.json",
        "output": "output",
    }
    fix = Fixture(
        root,
        config,
        copy.deepcopy(default_jobs if jobs is None else jobs),
        copy.deepcopy(default_events if events is None else events),
    )
    fix.write()
    return fix


def reference(fix: Fixture) -> dict:
    observed = timestamp(fix.config["observed_at"])
    rows = []
    for item in fix.jobs:
        deadline = timestamp(item["deadline"])
        cutoff = deadline + dt.timedelta(seconds=item["grace_seconds"])
        received = [timestamp(entry["completed_at"]) for entry in fix.events if entry["job"] == item["id"]]
        distinct = set(received)
        eligible = [instant for instant in distinct if instant <= observed]
        completed = min(eligible) if eligible else None
        status = "on_time" if completed is not None and completed <= cutoff else "late"
        if completed is None:
            status = "missing" if cutoff <= observed else "pending"
        delayed = (completed or observed) - cutoff
        delay = max(0, microseconds(delayed)) if status in ["late", "missing"] else 0
        rows.append(
            {
                "id": item["id"],
                "label": item["label"],
                "deadline": iso(deadline),
                "grace_seconds": item["grace_seconds"],
                "cutoff": iso(cutoff),
                "status": status,
                "completed_at": iso(completed) if completed else None,
                "lateness_us": delay,
                "observed_events": len(eligible),
                "future_events": len(distinct) - len(eligible),
                "duplicate_events": len(received) - len(distinct),
            }
        )
    return {
        "version": 1,
        "observed_at": iso(observed),
        "counts": {
            name: sum(row["status"] == name for row in rows) for name in ["on_time", "late", "missing", "pending"]
        },
        "jobs": rows,
        "received_events": len(fix.events),
        "future_events": sum(row["future_events"] for row in rows),
        "duplicate_events": sum(row["duplicate_events"] for row in rows),
    }


def verify(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {
        "report.json",
        "report.txt",
        "jobs.csv",
        "jobs.json",
        "events.json",
        "deadline-job.json",
        "manifest.json",
    }
    report = json.loads(files["report.json"])
    expected = reference(fix)
    assert report == expected, (report, expected)
    assert files["report.json"] == (canonical(expected) + "\n").encode()
    manifest = json.loads(files["manifest.json"])
    assert manifest == {
        "version": 1,
        "files": {
            name: {"bytes": len(data), "sha256": digest(data)}
            for name, data in files.items()
            if name != "manifest.json"
        },
    }
    csv_rows = list(csv.DictReader(io.StringIO(files["jobs.csv"].decode(), newline="")))
    assert len(csv_rows) == len(expected["jobs"])
    for row, item in zip(csv_rows, expected["jobs"], strict=True):
        assert row == {name: "" if item[name] is None else str(item[name]) for name in COLUMNS}
        assert f'{item["id"]} {canonical(item["label"])}: {item["status"]}' in files["report.txt"].decode()
    assert json.loads(files["jobs.json"]) == [
        dict(item, deadline=iso(timestamp(item["deadline"]))) for item in fix.jobs
    ]
    assert json.loads(files["events.json"]) == [
        dict(item, completed_at=iso(timestamp(item["completed_at"]))) for item in fix.events
    ]
    assert json.loads(files["deadline-job.json"]) == {
        "version": 1,
        "observed_at": iso(timestamp(fix.config["observed_at"])),
        "jobs": "jobs.json",
        "events": "events.json",
        "output": "replayed",
    }
    return report, files


def run(app: Application, fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    expected = reference(fix)
    code = int(expected["counts"]["late"] + expected["counts"]["missing"] > 0)
    inputs = {p: p.read_bytes() for p in [fix.root / fix.filename, fix.root / "jobs.json", fix.root / "events.json"]}
    result = app.run(fix.root, fix.settings)
    assert result.returncode == code, (result.returncode, result.stdout, result.stderr)
    assert json.loads(result.stdout) == expected
    assert all(path.read_bytes() == data for path, data in inputs.items())
    return verify(fix)


def semantics(app: Application, root: Path) -> dict:
    fix = fixture(root / "examples")
    report, files = run(app, fix)
    assert report["counts"] == {"on_time": 4, "late": 1, "missing": 2, "pending": 1}
    assert report["jobs"][3]["lateness_us"] == 1 and report["jobs"][4]["lateness_us"] == 0
    assert report["duplicate_events"] == 2 and report["future_events"] == 1
    hashes = [digest(files["report.json"])]
    boundary = timestamp("2000-03-01T00:00:00.123456Z")
    for delta in [-1, 0, 1]:
        at = boundary + dt.timedelta(microseconds=delta)
        jobs = [job("completion", iso(boundary - dt.timedelta(seconds=60)), 60), job("absent", iso(boundary))]
        fix = fixture(root / f"edge-{delta}", iso(at), jobs, [event("completion", iso(boundary))])
        report, files = run(app, fix)
        assert [row["status"] for row in report["jobs"]] == (
            ["pending", "pending"] if delta < 0 else ["on_time", "missing"]
        )
        assert report["jobs"][1]["lateness_us"] == max(0, delta)
        hashes.append(digest(files["report.json"]))
    dates = [
        "0001-01-01T00:00:00Z",
        "0099-12-31T23:59:59.999999Z",
        "0400-02-29T12:00:00Z",
        "1500-03-01T00:00:00Z",
        "1600-02-29T23:59:59.123456Z",
        "1900-03-01T00:00:00Z",
        "2000-02-29T12:00:00Z",
        "2100-03-01T00:00:00Z",
        "2400-02-29T00:00:00Z",
        "9999-12-31T23:59:59.999999Z",
    ]
    fix = fixture(root / "year-limits", dates[-1], [job("year" + str(i), date) for i, date in enumerate(dates)], [])
    report, files = run(app, fix)
    assert report["jobs"][0]["lateness_us"] == 315537897599999999
    hashes.append(digest(files["report.json"]))
    offsets = [-1439, -720, -345, -1, 0, 1, 345, 765, 1439]
    jobs = [job("zone" + str(i), offset(boundary, minute), 604800) for i, minute in enumerate(offsets)]
    events = [
        event(row["id"], offset(boundary + dt.timedelta(seconds=604800), -minute))
        for row, minute in zip(jobs, offsets, strict=True)
    ]
    fix = fixture(root / "offsets", iso(boundary + dt.timedelta(seconds=604800)), jobs, events)
    report, files = run(app, fix)
    assert report["counts"]["on_time"] == len(offsets)
    assert len({row["cutoff"] for row in report["jobs"]}) == 1
    hashes.append(digest(files["report.json"]))
    values = [
        "2000-03-01T00:00:00" + fraction + zone
        for fraction in ["", ".1", ".12", ".123", ".1234", ".12345", ".123456"]
        for zone in ["Z", "+00:00", "-00:00", "z"]
    ]
    fix = fixture(
        root / "precision",
        "2000-03-01T00:00:01Z",
        [job("fraction" + str(i), value) for i, value in enumerate(values)],
        [],
    )
    _, files = run(app, fix)
    hashes.append(digest(files["report.json"]))
    rng = random.Random(8501)
    generated = 0
    for batch, observed in enumerate(
        ["2024-02-29T12:00:00Z", "2024-03-01T00:00:00.123456Z", "2024-03-10T23:59:59Z", "9999-12-31T23:59:59.999999Z"]
    ):
        jobs, events = [], []
        for index in range(128):
            key = f"job{index}"
            deadline = boundary + dt.timedelta(
                days=rng.randint(-36500, 36500), microseconds=rng.randint(-1000001, 1000001)
            )
            grace = rng.choice([0, 1, 60, 3600, 604800])
            jobs.append(job(key, offset(deadline, rng.choice(offsets)), grace, f"Job {index} — café"))
            for _ in range(rng.randrange(5)):
                completed = deadline + dt.timedelta(
                    seconds=grace, microseconds=rng.choice([-1000001, -1, 0, 1, 1000001])
                )
                events.append(event(key, offset(completed, rng.choice(offsets))))
                if rng.randrange(4) == 0:
                    events.append(event(key, iso(completed)))
        rng.shuffle(events)
        fix = fixture(root / f"generated-{batch}", observed, jobs, events)
        _, files = run(app, fix)
        hashes.append(digest(files["report.json"]))
        generated += len(jobs)
    return {
        "explicit_jobs": 8 + 6 + len(dates) + len(offsets) + len(values),
        "generated_jobs": generated,
        "report_sha256": digest(canonical(hashes).encode()),
        "max_lateness_us": 315537897599999999,
    }


def rejected(app: Application, fix: Fixture, diagnostic: str = "") -> None:
    before = {p: p.read_bytes() for p in fix.root.rglob("*") if p.is_file()}
    before_paths = set(fix.root.rglob("*"))
    result = app.run(fix.root, fix.settings)
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert diagnostic in result.stderr, (diagnostic, result.stderr)
    assert set(fix.root.rglob("*")) == before_paths
    assert not list(fix.root.glob(".deadline-*"))
    assert all(path.read_bytes() == data for path, data in before.items())
    return


def invalid_timestamps(app: Application, root: Path) -> int:
    values = [
        "",
        "today",
        "2024-02-29",
        "2024-02-29T12:00:00",
        "2024-02-29 12:00:00Z",
        "2024-02-29T12:00Z",
        "2024-02-29T12:00:00.1234567Z",
        "2024-02-29T12:00:00.Z",
        "2024-02-29T12:00:00,5Z",
        "2024-02-29T24:00:00Z",
        "2024-02-29T23:60:00Z",
        "2016-12-31T23:59:60Z",
        "0000-01-01T00:00:00Z",
        "10000-01-01T00:00:00Z",
        "0001-01-01T00:00:00+00:01",
        "9999-12-31T23:59:59-00:01",
        "2024-00-01T00:00:00Z",
        "2024-13-01T00:00:00Z",
        "2024-01-00T00:00:00Z",
        "2024-04-31T00:00:00Z",
        "1900-02-29T00:00:00Z",
        "2100-02-29T00:00:00Z",
        "2024-02-29T12:00:00+24:00",
        "2024-02-29T12:00:00-24:00",
        "2024-02-29T12:00:00+00:60",
        "2024-02-29T12:00:00+0500",
        "2024-02-29T12:00:00+05:00:30",
        "2024-W09-4T12:00:00Z",
        "2024-060T12:00:00Z",
        "２０２４-02-29T12:00:00Z",
        "2024-02-29T12:00:00Z\n",
        " 2024-02-29T12:00:00Z",
        "2024-02-29T12:00:00Z\x00",
        None,
        0,
        False,
    ]
    for index, value in enumerate(values):
        for where in ["observed", "job", "event"]:
            fix = fixture(root / f"{index}-{where}")
            if where == "observed":
                fix.config["observed_at"] = value
                message = "observed_at: expected RFC3339"
            elif where == "job":
                fix.jobs[0]["deadline"] = value
                message = "jobs[0].deadline: expected RFC3339"
            else:
                fix.events[0]["completed_at"] = value
                message = "events[0].completed_at: expected RFC3339"
            fix.write()
            rejected(app, fix, message)
    return len(values) * 3


def invalid_documents(app: Application, root: Path) -> int:
    mutations = [
        lambda f: f.config.update(version=2),
        lambda f: f.config.update(version=True),
        lambda f: f.config.update(extra=0),
        lambda f: f.config.update(jobs="events.json"),
        lambda f: f.config.update(events="job.json"),
        lambda f: f.config.update(output=""),
        lambda f: f.jobs.clear(),
        lambda f: f.jobs.extend([f.jobs[0]] * 249),
        lambda f: f.events.extend([f.events[0]] * 4096),
        lambda f: f.jobs.append(f.jobs[0]),
        lambda f: f.jobs[0].update(id="../escape"),
        lambda f: f.jobs[0].update(id="a" * 33),
        lambda f: f.jobs[0].update(id="Я"),
        lambda f: f.jobs[0].update(label=""),
        lambda f: f.jobs[0].update(label="é" * 129),
        lambda f: f.jobs[0].update(label="bad\0label"),
        lambda f: f.jobs[0].update(label=1),
        lambda f: f.jobs[0].update(grace_seconds=-1),
        lambda f: f.jobs[0].update(grace_seconds=604801),
        lambda f: f.jobs[0].update(grace_seconds=True),
        lambda f: f.jobs[0].update(grace_seconds=1.0),
        lambda f: f.jobs[0].update(deadline="9999-12-31T23:59:59.000001Z", grace_seconds=1),
        lambda f: f.jobs[0].update(extra="x"),
        lambda f: f.events[0].update(job="unknown"),
        lambda f: f.events[0].update(extra="x"),
        lambda f: f.jobs[0].pop("deadline"),
        lambda f: f.events[0].pop("completed_at"),
    ]
    for index, mutate in enumerate(mutations):
        fix = fixture(root / f"shape-{index}")
        mutate(fix)
        fix.write()
        rejected(app, fix)
    raw_cases = [b"{", b"null", b"{}", b"[null]", b"\xff", b"[NaN]"]
    count = len(mutations)
    for filename in ["job.json", "jobs.json", "events.json"]:
        for index, raw in enumerate(raw_cases):
            fix = fixture(root / f"raw-{filename}-{index}")
            (fix.root / filename).write_bytes(raw)
            rejected(app, fix)
            count += 1
    return count


def capacity(app: Application, root: Path) -> dict:
    observed = timestamp("2024-03-01T00:00:00.000007Z")
    jobs = [job("job" + str(i).zfill(29), "2024-03-01T00:00:00Z", label="λ" * 128) for i in range(256)]
    events = [event(row["id"], iso(observed + dt.timedelta(microseconds=i - 7))) for row in jobs for i in range(16)]
    fix = fixture(root / "full", iso(observed), jobs, events)
    limits = {"job.json": 65536, "jobs.json": 262144, "events.json": 524288}
    for filename, size in limits.items():
        path = fix.root / filename
        data = path.read_bytes()
        assert len(data) <= size
        path.write_bytes(data + b" " * (size - len(data)))

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
    report, files = verify(fix)
    assert report["counts"]["on_time"] == 256 and report["future_events"] == 2048
    for filename, size in limits.items():
        oversized = fixture(root / f"oversized-{filename}")
        path = oversized.root / filename
        data = path.read_bytes()
        path.write_bytes(data + b" " * (size + 1 - len(data)))
        rejected(app, oversized, "input byte limit exceeded")
    base = timestamp("2024-03-01T00:00:00Z")
    single = fixture(
        root / "single-job",
        iso(base + dt.timedelta(microseconds=2000)),
        [job("busy", iso(base))],
        [event("busy", iso(base + dt.timedelta(microseconds=i))) for i in range(4096)],
    )
    one, _ = run(app, single)
    assert one["jobs"][0]["observed_events"] == 2001 and one["future_events"] == 2095
    return {
        "jobs": 256,
        "events": 4096,
        "label_bytes": 256,
        "identifier_characters": 32,
        "memory_limit": 268435456,
        "input_byte_limits": limits,
        "single_job_distinct_events": 4096,
        "report_sha256": digest(files["report.json"]),
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, DEADLINE_PAUSE=label, DEADLINE_RELEASE=str(fix.root / "release"))),
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
            assert line is not None, "exited before checkpoint"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, root: Path) -> dict:
    count = 0
    for label in ["staged", "published"]:
        for killed in [False, True]:
            fix = fixture(root / f"{label}-{killed}")
            if killed:
                process = paused(app, fix, label)
                process.kill()
                process.communicate(timeout=5)
            else:
                result = app.run(fix.root, dict(fix.settings, DEADLINE_FAULT=label))
                assert result.returncode == 2
                assert not list(fix.root.glob(".deadline-*"))
            if label == "staged":
                assert not fix.output.exists()
                if killed:
                    orphan = next(fix.root.glob(".deadline-*"))
                    original = {p.name: p.read_bytes() for p in orphan.iterdir()}
                    run(app, fix)
                    assert original == {p.name: p.read_bytes() for p in orphan.iterdir()}
                else:
                    run(app, fix)
            else:
                _, files = verify(fix)
                result = app.run(fix.root, fix.settings)
                assert result.returncode == 2
                assert files == {p.name: p.read_bytes() for p in fix.output.iterdir()}
            count += 1
    for name in ["job.json", "jobs.json", "events.json"]:
        fix = fixture(root / ("live-change-" + name))
        process = paused(app, fix, "staged")
        path = fix.root / name
        path.write_bytes(path.read_bytes() + b" ")
        (fix.root / "release").write_text("resume")
        process.communicate(timeout=10)
        assert process.returncode == 2 and not fix.output.exists()
        assert not list(fix.root.glob(".deadline-*"))
        count += 1
    for name in ["job.json", "jobs.json", "events.json"]:
        for kind in ["symlink", "hardlink"]:
            fix = fixture(root / f"{name}-{kind}")
            path, target = fix.root / name, fix.root / "original"
            path.rename(target)
            if kind == "symlink":
                path.symlink_to(target)
            else:
                os.link(target, path)
            rejected(app, fix)
            count += 1
    for kind in ["directory", "file", "symlink"]:
        fix = fixture(root / f"existing-{kind}")
        if kind == "directory":
            fix.output.mkdir()
            (fix.output / "preserved").write_text("keep")
        elif kind == "file":
            fix.output.write_text("keep")
        else:
            fix.output.symlink_to(fix.root / "missing")
        result = app.run(fix.root, fix.settings)
        assert result.returncode == 2 and "output already exists" in result.stderr
        assert fix.output.is_symlink() if kind == "symlink" else fix.output.exists()
        count += 1
    if os.getuid() != 0:
        fix = fixture(root / "permissions")
        fix.root.chmod(0o500)
        try:
            rejected(app, fix)
        finally:
            fix.root.chmod(0o700)
        count += 1
    fix = fixture(root / "concurrent")
    processes = [
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
    results = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            results.append(process.returncode)
            assert process.returncode in [1, 2], (stdout, stderr)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    assert results.count(1) == 1
    verify(fix)
    assert not list(fix.root.glob(".deadline-*"))
    return {"failure_and_alias_checks": count, "concurrent_writers": 8, "successful_publications": 1}


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid_timestamps": invalid_timestamps(app, directory / "invalid-times"),
        "invalid_documents": invalid_documents(app, directory / "invalid-documents"),
        "capacity": capacity(app, directory / "capacity"),
        "publication": publication(app, directory / "publication"),
        "independent_datetime_oracle": True,
    }
