"""Independent gzip decoding and durable-index checks for the complete archiver."""

# ruff: noqa: PLR1711 - explicit returns
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application

DEFAULT = {"source_bytes": 8388608, "compressed_bytes": 9437184, "total_bytes": 33554432}
FIELDS = {"id", "source", "size", "sha256", "compressed_size", "compressed_sha256", "level"}
POINTS = ["streaming", "closed", "prepared", "published", "indexed"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    return


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob("*") if p.is_file() and not p.is_symlink()
    }


def fixture(root: Path, data: dict[str, bytes] | None = None) -> tuple[dict, dict[str, bytes]]:
    root.mkdir(parents=True)
    data = (
        {"access-001": b"GET /api/chats 200\n" * 100, "notes_001": "Saved notes — 世界\n".encode(), "empty": b""}
        if data is None
        else data
    )
    config = {
        "version": 1,
        "mode": "archive",
        "directory": "archives",
        "inputs": [],
        "level": 6,
        "limits": dict(DEFAULT),
    }
    for name, raw in data.items():
        path = name + ".log"
        (root / path).write_bytes(raw)
        config["inputs"].append({"id": name, "path": path})
    save(root / "gzip-job.json", config)
    return config, data


def operation(config: dict, mode: str) -> dict:
    return {
        key: mode if key == "mode" else copy.deepcopy(value)
        for key, value in config.items()
        if key not in {"inputs", "level"}
    }


def inspect(root: Path, expected: dict[str, bytes] | None = None) -> dict:
    index = json.loads((root / "index.json").read_bytes())
    assert set(index) == {"version", "format", "entries"} and index["version"] == 1
    assert index["format"] == "py2rust-gzip-log-index"
    rows = index["entries"]
    assert len(rows) == len({row["id"] for row in rows})
    if expected is not None:
        assert {row["id"] for row in rows} == set(expected), (root, rows, expected.keys())
    for row in rows:
        assert set(row) == FIELDS and type(row["size"]) is int and type(row["compressed_size"]) is int
        encoded = (root / (row["id"] + ".gz")).read_bytes()
        assert len(encoded) == row["compressed_size"] and digest(encoded) == row["compressed_sha256"]
        actual = gzip.decompress(encoded)
        assert len(actual) == row["size"] and digest(actual) == row["sha256"]
        if expected is not None:
            assert actual == expected[row["id"]], (root, row)
    return {
        "completed": len(rows),
        "bytes": sum(row["size"] for row in rows),
        "compressed_bytes": sum(row["compressed_size"] for row in rows),
        "pending": (root / "pending.json").exists() or (root / ".stage.gz").exists(),
    }


def run(app: Application, root: Path, config: dict, expected: dict[str, bytes] | None = None) -> dict:
    save(root / "gzip-job.json", config)
    originals = {row["path"]: digest((root / row["path"]).read_bytes()) for row in config.get("inputs", [])}
    result = app.run(root, {}, timeout=240)
    assert result.returncode == 0 and not result.stderr, (root, result)
    summary = inspect(root / config["directory"], expected)
    assert json.loads(result.stdout) == summary, (root, result.stdout, summary)
    assert all(digest((root / name).read_bytes()) == sha for name, sha in originals.items())
    return summary


def reject(app: Application, root: Path, config: dict | None = None, needle: str = "") -> None:
    if config is not None:
        save(root / "gzip-job.json", config)
    result = app.run(root, {}, timeout=120)
    assert result.returncode == 2 and not result.stdout and result.stderr, (root, result)
    assert needle in result.stderr, (needle, result.stderr)
    return


def pause(app: Application, root: Path, config: dict, point: str) -> subprocess.Popen:
    save(root / "gzip-job.json", config)
    release = root / "release"
    release.unlink(missing_ok=True)
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"GZIP_PAUSE": point, "GZIP_RELEASE": str(release)}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert select.select([process.stdout], [], [], 30)[0], (root, point, "no checkpoint")
        assert process.stdout.readline().strip() == "PAUSED " + point, (root, point)
        assert process.poll() is None
        return process
    except BaseException:
        process.kill()
        process.communicate(timeout=5)
        raise


