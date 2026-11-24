"""Independent ZoneInfo oracle, actual portable replay and bounded publication checks."""

# ruff: noqa: PLR1711, DTZ001 - explicit returns and intentionally naive local timestamps
from __future__ import annotations

import base64
import copy
import csv
import datetime as dt
import hashlib
import io
import json
import os
import queue
import random
import re
import resource
import shutil
import struct
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from .common import Application

UTC = dt.timezone.utc
DATABASE = Path("/usr/share/zoneinfo")
COLUMNS = [
    "id",
    "label",
    "status",
    "source_zone",
    "requested_local",
    "target_zone",
    "local",
    "utc",
    "offset_seconds",
    "abbreviation",
]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def appointment(
    key: str, local: str, zone: str, ambiguity: str = "reject", gap: str = "reject", label: str = "Meeting"
) -> dict:
    return {"id": key, "label": label, "local": local, "zone": zone, "ambiguity": ambiguity, "gap": gap}


def examples() -> list[dict]:
    rows = [appointment("ordinary", "2024-02-29T12:34:56.123456", "Asia/Kathmandu", label='Planning, "世界"\nAgenda')]
    for index, (zone, fold, gap) in enumerate(
        [
            ("America/New_York", "2024-11-03T01:30:00.123456", "2024-03-10T02:30:00.123456"),
            ("Europe/Berlin", "2024-10-27T02:30:00", "2024-03-31T02:30:00"),
            ("Australia/Lord_Howe", "2024-04-07T01:45:00", "2024-10-06T02:15:00"),
            ("Europe/Dublin", "2024-10-27T01:30:00", "2024-03-31T01:30:00"),
            ("Antarctica/Troll", "2024-10-27T01:30:00", "2024-03-31T01:30:00"),
        ]
    ):
        for policy in ["reject", "earlier", "later"]:
            rows.append(appointment(f"fold{index}_{policy}", fold, zone, ambiguity=policy))
        for policy in ["reject", "shift_forward", "shift_backward"]:
            rows.append(appointment(f"gap{index}_{policy}", gap, zone, gap=policy))
    for policy in ["reject", "shift_forward", "shift_backward"]:
        rows.append(appointment("date_line_" + policy, "2011-12-30T12:00:00", "Pacific/Apia", gap=policy))
    rows += [
        appointment("historical", "1890-01-01T12:00:00", "Europe/Amsterdam"),
        appointment("future", "2050-07-01T12:00:00", "America/New_York"),
        appointment("bad_date", "1900-02-29T12:00:00", "UTC"),
    ]
    return rows


@dataclass
class Fixture:
    root: Path
    config: dict
    filename: str = "job.json"

    @property
    def output(self) -> Path:
        return self.root / self.config["output"]

    @property
    def settings(self) -> dict:
        return {"TIMEZONE_CONFIG": str(self.root / self.filename)}

    def write(self) -> None:
        (self.root / self.filename).write_text(canonical(self.config))
        return

    def data(self) -> dict[str, bytes]:
        path = self.root / self.config["tzdata"]
        names = set(self.config["targets"]) | {item["zone"] for item in self.config["appointments"]}
        if path.is_dir():
            return {name: (path / name).read_bytes() for name in names}
        return {name: base64.b64decode(value, validate=True) for name, value in json.loads(path.read_bytes()).items()}


def fixture(root: Path, rows: list[dict] | None = None, targets: list[str] | None = None) -> Fixture:
    root.mkdir(parents=True)
    rows = copy.deepcopy(examples() if rows is None else rows)
    targets = targets or ["UTC", "Europe/Berlin", "Asia/Kathmandu"]
    for name in set(targets) | {row["zone"] for row in rows}:
        path = root / "tzdata" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((DATABASE / name).read_bytes())
    fix = Fixture(
        root, {"version": 1, "tzdata": "tzdata", "targets": targets, "appointments": rows, "output": "output"}
    )
    fix.write()
    return fix


