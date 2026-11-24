"""Independent UTC grouping, exact occurrence accounting, manifests and publication checks."""

from __future__ import annotations

import hashlib
import json
import random
import selectors
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .common import Application
from .csv_json import canonical


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def data(rows: list, ending: str = "\n", terminal: bool = True) -> bytes:
    text = ending.join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows)
    return (text + (ending if rows and terminal else "")).encode()


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def source(self) -> Path:
        return self.work / self.config["input"]

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        (self.work / "partition-job.json").write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "PARTITION_CONFIG": str(self.work / "partition-job.json"),
            "PARTITION_MODE": mode,
            "PARTITION_FAIL": "",
            "PARTITION_PAUSE": "",
            "PARTITION_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, source: bytes, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    config = {
        "input": "input.jsonl",
        "output": "partitioned",
        "timestamp_field": "timestamp",
        "topic_field": "topic",
        "max_rows": 10000,
        "max_line_bytes": 65536,
        "max_input_bytes": 4194304,
        "max_shards": 256,
        **changes,
    }
    fix = Fixture(work, config)
    (work / "input.jsonl").write_bytes(source)
    fix.save()
    return fix


def oracle(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    raw = fix.source.read_bytes()
    lines = raw.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    groups = defaultdict(list)
    for number, line in enumerate(lines, 1):
        row = json.loads(line)
        moment = datetime.fromisoformat(row[fix.config["timestamp_field"]]).astimezone(timezone.utc)
        day = f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"
        groups[day, row[fix.config["topic_field"]]].append((number, row))
    shards, files = [], {}
    for (day, topic), members in sorted(groups.items()):
        name = day + "--" + digest(topic.encode()) + ".jsonl"
        encoded = b"".join((canonical(row) + "\n").encode() for _, row in members)
        files[name] = encoded
        shards.append(
            {
                "date": day,
                "topic": topic,
                "file": name,
                "rows": len(members),
                "bytes": len(encoded),
                "sha256": digest(encoded),
                "first_line": members[0][0],
                "last_line": members[-1][0],
            }
        )
    manifest = {
        "version": 1,
        "input_sha256": digest(raw),
        "input_bytes": len(raw),
        "rows": len(lines),
        "shard_bytes": sum(len(value) for value in files.values()),
        "timestamp_field": fix.config["timestamp_field"],
        "topic_field": fix.config["topic_field"],
        "shards": shards,
    }
    return manifest, files


def outputs(fix: Fixture, manifest: dict, files: dict[str, bytes]) -> None:
    assert sorted(path.name for path in fix.output.iterdir()) == sorted([*files, "manifest.json"])
    assert json.loads((fix.output / "manifest.json").read_bytes()) == manifest
    for name, expected in files.items():
        assert (fix.output / name).read_bytes() == expected
    assert sum(shard["rows"] for shard in manifest["shards"]) == manifest["rows"]
    assert not list(fix.work.glob(".jsonl-partition-*"))
    return  # noqa: PLR1711


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    manifest, files = oracle(fix)
    before = fix.source.read_bytes()
    result = app.run(fix.work, fix.settings(mode), timeout=45)
    assert result.returncode == 0 and not result.stderr, (result, fix.config)
    assert json.loads(result.stdout) == manifest
    assert fix.source.read_bytes() == before
    if mode == "write":
        outputs(fix, manifest, files)
        assert (fix.output / "manifest.json").read_text() == result.stdout
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".jsonl-partition-*"))
    return manifest


def failure(app: Application, fix: Fixture, message: str, **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    original = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=45)
    assert result.returncode == 2 and message in result.stderr and result.stdout == "", (result, message, fix.config)
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if original is not None:
        assert fix.output.read_bytes() == original
    assert not list(fix.work.glob(".jsonl-partition-*"))
    return  # noqa: PLR1711


def sample() -> list[dict]:
    return [
        {"timestamp": "2026-10-07T00:30:00+02:00", "topic": "network/metrics", "id": 1, "value": 1.25},
        {"timestamp": "2026-10-06T23:30:00-03:00", "topic": "network/metrics", "id": 2, "value": -0.0},
        {"timestamp": "2026-10-07T03:00:00Z", "topic": "世界", "id": 3, "value": [True, None, {"n": 2**63 - 1}]},
        {"timestamp": "2026-10-06T21:00:00Z", "topic": "network/metrics", "id": 4, "value": -(2**63)},
        {"timestamp": "2026-10-07T03:00:00Z", "topic": "../../outside\x00\n", "id": 5, "value": "😀"},
    ]