def semantics(app: Application, root: Path) -> dict:
    config, data = fixture(root)
    first = run(app, root, config, data)
    preserved = snapshot(root / "archives")
    assert run(app, root, config, data) == first
    assert snapshot(root / "archives") == preserved
    assert run(app, root, operation(config, "verify"), data) == first
    assert snapshot(root / "archives") == preserved
    (root / "new.log").write_bytes(b"rotated after checkpoint\0\xff\n")
    config["inputs"].append({"id": "next", "path": "new.log"})
    data["next"] = (root / "new.log").read_bytes()
    run(app, root, config, data)
    (root / "access-001.log").write_bytes(b"ID reuse with changed bytes")
    before = snapshot(root / "archives")
    reject(app, root, config, "different source bytes")
    assert snapshot(root / "archives") == before
    for item in config["inputs"]:
        (root / item["path"]).unlink()
    run(app, root, operation(config, "verify"), data)
    run(app, root, operation(config, "recover"), data)
    return {
        "initial_logs": 3,
        "appended_logs": 1,
        "idempotent_restart": True,
        "changed_id_rejected": True,
        "verification_independent_of_original_files": True,
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(119)
    portable = []
    for case in range(12):
        data = {
            f"log-{index}": rng.randbytes(rng.randrange(4097)) + ("世界\n" * rng.randrange(20)).encode()
            for index in range(rng.randrange(1, 9))
        }
        config, _ = fixture(root / str(case), data)
        config["level"] = case % 10
        run(app, root / str(case), config, data)
        run(app, root / str(case), operation(config, "verify"), data)
        portable.append({name: {"size": len(raw), "sha256": digest(raw)} for name, raw in data.items()})
    return {
        "seed": 119,
        "projects": 12,
        "logs": sum(len(row) for row in portable),
        "logical_sha256": digest(json.dumps(portable, sort_keys=True).encode()),
    }


def recovery(app: Application, root: Path) -> dict:
    for kind in ["exception", "kill"]:
        for point in POINTS:
            home = root / kind / point
            config, data = fixture(home, {"old": b"already committed\n"})
            run(app, home, config, data)
            (home / "new.log").write_bytes(bytes(range(256)) * 1024)
            new = (home / "new.log").read_bytes()
            config["inputs"].append({"id": "new", "path": "new.log"})
            if kind == "exception":
                save(home / "gzip-job.json", config)
                result = app.run(home, {"GZIP_FAULT": point}, timeout=90)
                assert result.returncode == 2 and "injected failure" in result.stderr and not result.stdout, result
            else:
                process = pause(app, home, config, point)
                try:
                    inspect(home / "archives", dict(data, new=new) if point == "indexed" else data)
                    reject(app, home, config)
                    process.kill()
                    process.communicate(timeout=5)
                    assert process.returncode < 0
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate(timeout=5)
            visible = dict(data, new=new) if point == "indexed" else data
            assert run(app, home, operation(config, "verify"), visible)["pending"]
            completed = dict(data, new=new) if point in ["prepared", "published", "indexed"] else data
            assert not run(app, home, operation(config, "recover"), completed)["pending"]
            assert not run(app, home, config, dict(data, new=new))["pending"]
    return {
        "caught_failures": 5,
        "hard_kills": 5,
        "completed_index_checked_while_paused": True,
        "incomplete_never_indexed": True,
        "recovered_and_retried": True,
        "concurrent_process_rejected": True,
    }


def races(app: Application, root: Path) -> dict:
    for kind in ["append", "replace", "rotate_after_prepared", "destination_collision"]:
        home = root / kind
        config, data = fixture(home, {"log": b"a" * 131073})
        point = "streaming" if kind in ["append", "replace"] else "prepared"
        process = pause(app, home, config, point)
        try:
            if kind == "append":
                with (home / "log.log").open("ab") as output:
                    output.write(b"changed")
            elif kind == "replace":
                (home / "replacement").write_bytes(b"other file")
                (home / "replacement").replace(home / "log.log")
            elif kind == "rotate_after_prepared":
                (home / "log.log").rename(home / "rotated.log")
            else:
                (home / "archives/log.gz").write_bytes(b"foreign file")
            (home / "release").write_text("continue")
            stdout, stderr = process.communicate(timeout=60)
            if kind == "rotate_after_prepared":
                assert process.returncode == 0 and not stderr
                assert json.loads(stdout) == inspect(home / "archives", data)
            else:
                assert process.returncode == 2 and stderr and not stdout
                index = json.loads((home / "archives/index.json").read_bytes())
                assert not index["entries"]
                if kind == "destination_collision":
                    assert (home / "archives/log.gz").read_bytes() == b"foreign file"
                    (home / "archives/log.gz").unlink()
                    run(app, home, operation(config, "recover"), data)
                else:
                    run(app, home, operation(config, "recover"), {})
                    run(app, home, config, {"log": (home / "log.log").read_bytes()})
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    return {
        "source_and_publication_races": 4,
        "captured_log_survives_later_rotation": True,
        "foreign_destination_preserved": True,
    }


def invalid(app: Application, root: Path) -> dict:
    base, _ = fixture(root / "template")
    variants = []
    for field, values in {
        "version": [0, 2, True, 1.0, "1"],
        "mode": ["", "delete", None],
        "directory": ["", "\0", 1, "x" * 4097],
        "level": [-1, 10, True, 6.0],
        "inputs": [
            None,
            {},
            [{"id": "duplicate", "path": "x"}] * 2,
            [{"id": "x", "path": ""}],
            [{"id": "../escape", "path": "x"}],
        ],
    }.items():
        for value in values:
            candidate = copy.deepcopy(base)
            candidate[field] = value
            variants.append(candidate)
    for key, maximum in [("source_bytes", 1073741824), ("compressed_bytes", 2147483648), ("total_bytes", 4294967296)]:
        for value in [-1, maximum + 1, True, 1.0, "100"]:
            candidate = copy.deepcopy(base)
            candidate["limits"][key] = value
            variants.append(candidate)
    variants.append(dict(base, unexpected=1))
    for key in base:
        candidate = copy.deepcopy(base)
        del candidate[key]
        variants.append(candidate)
    for number, config in enumerate(variants):
        home = root / str(number)
        fixture(home)
        reject(app, home, config)
        assert not (home / "archives").exists(), home
    malformed = ["{", "[]", "null", '{"version":1,"version":1}', '{"value":NaN}', '{"x":Infinity}']
    for number, raw in enumerate(malformed):
        home = root / ("json-" + str(number))
        fixture(home)
        (home / "gzip-job.json").write_text(raw)
        reject(app, home)
        assert not (home / "archives").exists()
    return {"invalid_requests": len(variants), "malformed_json": len(malformed)}


def corruption(app: Application, root: Path) -> dict:
    config, data = fixture(root, {"log": b"CRC, index and file metadata\n" * 8})
    run(app, root, config, data)
    archive = root / "archives"
    index = json.loads((archive / "index.json").read_bytes())
    # Mutate one independently encoded stream in both engines. Native encoders
    # need not produce identical DEFLATE blocks or compressed lengths.
    encoded = gzip.compress(data["log"], compresslevel=6, mtime=0)
    index["entries"][0].update(compressed_size=len(encoded), compressed_sha256=digest(encoded))
    save(archive / "index.json", index)
    (archive / "log.gz").write_bytes(encoded)
    original = (archive / "index.json").read_bytes()
    verify = operation(config, "verify")
    mutations = []
    for key, value in [("version", True), ("version", 2), ("format", "foreign"), ("entries", {})]:
        updated = copy.deepcopy(index)
        updated[key] = value
        mutations.append(updated)
    for key, value in [
        ("id", "../x"),
        ("source", None),
        ("size", True),
        ("size", len(data["log"]) + 1),
        ("sha256", "0" * 64),
        ("compressed_size", len(encoded) - 1),
        ("compressed_sha256", "a" * 64),
        ("level", 10),
    ]:
        updated = copy.deepcopy(index)
        updated["entries"][0][key] = value
        mutations.append(updated)
    updated = copy.deepcopy(index)
    updated["entries"].append(updated["entries"][0].copy())
    mutations.append(updated)
    for updated in mutations:
        save(archive / "index.json", updated)
        preserved = snapshot(archive)
        reject(app, root, verify)
        assert snapshot(archive) == preserved
    broken = [encoded[:length] for length in range(len(encoded))]
    broken += [encoded + suffix for suffix in [b"\0", b"x", gzip.compress(b"second", mtime=0)]]
    for offset in [0, 1, 2, 3, -1, -5, -8]:
        changed = bytearray(encoded)
        changed[offset] ^= 255
        broken.append(bytes(changed))
    for raw in broken:
        changed = copy.deepcopy(index)
        changed["entries"][0].update(compressed_size=len(raw), compressed_sha256=digest(raw))
        save(archive / "index.json", changed)
        (archive / "log.gz").write_bytes(raw)
        preserved = snapshot(archive)
        reject(app, root, verify)
        assert snapshot(archive) == preserved
    (archive / "index.json").write_bytes(original)
    (archive / "log.gz").write_bytes(encoded)
    run(app, root, verify, data)
    return {
        "inconsistent_indices": len(mutations),
        "corrupt_truncated_and_trailing_streams": len(broken),
        "failed_verification_preserves_files": True,
    }


def limits(app: Application, root: Path) -> dict:
    for number, settings in enumerate(
        [
            {"source_bytes": 4, "compressed_bytes": 1000, "total_bytes": 8},
            {"source_bytes": 3, "compressed_bytes": 1000, "total_bytes": 8},
            {"source_bytes": 4, "compressed_bytes": 1000, "total_bytes": 7},
            {"source_bytes": 4, "compressed_bytes": 20, "total_bytes": 8},
        ]
    ):
        home = root / str(number)
        config, data = fixture(home, {"one": b"abcd", "two": b"efgh"})
        config["limits"] = settings
        if number == 0:
            run(app, home, config, data)
        else:
            reject(app, home, config)
            expected = {"one": b"abcd"} if number == 2 else {}
            inspect(home / "archives", expected)
            config["limits"] = dict(DEFAULT)
            run(app, home, config, data)
    many = {f"file-{index}": b"" for index in range(128)}
    config, _ = fixture(root / "count", many)
    config["limits"].update(source_bytes=0, total_bytes=0)
    run(app, root / "count", config, many)
    config["inputs"] = [{"id": "extra", "path": "extra.log"}]
    (root / "count/extra.log").write_bytes(b"")
    reject(app, root / "count", config, "count limit")
    assert inspect(root / "count/archives", many)["completed"] == 128
    return {
        "source_compressed_aggregate_budget_cases": 4,
        "completed_archive_count": 128,
        "zero_byte_logs": True,
        "budget_failure_retried": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    for kind in [
        "source_symlink",
        "source_hardlink",
        "source_directory",
        "source_fifo",
        "output_symlink",
        "foreign_directory",
    ]:
        home = root / kind
        config, _ = fixture(home, {"log": b"preserved"})
        if kind.startswith("source_"):
            (home / "log.log").rename(home / "original")
            if kind == "source_symlink":
                (home / "log.log").symlink_to("original")
            elif kind == "source_hardlink":
                os.link(home / "original", home / "log.log")
            elif kind == "source_directory":
                (home / "log.log").mkdir()
            else:
                os.mkfifo(home / "log.log")
        elif kind == "output_symlink":
            (home / "elsewhere").mkdir()
            (home / "archives").symlink_to("elsewhere", target_is_directory=True)
        else:
            (home / "archives").mkdir()
            (home / "archives/foreign.txt").write_bytes(b"keep me")
        reject(app, home, config)
        if kind.startswith("source_"):
            assert (home / "original").read_bytes() == b"preserved"
        if kind == "foreign_directory":
            assert (home / "archives/foreign.txt").read_bytes() == b"keep me"
    for name in ["index.json", ".lock", ".stage.gz", ".index.json.tmp", ".pending.json.tmp"]:
        home = root / ("managed-" + name)
        config, data = fixture(home, {"log": b"existing"})
        run(app, home, config, data)
        (home / "foreign").write_bytes(b"untouched")
        path = home / "archives" / name
        path.unlink(missing_ok=True)
        path.symlink_to("../foreign")
        reject(app, home, operation(config, "recover"))
        assert (home / "foreign").read_bytes() == b"untouched" and path.is_symlink()
    return {"guarded_path_cases": 11}


def memory(app: Application, root: Path) -> dict:
    config, _ = fixture(root, {})
    size = 1073741824
    source = root / "large.log"
    with source.open("wb") as output:
        output.write(b"first network log record\n")
        output.truncate(size)
        output.seek(size - 32)
        output.write(b"last network log record".ljust(32, b"\n"))
    expected = hashlib.sha256()
    with source.open("rb") as input_file:
        while chunk := input_file.read(1048576):
            expected.update(chunk)
    config["inputs"] = [{"id": "large", "path": "large.log"}]
    config["limits"] = {"source_bytes": size, "compressed_bytes": 2147483648, "total_bytes": 4294967296}
    save(root / "gzip-job.json", config)
    result = subprocess.run(
        ["/usr/bin/prlimit", "--as=134217728", "--", *app.command],
        cwd=root,
        env=app.environment({}),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr, result
    summary = json.loads(result.stdout)
    assert summary["completed"] == 1 and summary["bytes"] == size and not summary["pending"]
    row = json.loads((root / "archives/index.json").read_bytes())["entries"][0]
    assert row["size"] == size and row["sha256"] == expected.hexdigest()
    actual = hashlib.sha256()
    length = 0
    with gzip.open(root / "archives/large.gz", "rb") as decoded:
        while chunk := decoded.read(1048576):
            actual.update(chunk)
            length += len(chunk)
    assert length == size and actual.digest() == expected.digest()
    encoded = (root / "archives/large.gz").read_bytes()
    assert len(encoded) == row["compressed_size"] == summary["compressed_bytes"]
    assert digest(encoded) == row["compressed_sha256"]
    before = snapshot(root / "archives")
    with source.open("ab") as output:
        output.write(b"x")
    config["inputs"] = [{"id": "too-large", "path": "large.log"}]
    reject(app, root, config, "source exceeds expansion budget")
    assert snapshot(root / "archives") == before
    return {
        "maximum_source_bytes": size,
        "address_space_bytes": 134217728,
        "original_sha256": expected.hexdigest(),
        "independent_streaming_decode": True,
        "one_byte_over_maximum_rejected": True,
    }


def check(app: Application, root: Path) -> dict:
    observations = {}
    for name, function in [
        ("semantics", semantics),
        ("generated", generated),
        ("recovery", recovery),
        ("races", races),
        ("invalid", invalid),
        ("corruption", corruption),
        ("limits", limits),
        ("filesystem", filesystem),
        ("memory", memory),
    ]:
        observations[name] = function(app, root / name)
        print(app.engine + " gzip " + name + ": passed", flush=True)
    return observations