def view(zone: ZoneInfo, value: dt.datetime) -> dict:
    utc = value.astimezone(UTC)
    local = utc.astimezone(zone)
    return {
        "utc": utc.isoformat(timespec="microseconds"),
        "local": local.replace(tzinfo=None).isoformat(timespec="microseconds"),
        "offset_seconds": int(local.utcoffset().total_seconds()),
        "abbreviation": local.tzname(),
        "is_dst": bool(local.dst()),
    }


def resolve(zone: ZoneInfo, text: str) -> dict:
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?", text):
        raise ValueError("invalid local timestamp")
    local = dt.datetime.fromisoformat(text)
    candidates, projections = {}, {}
    for fold in [0, 1]:
        utc = local.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        projected = view(zone, utc)
        projections[utc] = projected
        if projected["local"] == local.isoformat(timespec="microseconds"):
            candidates[utc] = projected
    kind = "gap" if not candidates else "unique" if len(candidates) == 1 else "fold"
    return {
        "kind": kind,
        "local": local.isoformat(timespec="microseconds"),
        "candidates": [candidates[key] for key in sorted(candidates)],
        "projections": [projections[key] for key in sorted(projections)] if kind == "gap" else [],
    }


def reference(fix: Fixture) -> dict:
    data = fix.data()
    zones = {key: ZoneInfo.from_file(io.BytesIO(raw)) for key, raw in data.items()}
    rows = []
    for item in fix.config["appointments"]:
        row = {
            "appointment": item,
            "status": "invalid",
            "reason": "timestamp or projection outside supported range",
            "resolution": None,
            "selected": None,
            "destinations": [],
        }
        try:
            resolution = resolve(zones[item["zone"]], item["local"])
            row["resolution"] = resolution
            kind = resolution["kind"]
            if kind == "unique":
                selected, policy = resolution["candidates"][0], "unique"
            else:
                policy = item["ambiguity" if kind == "fold" else "gap"]
                if policy == "reject":
                    row.update(status="rejected", reason=kind + " requires an explicit selection policy")
                    rows.append(row)
                    continue
                choices = resolution["candidates" if kind == "fold" else "projections"]
                selected = choices[-1 if policy in ["later", "shift_forward"] else 0]
            utc = dt.datetime.fromisoformat(selected["utc"])
            destinations = [{"zone": name, "time": view(zones[name], utc)} for name in fix.config["targets"]]
            row.update(status="converted", reason=policy, selected=selected, destinations=destinations)
        except (ValueError, OverflowError):
            pass
        rows.append(row)
    return {
        "version": 1,
        "appointments": rows,
        "counts": {name: sum(row["status"] == name for row in rows) for name in ["converted", "rejected", "invalid"]},
        "tzif_sha256": {name: digest(raw) for name, raw in data.items()},
    }