def paused(app: Application, fix: Fixture, checkpoint: str) -> subprocess.Popen:
    signal = fix.work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(PARTITION_PAUSE=checkpoint, PARTITION_CONTINUE=str(signal))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(10):
            process.kill()
            process.communicate(timeout=5)
            raise AssertionError("partition writer did not pause")
        line = process.stdout.readline()
    if line != "PAUSED " + checkpoint + "\n":
        process.kill()
        output, error = process.communicate(timeout=5)
        raise AssertionError((line, output, error))
    return process


def publication(app: Application, directory: Path) -> int:
    raw = data(sample())
    template = fixture(directory, "publication-template", raw)
    manifest, files = oracle(template)
    points = ["validated", "stage", *files, "manifest.json", "ready", "published"]
    for index, point in enumerate(points):
        fix = fixture(directory, f"fault-{index}", raw)
        result = app.run(fix.work, fix.settings(PARTITION_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        if point == "published":
            outputs(fix, manifest, files)
        else:
            assert not fix.output.exists()
            assert not list(fix.work.glob(".jsonl-partition-*"))
            success(app, fix)
    for name in ["input", "configuration", "destination"]:
        fix = fixture(directory, "changed-" + name, raw)
        process = paused(app, fix, "ready")
        try:
            if name == "input":
                fix.source.write_bytes(data([*sample(), sample()[0]]))
            elif name == "configuration":
                with (fix.work / "partition-job.json").open("a") as stream:
                    stream.write(" ")
            else:
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"other writer")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=10)
            assert process.returncode == 2 and not output, (output, error)
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"other writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
            assert not list(fix.work.glob(".jsonl-partition-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    fix = fixture(directory, "terminated", raw)
    process = paused(app, fix, "ready")
    process.kill()
    process.communicate(timeout=5)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".jsonl-partition-*"))
    assert len(abandoned) == 1 and (abandoned[0] / "manifest.json").exists()
    # A later run uses a fresh staging name and leaves the interrupted writer's files alone.
    before = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and json.loads(result.stdout) == manifest
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == before
    for name, expected in files.items():
        assert (fix.output / name).read_bytes() == expected
    for kind in ["file", "directory", "symlink", "dangling", "same-input", "same-config"]:
        fix = fixture(directory, "existing-" + kind, raw)
        if kind == "file":
            fix.output.write_bytes(b"keep")
        elif kind == "directory":
            fix.output.mkdir()
        elif kind in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.source if kind == "symlink" else fix.work / "absent")
        else:
            fix.config["output"] = "input.jsonl" if kind == "same-input" else "partition-job.json"
            fix.save()
        original = fix.output.read_bytes() if fix.output.is_file() else None
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and "output directory already exists" in result.stderr
        if original is not None:
            assert fix.output.read_bytes() == original
        assert not list(fix.work.glob(".jsonl-partition-*"))
    return len(points) + 3 + 1 + 6


def limits(app: Application, directory: Path) -> int:
    row = sample()[0]
    for name, count, config in [
        ("rows", 10000, {}),
        ("shards", 256, {}),
    ]:
        rows = [dict(row, topic=str(index) if name == "shards" else "same") for index in range(count)]
        success(app, fixture(directory, name + "-exact", data(rows), **config))
        extra = dict(row, topic=str(count))
        failure(
            app,
            fixture(directory, name + "-over", data([*rows, extra])),
            "input row limit exceeded" if name == "rows" else "shard count limit exceeded",
        )
    raw = data([row])[:-1]
    success(app, fixture(directory, "line-exact", raw + b" " * (65536 - len(raw))))
    failure(app, fixture(directory, "line-over", raw + b" " * (65537 - len(raw))), "line byte limit exceeded")
    block = raw + b" " * (65535 - len(raw)) + b"\n"
    success(app, fixture(directory, "bytes-exact", block * 64))
    failure(app, fixture(directory, "bytes-over", block * 64 + b" "), "input byte limit exceeded")
    success(app, fixture(directory, "topic-exact", data([dict(row, topic="😀" * 64)])))
    failure(app, fixture(directory, "topic-over", data([dict(row, topic="😀" * 64 + "a")])), "topic must contain")
    key = "é" * 64
    success(app, fixture(directory, "field-exact", data([{key: row["timestamp"], "topic": "a"}]), timestamp_field=key))
    failure(app, fixture(directory, "field-over", b"", timestamp_field=key + "a"), "field name must contain")
    fix = fixture(directory, "config-exact", b"")
    path = fix.work / "partition-job.json"
    original = path.read_bytes()
    path.write_bytes(original + b" " * (65536 - len(original)))
    success(app, fix)
    fix = fixture(directory, "config-over", b"")
    (fix.work / "partition-job.json").write_bytes(b" " * 65537)
    failure(app, fix, "input byte limit exceeded")
    expanded = dict(row, values=[0.1] * 10000)
    failure(app, fixture(directory, "output-over", data([expanded] * 80)), "total shard data exceeds 16 MiB")
    return 15


def check(app: Application, directory: Path) -> dict:
    observations = []
    cases = [[], sample(), [*sample(), sample()[0], sample()[0]]]
    cases.append([dict(sample()[0], topic=topic) for topic in ["x", "X", "é", "e\u0301", " ", "/", ".", "..", "\\"]])
    cases.append(
        [
            dict(sample()[0], timestamp=value)
            for value in [
                "0001-01-01T00:00:00Z",
                "9999-12-31T23:59:59Z",
                "2024-02-29T23:30:00-01:00",
                "2026-01-01T00:30:00+01:00",
                "2026-10-07T12:34:56.123456Z",
            ]
        ]
    )
    rng = random.Random(500050)
    for _ in range(24):
        cases.append(
            [
                {
                    "timestamp": f"2026-10-{rng.randrange(1, 29):02d}T00:30:00+02:00",
                    "topic": rng.choice(["network", "世界", "", "a/b", "x\x00y"]) or "empty label",
                    "id": index,
                    "payload": [rng.randrange(-10000, 10000), None, True, rng.random()],
                }
                for index in range(rng.randrange(1, 101))
            ]
        )
    for index, rows in enumerate(cases):
        fix = fixture(directory, f"group-{index}", data(rows, "\r\n" if index % 2 else "\n", index % 3 != 0))
        observations.append(success(app, fix, "preview"))
        success(app, fix)
        again = fixture(directory, f"repeat-{index}", fix.source.read_bytes())
        success(app, again)
        assert {p.name: p.read_bytes() for p in fix.output.iterdir()} == {
            p.name: p.read_bytes() for p in again.output.iterdir()
        }
    success(
        app,
        fixture(
            directory,
            "custom-fields",
            data([{"when": "2026-01-01T00:00:00Z", "kind": "custom"}]),
            timestamp_field="when",
            topic_field="kind",
        ),
    )
    bad_rows = [None, [], True, 7, "text", {}, {"topic": "x"}, {"timestamp": "2026-01-01T00:00:00Z"}]
    bad_rows.extend(
        dict(sample()[0], timestamp=value) for value in [None, False, 0, "2026-01-01", "bad", "2026-02-30T00:00:00Z"]
    )
    bad_rows.extend(dict(sample()[0], topic=value) for value in [None, 1, True, [], {}, ""])
    for index, row in enumerate(bad_rows):
        failure(app, fixture(directory, f"record-{index}", data([sample()[0], row, sample()[1]])), "line 2:")
    malformed = [
        b"\n",
        b" \n",
        b"{}\n\n",
        b"{bad}\n",
        b"[]\n",
        b'{"x":1e309}\n',
        b"[NaN]\n",
        b'{"x":9223372036854775808}\n',
        b"\xff\n",
        b'{"x":"\\ud800"}\n',
    ]
    for index, raw in enumerate(malformed):
        failure(app, fixture(directory, f"malformed-{index}", raw), "")
    invalid = [
        {"extra": 1},
        {"timestamp_field": ""},
        {"topic_field": ""},
        {"topic_field": "timestamp"},
        {"timestamp_field": True},
        {"input": ""},
        {"input": "\x00"},
        {"input": False},
        {"output": ""},
    ]
    for name, maximum in [
        ("max_rows", 10000),
        ("max_line_bytes", 65536),
        ("max_input_bytes", 4194304),
        ("max_shards", 256),
    ]:
        invalid.extend({name: value} for value in [0, -1, maximum + 1, True, 1.0, "1"])
    for index, changes in enumerate(invalid):
        failure(app, fixture(directory, f"config-{index}", data(sample()), **changes), "")
    failure(app, fixture(directory, "bad-mode", b""), "invalid partition mode", PARTITION_MODE="bad")
    for name in ["input", "configuration"]:
        fix = fixture(directory, "link-" + name, data(sample()))
        path = fix.source if name == "input" else fix.work / "partition-job.json"
        target = path.with_suffix(".original")
        path.rename(target)
        path.symlink_to(target)
        failure(app, fix, "input must be a regular file")
    return {
        "datasets": len(cases),
        "previews": len(cases),
        "exact_repeats": len(cases),
        "custom_fields": 1,
        "invalid_records": len(bad_rows),
        "malformed_inputs": len(malformed),
        "invalid_configs": len(invalid) + 1,
        "input_symlinks": 2,
        "capacity_checks": limits(app, directory),
        "publication_checks": publication(app, directory),
        "manifest_sha256": digest(canonical(observations).encode()),
    }