def verify(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {
        "report.json",
        "report.txt",
        "schedule.csv",
        "zones.json",
        "timezone-job.json",
        "manifest.json",
    }
    expected = reference(fix)
    assert json.loads(files["report.json"]) == expected
    assert files["report.json"] == (canonical(expected) + "\n").encode()
    assert json.loads(files["zones.json"]) == {name: base64.b64encode(raw).decode() for name, raw in fix.data().items()}
    replay = json.loads(files["timezone-job.json"])
    assert replay == dict(fix.config, tzdata="zones.json", output="replayed")
    manifest = json.loads(files["manifest.json"])
    assert manifest == {
        "version": 1,
        "files": {
            name: {"bytes": len(data), "sha256": digest(data)}
            for name, data in files.items()
            if name != "manifest.json"
        },
    }
    expected_csv = [COLUMNS]
    for row in expected["appointments"]:
        item = row["appointment"]
        prefix = [item["id"], item["label"], row["status"], item["zone"], item["local"]]
        if row["destinations"]:
            for destination in row["destinations"]:
                time = destination["time"]
                expected_csv.append(
                    prefix
                    + [
                        destination["zone"],
                        time["local"],
                        time["utc"],
                        str(time["offset_seconds"]),
                        time["abbreviation"],
                    ]
                )
                assert (destination["zone"] + ": " + time["local"] + " " + time["abbreviation"]) in files[
                    "report.txt"
                ].decode()
        else:
            expected_csv.append(prefix + [""] * 5)
        assert (item["id"] + " " + canonical(item["label"]) + ": " + row["status"]) in files["report.txt"].decode()
    assert list(csv.reader(io.StringIO(files["schedule.csv"].decode(), newline=""))) == expected_csv
    return expected, files


def run(app: Application, fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    before = fix.data()
    staging = set(fix.root.glob(".timezone-*"))
    result = app.run(fix.root, fix.settings, timeout=40)
    expected = reference(fix)
    assert result.returncode == int(expected["counts"]["invalid"] + expected["counts"]["rejected"] > 0), result.stderr
    report, files = verify(fix)
    assert json.loads(result.stdout) == report and fix.data() == before
    assert set(fix.root.glob(".timezone-*")) == staging
    return report, files


def semantics(app: Application, root: Path) -> dict:
    fix = fixture(root / "explicit")
    result, files = run(app, fix)
    hashes = [digest(files["report.json"])]
    rows = {row["appointment"]["id"]: row for row in result["appointments"]}
    assert rows["historical"]["selected"]["offset_seconds"] == 1172
    assert rows["gap2_shift_forward"]["selected"]["local"] == "2024-10-06T02:45:00.000000"
    assert rows["gap2_shift_backward"]["selected"]["local"] == "2024-10-06T01:45:00.000000"
    assert rows["date_line_shift_forward"]["selected"]["local"] == "2011-12-31T12:00:00.000000"
    assert rows["date_line_shift_backward"]["selected"]["local"] == "2011-12-29T12:00:00.000000"
    boundary_rows = []
    for index, (zone, stamp) in enumerate(
        [
            ("America/New_York", "2024-03-10T02:00:00"),
            ("America/New_York", "2024-11-03T02:00:00"),
            ("Australia/Lord_Howe", "2024-10-06T02:30:00"),
            ("Australia/Lord_Howe", "2024-04-07T02:00:00"),
            ("Pacific/Apia", "2011-12-31T00:00:00"),
            ("Europe/Amsterdam", "1937-07-01T00:00:00"),
        ]
    ):
        for shift in [-3600000001, -3600000000, -1, 0, 1, 1799999999, 1800000000, 3600000000]:
            value = dt.datetime.fromisoformat(stamp) + dt.timedelta(microseconds=shift)
            boundary_rows.append(
                appointment(
                    "edge" + str(len(boundary_rows)),
                    value.isoformat(timespec="microseconds"),
                    zone,
                    "later",
                    "shift_forward",
                )
            )
    _, files = run(app, fixture(root / "boundaries", boundary_rows))
    hashes.append(digest(files["report.json"]))
    rng = random.Random(8601)
    names = [
        "UTC",
        "America/New_York",
        "Europe/Dublin",
        "Africa/Casablanca",
        "Asia/Kathmandu",
        "Europe/Amsterdam",
        "Pacific/Apia",
        "Australia/Lord_Howe",
    ]
    for batch in range(4):
        generated = []
        for index in range(128):
            year = rng.choice([1890, 1900, 1970, 2024, 2038, 2050, 2400, 9998])
            value = dt.datetime(year, 1, 1) + dt.timedelta(
                days=rng.randrange(365), seconds=rng.randrange(86400), microseconds=rng.randrange(1000000)
            )
            generated.append(
                appointment(
                    "meeting" + str(index),
                    value.isoformat(timespec="microseconds"),
                    rng.choice(names),
                    rng.choice(["reject", "earlier", "later"]),
                    rng.choice(["reject", "shift_forward", "shift_backward"]),
                )
            )
        _, files = run(app, fixture(root / f"generated-{batch}", generated, names))
        hashes.append(digest(files["report.json"]))
    invalid = [
        "",
        "today",
        "2024-01-01",
        "2024-01-01 12:00:00",
        "2024-01-01t12:00:00",
        "2024-01-01T12:00:00Z",
        "2024-01-01T12:00:00+05:00",
        "2024-01-01T12:00:00.1234567",
        "2024-01-01T12:00:00.",
        "2024-01-01T12:00:00\n",
        "0000-01-01T12:00:00",
        "10000-01-01T12:00:00",
        "1900-02-29T12:00:00",
        "2024-13-01T12:00:00",
        "2024-04-31T12:00:00",
        "2024-01-01T24:00:00",
        "2024-01-01T12:60:00",
        "2016-12-31T23:59:60",
        "２０２４-01-01T00:00:00",
    ]
    report, files = run(
        app,
        fixture(root / "invalid-local", [appointment("bad" + str(i), text, "UTC") for i, text in enumerate(invalid)]),
    )
    assert report["counts"]["invalid"] == len(invalid)
    hashes.append(digest(files["report.json"]))
    edges = [
        appointment("early", "0001-01-01T00:00:00", "Asia/Kathmandu"),
        appointment("late", "9999-12-31T23:59:59.999999", "America/New_York"),
        appointment("project", "9999-12-31T23:59:59.999999", "UTC"),
    ]
    report, files = run(app, fixture(root / "year-overflow", edges, ["UTC", "Asia/Kathmandu"]))
    assert report["counts"]["invalid"] == 3
    hashes.append(digest(files["report.json"]))
    return {
        "explicit_appointments": len(examples()),
        "boundary_appointments": len(boundary_rows),
        "generated_appointments": 512,
        "invalid_local_timestamps": len(invalid),
        "overflow_appointments": 3,
        "reports_sha256": digest(canonical(hashes).encode()),
    }


def rejected(app: Application, fix: Fixture, diagnostic: str = "") -> None:
    before = {path: path.read_bytes() for path in fix.root.rglob("*") if path.is_file()}
    paths = set(fix.root.rglob("*"))
    result = app.run(fix.root, fix.settings)
    assert result.returncode == 2 and diagnostic in result.stderr, (result.returncode, result.stderr)
    assert set(fix.root.rglob("*")) == paths
    assert all(path.read_bytes() == data for path, data in before.items())
    return


def invalid_documents(app: Application, root: Path) -> int:
    mutations = [
        lambda c: c.update(version=2),
        lambda c: c.update(version=True),
        lambda c: c.update(extra=0),
        lambda c: c.update(appointments=[]),
        lambda c: c.update(appointments=c["appointments"] * 257),
        lambda c: c.update(targets=[]),
        lambda c: c.update(targets=["UTC"] * 9),
        lambda c: c.update(targets=["UTC"] * 2),
        lambda c: c.update(output=""),
        lambda c: c.update(tzdata="missing"),
        lambda c: c.update(targets=["../escape"]),
        lambda c: c.update(targets=["/UTC"]),
        lambda c: c.update(targets=["No/Such_Zone"]),
        lambda c: c["appointments"][0].update(id="1bad"),
        lambda c: c["appointments"][0].update(id="a" * 33),
        lambda c: c["appointments"][0].update(id="λ"),
        lambda c: c["appointments"][0].update(label=""),
        lambda c: c["appointments"][0].update(label="λ" * 129),
        lambda c: c["appointments"][0].update(label="a\0b"),
        lambda c: c["appointments"][0].update(label=1),
        lambda c: c["appointments"][0].update(local=None),
        lambda c: c["appointments"][0].update(local="a" * 65),
        lambda c: c["appointments"][0].update(local="a\0b"),
        lambda c: c["appointments"][0].update(zone="UTC/../../escape"),
        lambda c: c["appointments"][0].update(zone="世界"),
        lambda c: c["appointments"][0].update(ambiguity="first"),
        lambda c: c["appointments"][0].update(gap="next"),
        lambda c: c["appointments"].append(c["appointments"][0]),
        lambda c: c["appointments"][0].pop("gap"),
        lambda c: c["appointments"][0].update(extra=1),
    ]
    one = [appointment("meeting", "2024-01-01T00:00:00", "UTC")]
    for index, mutate in enumerate(mutations):
        fix = fixture(root / str(index), one, ["UTC"])
        mutate(fix.config)
        fix.write()
        rejected(app, fix)
    raws = [b"{", b"null", b"{}", b"[]", b"\xff", b'{"version":NaN}']
    for index, raw in enumerate(raws):
        fix = fixture(root / f"raw-{index}", one, ["UTC"])
        (fix.root / "job.json").write_bytes(raw)
        rejected(app, fix)
    bad_zones = [
        b"",
        b"TZif",
        b"x" * 100,
        b"x" * 65537,
        (DATABASE / "UTC").read_bytes()[:28] + struct.pack(">I", 1) + (DATABASE / "UTC").read_bytes()[32:],
    ]
    for index, data in enumerate(bad_zones):
        fix = fixture(root / f"zone-{index}", one, ["UTC"])
        (fix.root / "tzdata/UTC").write_bytes(data)
        rejected(app, fix)
    bundles = [
        {},
        {"UTC": "bad!"},
        {"UTC": 0},
        {"UTC": base64.b64encode(b"bad").decode()},
        {"UTC": "a" * 87385},
        {"UTC": base64.b64encode((DATABASE / "UTC").read_bytes()).decode(), "extra": ""},
    ]
    for index, bundle in enumerate(bundles):
        fix = fixture(root / f"bundle-{index}", one, ["UTC"])
        fix.config["tzdata"] = "zones.json"
        (fix.root / "zones.json").write_text(canonical(bundle))
        fix.write()
        rejected(app, fix)
    return len(mutations) + len(raws) + len(bad_zones) + len(bundles)


def capacity(app: Application, root: Path) -> dict:
    names = [
        "UTC",
        "Europe/Berlin",
        "Asia/Kathmandu",
        "America/New_York",
        "Europe/Dublin",
        "Pacific/Apia",
        "Australia/Lord_Howe",
        "Africa/Casablanca",
        "Asia/Tokyo",
        "Asia/Yekaterinburg",
        "Europe/London",
        "Europe/Amsterdam",
        "Antarctica/Troll",
        "Pacific/Honolulu",
        "America/Los_Angeles",
        "Australia/Sydney",
    ]
    rows = [
        appointment("m" + str(i).zfill(31), "2024-02-29T12:34:56.123456", names[i % 16], label="λ" * 128)
        for i in range(256)
    ]
    fix = fixture(root / "full", rows, names[:8])
    data = fix.data()
    fix.config["tzdata"] = "zones.json"
    (fix.root / "zones.json").write_text(
        canonical({name: base64.b64encode(raw).decode() for name, raw in data.items()})
    )
    shutil.rmtree(fix.root / "tzdata")
    fix.write()
    limits = {"job.json": 262144, "zones.json": 1572864}
    for name, size in limits.items():
        path = fix.root / name
        raw = path.read_bytes()
        assert len(raw) <= size
        path.write_bytes(raw + b" " * (size - len(raw)))

    def limited() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=40,
        preexec_fn=limited,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report, files = verify(fix)
    assert report["counts"]["converted"] == 256
    for name, size in limits.items():
        oversized = fixture(root / ("oversized-" + name), [appointment("only", "2024-01-01T00:00:00", "UTC")], ["UTC"])
        if name == "zones.json":
            oversized.config["tzdata"] = name
            oversized.write()
        path = oversized.root / name
        raw = path.read_bytes() if path.exists() else b"{}"
        path.write_bytes(raw + b" " * (size + 1 - len(raw)))
        rejected(app, oversized, "input byte limit exceeded")
    large = fixture(root / "large-zone", [appointment("only", "2050-01-01T00:00:00", "UTC")], ["UTC"])
    times = 13096
    raw = b"TZif\0" + b"\0" * 15 + struct.pack(">6I", 0, 0, 0, times, 1, 6)
    raw += b"".join(struct.pack(">i", index - times) for index in range(times)) + b"\0" * times
    raw += struct.pack(">iBB", 0, 0, 0) + b"UTC\0\0\0"
    assert len(raw) == 65536
    (large.root / "tzdata/UTC").write_bytes(raw)
    run(app, large)
    excessive = fixture(root / "too-many-zones", rows, names[:8])
    excessive.config["appointments"][0]["zone"] = "Europe/Paris"
    excessive.write()
    rejected(app, excessive, "at most 16")
    return {
        "appointments": 256,
        "targets": 8,
        "zones": 16,
        "input_byte_limits": limits,
        "tzif_bytes": 65536,
        "memory_limit": 268435456,
        "maximum_identifier_characters": 32,
        "maximum_label_bytes": 256,
        "report_sha256": digest(files["report.json"]),
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, TIMEZONE_PAUSE=label, TIMEZONE_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
            if line.strip() == "PAUSED " + label:
                return
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
                result = app.run(fix.root, dict(fix.settings, TIMEZONE_FAULT=label))
                assert result.returncode == 2
                assert not list(fix.root.glob(".timezone-*"))
            if label == "staged":
                assert not fix.output.exists()
                if killed:
                    orphan = next(fix.root.glob(".timezone-*"))
                    original = {p.name: p.read_bytes() for p in orphan.iterdir()}
                    run(app, fix)
                    assert original == {p.name: p.read_bytes() for p in orphan.iterdir()}
                else:
                    run(app, fix)
            else:
                _, files = verify(fix)
                assert app.run(fix.root, fix.settings).returncode == 2
                assert files == {p.name: p.read_bytes() for p in fix.output.iterdir()}
            count += 1
    for name in ["job.json", "tzdata/UTC", "zones.json"]:
        fix = fixture(root / ("live-" + name.replace("/", "-")))
        if name == "zones.json":
            data = {key: base64.b64encode(raw).decode() for key, raw in fix.data().items()}
            (fix.root / name).write_text(canonical(data))
            fix.config["tzdata"] = name
            fix.write()
        process = paused(app, fix, "staged")
        path = fix.root / name
        path.write_bytes(path.read_bytes() + b" ")
        (fix.root / "release").write_text("resume")
        process.communicate(timeout=10)
        assert process.returncode == 2 and not fix.output.exists() and not list(fix.root.glob(".timezone-*"))
        count += 1
    for kind in ["symlink", "hardlink"]:
        fix = fixture(root / ("alias-" + kind))
        path, target = fix.root / "tzdata/UTC", fix.root / "tzdata/Universal"
        path.rename(target)
        if kind == "symlink":
            path.symlink_to(target)
        else:
            os.link(target, path)
        run(app, fix)
        count += 1
    for kind in ["escape", "config-link", "directory", "file", "dangling"]:
        fix = fixture(root / kind)
        if kind == "escape":
            path = fix.root / "tzdata/UTC"
            path.unlink()
            path.symlink_to(DATABASE / "UTC")
        elif kind == "config-link":
            path = fix.root / "job.json"
            path.rename(fix.root / "original.json")
            path.symlink_to(fix.root / "original.json")
        elif kind == "directory":
            fix.output.mkdir()
        elif kind == "file":
            fix.output.write_text("keep")
        else:
            fix.output.symlink_to(fix.root / "missing")
        rejected(app, fix)
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
            stdout, stderr = process.communicate(timeout=30)
            assert process.returncode in [1, 2], (stdout, stderr)
            results.append(process.returncode)
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    assert results.count(1) == 1 and not list(fix.root.glob(".timezone-*"))
    verify(fix)
    return {"failure_and_alias_checks": count, "concurrent_writers": 8, "successful_publications": 1}


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid_documents": invalid_documents(app, directory / "invalid"),
        "capacity": capacity(app, directory / "capacity"),
        "publication": publication(app, directory / "publication"),
        "independent_zoneinfo_oracle": True,
    }
