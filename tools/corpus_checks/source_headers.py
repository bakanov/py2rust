"""Independent exact-output, byte-splice, policy, replay and publication tests for source headers."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import select
import subprocess
import time
from pathlib import Path

from .common import Application
from .header_fixture import POLICY, canonical, cases


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n")
    return  # noqa: PLR1711


def fixture(root: Path, files: dict[str, tuple] | None = None, policy: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for number, (name, row) in enumerate((cases() if files is None else files).items()):
        path = f"input-{number}.txt"
        (root / path).write_bytes(row[0])
        entries.append({"name": name, "path": path, "style": row[1]})
    config = {
        "version": 1,
        "mode": "check",
        "output": "inspection",
        "policy": POLICY if policy is None else policy,
        "files": entries,
    }
    save(root / "headers-job.json", config)
    return config


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def inspect_bundle(root: Path, config: dict, expected: dict | None = None) -> dict:
    output = root / config["output"]
    report = json.loads((output / "report.json").read_bytes())
    plan = json.loads((output / "patches.json").read_bytes())
    assert set(report) == {"version", "mode", "policy", "files", "groups", "summary"}
    assert report["version"] == 1 and report["mode"] == config["mode"]
    assert set(plan) == {"version", "policy", "files"} and plan["version"] == 1
    assert plan["policy"] == report["policy"]
    source_entries = config.get("files")
    source_base = root
    if config["mode"] == "apply":
        patch_file = root / config["patches"]
        source_entries = json.loads(patch_file.read_bytes())["files"]
        source_base = patch_file.parent
    else:
        assert report["policy"] == config["policy"]
    names = {"report.json", "report.txt", "patches.json", "apply.json", "replay.json"}
    replay, recheck = [], []
    counts = {"files": len(source_entries), "violations": 0, "remaining": 0, "changed_files": 0, "manual_files": 0}
    grouped = {}
    assert len(report["files"]) == len(plan["files"]) == len(source_entries)
    for entry, row, patch in zip(source_entries, report["files"], plan["files"], strict=True):
        name = entry["name"]
        data = (source_base / entry["path"]).read_bytes()
        assert row["name"] == patch["name"] == name and patch["style"] == entry["style"]
        assert set(row) == {"name", "issues", "remaining", "manual", "before_sha256", "after_sha256"}
        assert set(patch) == {"name", "path", "style", "before_sha256", "after_sha256", "edit"}
        assert patch["path"] == "sources/" + name
        assert (output / patch["path"]).read_bytes() == data
        names.add(patch["path"])
        after = data
        if patch["edit"] is not None:
            edit = patch["edit"]
            assert set(edit) == {"start", "end", "removed", "replacement"}
            start, end = edit["start"], edit["end"]
            assert type(start) is int and type(end) is int and 0 <= start <= end <= len(data)
            removed = base64.b64decode(edit["removed"], validate=True)
            replacement = base64.b64decode(edit["replacement"], validate=True)
            assert data[start:end] == removed
            # Prefix and suffix are copied exactly, including BOMs and multibyte sequences.
            after = data[:start] + replacement + data[end:]
            after.decode("utf-8")
            assert data[:start].decode("utf-8") is not None and data[end:].decode("utf-8") is not None
        assert row["before_sha256"] == patch["before_sha256"] == digest(data)
        assert row["after_sha256"] == patch["after_sha256"] == digest(after)
        if expected is not None:
            wanted = expected[name]
            assert data == wanted[0] and after == wanted[3], name
            assert row["issues"] == [{"kind": kind, "line": line} for kind, line in wanted[2]], (name, row)
            assert row["manual"] == wanted[4]
        expected_remaining = row["issues"] if config["mode"] == "check" or row["manual"] else []
        assert row["remaining"] == expected_remaining
        if config["mode"] == "apply":
            names.add("files/" + name)
            assert (output / "files" / name).read_bytes() == after
        counts["violations"] += len(row["issues"])
        counts["remaining"] += len(row["remaining"])
        counts["changed_files"] += after != data
        counts["manual_files"] += row["manual"]
        for finding in row["issues"]:
            assert type(finding["line"]) is int and finding["line"] >= 1
            grouped.setdefault(finding["kind"], []).append({"file": name, "line": finding["line"]})
        replay.append({"name": name, "path": patch["path"], "style": entry["style"]})
        recheck.append({"name": name, "path": "files/" + name, "style": entry["style"]})
    assert report["summary"] == counts and report["groups"] == grouped
    assert json.loads((output / "replay.json").read_bytes()) == {
        "version": 1,
        "mode": "check",
        "output": "replayed",
        "policy": plan["policy"],
        "files": replay,
    }
    assert json.loads((output / "apply.json").read_bytes()) == {
        "version": 1,
        "mode": "apply",
        "output": "applied",
        "patches": "patches.json",
    }
    if config["mode"] == "apply":
        names.add("recheck.json")
        assert json.loads((output / "recheck.json").read_bytes()) == {
            "version": 1,
            "mode": "check",
            "output": "rechecked",
            "policy": plan["policy"],
            "files": recheck,
        }
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert set(manifest) == names and set(snapshot(output)) == names | {"manifest.json"}
    for name, info in manifest.items():
        raw = (output / name).read_bytes()
        assert info == {"bytes": len(raw), "sha256": digest(raw)}
    text = (output / "report.txt").read_text().splitlines()
    assert json.loads(text[0].removeprefix("Source header check: ")) == counts
    assert text[1:] == [
        f'{row["name"]}:{item["line"]}: {item["kind"]}' for row in report["files"] for item in row["issues"]
    ]
    return report


def run(app: Application, root: Path, config: dict, expected: dict | None = None, timeout: int = 30) -> dict:
    result = app.run(root, {}, timeout=timeout)
    assert result.returncode in [0, 1] and not result.stderr, (root, result)
    report = inspect_bundle(root, config, expected)
    assert json.loads(result.stdout) == report["summary"]
    assert result.returncode == (1 if report["summary"]["remaining"] else 0)
    return report


def consume(app: Application, bundle: Path, request: str, expected: dict | None = None) -> tuple[dict, Path]:
    config = json.loads((bundle / request).read_bytes())
    save(bundle / "headers-job.json", config)
    report = run(app, bundle, config, expected)
    return report, bundle / config["output"]


def semantics(app: Application, root: Path) -> dict:
    work = root / "hand"
    config = fixture(work)
    original = {entry["path"]: (work / entry["path"]).read_bytes() for entry in config["files"]}
    report = run(app, work, config, cases())
    applied, corrected = consume(app, work / "inspection", "apply.json", cases())
    assert applied["summary"]["remaining"] == 1 and applied["summary"]["manual_files"] == 1
    clean_expected = {name: (row[3], row[1], row[2] if row[4] else [], row[3], row[4]) for name, row in cases().items()}
    checked, _ = consume(app, corrected, "recheck.json", clean_expected)
    assert checked["summary"]["changed_files"] == 0
    for name, raw in original.items():
        assert (work / name).read_bytes() == raw
    work = root / "empty"
    assert run(app, work, fixture(work, {}), {})["summary"]["files"] == 0
    generated = 0
    for year in [1900, 2000, 2026, 9999]:
        data = {}
        policy = dict(POLICY, year=year)
        for style in ["hash", "slash"]:
            for newline in [b"\n", b"\r\n"]:
                for bom in [b"", b"\xef\xbb\xbf"]:
                    for has_header in [False, True]:
                        code = b'print("\xe4\xb8\x96\xe7\x95\x8c")' + newline + b"trailing bytes"
                        header = canonical(style, str(year), newline=newline)
                        raw = bom + (header if has_header else b"") + code
                        issues = [] if has_header else [("missing_copyright", 1), ("missing_license", 1)]
                        name = f"pkg/{len(data)}.txt"
                        data[name] = (raw, style, issues, bom + header + code, False)
        work = root / f"generated-{year}"
        run(app, work, fixture(work, data, policy), data)
        consume(app, work / "inspection", "apply.json", data)
        generated += len(data)
    return {
        "hand_labeled_files": len(cases()),
        "generated_byte_preservation_cases": generated,
        "exact_file_line_and_grouping": True,
        "manual_preamble_conflict": True,
        "rechecked_edits_are_idempotent": True,
        "input_files_unchanged": True,
        "hand_summary": report["summary"],
    }


def apply_fixture(root: Path) -> dict:
    data = canonical() + b"pass\n"
    fixture(root, {"valid.py": (data, "hash", [], data, False)})
    row = {
        "name": "valid.py",
        "path": "input-0.txt",
        "style": "hash",
        "before_sha256": digest(data),
        "after_sha256": digest(data),
        "edit": None,
    }
    save(root / "patches.json", {"version": 1, "policy": POLICY, "files": [row]})
    config = {"version": 1, "mode": "apply", "patches": "patches.json", "output": "inspection"}
    save(root / "headers-job.json", config)
    return config


def reject(app: Application, root: Path) -> None:
    result = app.run(root, {}, timeout=20)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert not (root / "inspection").exists()
    return  # noqa: PLR1711


def invalid(app: Application, root: Path) -> dict:
    changes = [
        ("version", True),
        ("version", 2),
        ("mode", "rewrite"),
        ("files", {}),
        ("files", [{}]),
        ("output", ""),
        ("output", "\0"),
        ("extra", 1),
    ]
    for number, (key, value) in enumerate(changes):
        work = root / f"config-{number}"
        config = fixture(work, {})
        config[key] = value
        save(work / "headers-job.json", config)
        reject(app, work)
    policies = [("year", value) for value in [True, 1.5, 1899, 10000]]
    for key in ["owners", "licenses"]:
        policies += [
            (key, value)
            for value in [
                [],
                ["same", "same"],
                [1],
                [" leading"],
                ["trailing "],
                ["bad\nlabel"],
                ["bad\0label"],
                ["a" * 129],
                [str(i) for i in range(9)],
                "label",
            ]
        ]
    policies += [("licenses", ["MIT OR Apache-2.0"]), ("licenses", ["a" * 65]), ("extra", 1)]
    for number, (key, value) in enumerate(policies):
        work = root / f"policy-{number}"
        fixture(work, {}, dict(POLICY, **{key: value}))
        reject(app, work)
    entries = [
        ("style", "block"),
        ("name", ""),
        ("name", "../escape"),
        ("name", "/absolute"),
        ("name", "a//b"),
        ("name", "a/./b"),
        ("name", "a\\b"),
        ("name", "a\nname"),
        ("name", "a" * 241),
        ("name", "/".join(["a"] * 9)),
        ("name", "é" * 121),
        ("path", "missing"),
        ("path", "../escape"),
        ("extra", 1),
    ]
    for number, (key, value) in enumerate(entries):
        work = root / f"entry-{number}"
        config = fixture(work, {"ok.py": (b"", "hash")})
        config["files"][0][key] = value
        save(work / "headers-job.json", config)
        reject(app, work)
    for kind in ["duplicate-name", "duplicate-path", "prefix", "too-many"]:
        work = root / kind
        config = fixture(work, {"a": (b"", "hash"), "b": (b"", "hash")})
        if kind == "duplicate-name":
            config["files"][1]["name"] = "a"
        elif kind == "duplicate-path":
            config["files"][1]["path"] = "input-0.txt"
        elif kind == "prefix":
            config["files"][1]["name"] = "a/child"
        else:
            config["files"] *= 17
        save(work / "headers-job.json", config)
        reject(app, work)
    bad_sources = [b"\xff", b"print('x')\0", b"a\rb", b"# coding: latin-1\n", b" " * 65537, b"\n" * 4097, b"x" * 65536]
    for number, data in enumerate(bad_sources):
        work = root / f"source-{number}"
        fixture(work, {"a.py": (data, "hash")})
        reject(app, work)
    bad_patches = [
        ("before_sha256", "0" * 64),
        ("after_sha256", "0" * 64),
        ("before_sha256", True),
        ("edit", {}),
        ("edit", {"start": 0, "end": 0, "removed": "", "replacement": "ZXZpbA=="}),
        ("extra", 1),
    ]
    for number, (key, value) in enumerate(bad_patches):
        work = root / f"patch-{number}"
        apply_fixture(work)
        patch = json.loads((work / "patches.json").read_bytes())
        patch["files"][0][key] = value
        save(work / "patches.json", patch)
        reject(app, work)
    work = root / "stale"
    apply_fixture(work)
    (work / "input-0.txt").write_bytes(canonical() + b"different code\n")
    reject(app, work)
    malformed = [b"{", b"\xff", b'{"version":1,"version":1}', b"null", b"[]"]
    for name, limit in [("headers-job.json", 65536), ("patches.json", 4194304)]:
        for number, raw in enumerate([*malformed, b" " * (limit + 1)]):
            work = root / f"raw-{name}-{number}"
            apply_fixture(work)
            (work / name).write_bytes(raw)
            reject(app, work)
    return {
        "configurations": len(changes),
        "policies": len(policies),
        "entries": len(entries),
        "duplicate_prefix_or_count_cases": 4,
        "invalid_sources": len(bad_sources),
        "tampered_or_stale_patches": len(bad_patches) + 1,
        "malformed_or_oversized_documents": 12,
    }


def limits(app: Application, root: Path) -> dict:
    owner = "O" * 128
    license_name = "L" * 64
    policy = {
        "year": 9999,
        "owners": [owner, *[f"owner-{i}" for i in range(7)]],
        "licenses": [license_name, *[f"License-{i}" for i in range(7)]],
    }
    header = canonical(years="9999", owner=owner, license_name=license_name)
    data = header + b"x" * (32768 - len(header))
    files = {f"pkg/file-{i}.py": (data, "hash", [], data, False) for i in range(32)}
    work = root / "maximum"
    config = fixture(work, files, policy)
    request = work / "headers-job.json"
    request.write_bytes(request.read_bytes().ljust(65536, b" "))
    run(app, work, config, files, 120)
    patch = work / "inspection/patches.json"
    patch.write_bytes(patch.read_bytes().ljust(4194304, b" "))
    applied, output = consume(app, work / "inspection", "apply.json", files)
    assert applied["summary"]["remaining"] == 0
    consume(app, output, "recheck.json", files)
    for label, data, name in [
        ("bytes", canonical() + b"x" * (65536 - len(canonical())), "a.py"),
        ("lines", canonical() + b"\n" * 4094, "a.py"),
        ("path", canonical(), "/".join(["p" * 29] * 7 + ["f" * 30])),
        ("unicode", canonical(), "世界/é😀.py"),
    ]:
        work = root / label
        files = {name: (data, "hash", [], data, False)}
        config = fixture(work, files)
        run(app, work, config, files)
        _, output = consume(app, work / "inspection", "apply.json", files)
        consume(app, output, "recheck.json", files)
    work = root / "total-overflow"
    fixture(work, {f"{i}.py": (canonical() + b"x" * (32769 - len(canonical())), "hash") for i in range(32)})
    reject(app, work)
    work = root / "corrected-total-overflow"
    fixture(work, {f"{i}.py": (b"x" * 32768, "hash") for i in range(32)})
    reject(app, work)
    return {
        "files": 32,
        "source_bytes": 65536,
        "total_source_bytes": 1048576,
        "lines": 4096,
        "configuration_bytes": 65536,
        "patch_document_bytes": 4194304,
        "logical_path_characters": 240,
        "logical_path_parts": 8,
        "owner_characters": 128,
        "license_characters": 64,
        "policy_choices": 8,
        "total_and_corrected_overflows": 2,
        "unicode_paths_and_export_rechecks": True,
    }


def paused(app: Application, root: Path, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"HEADERS_PAUSE": label, "HEADERS_RELEASE": str(root.parent / (root.name + "-release"))}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], 0.05)
        if ready:
            line = process.stdout.readline()
            if line.strip() == "PAUSED " + label:
                return process
            if not line:
                break
    process.kill()
    raise AssertionError(("pause failed", process.communicate()))


def publication(app: Application, root: Path) -> dict:
    raw = b"pass\n"
    files = {
        "nested/deep/a.py": (raw, "hash", [("missing_copyright", 1), ("missing_license", 1)], canonical() + raw, False)
    }
    for label in ["staged", "published"]:
        for mode in ["fault", "kill"]:
            work = root / (label + "-" + mode)
            config = fixture(work, files)
            if mode == "fault":
                result = app.run(work, {"HEADERS_FAULT": label})
                assert result.returncode == 2 and "injected failure" in result.stderr
                assert not list(work.glob(".headers-*"))
            else:
                process = paused(app, work, label)
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9
            if label == "published":
                inspect_bundle(work, config, files)
            else:
                assert not (work / "inspection").exists()
            if label == "staged" and mode == "fault":
                run(app, work, config, files)
    changes = ["headers-job.json", "patches.json", "input-0.txt", "removed", "replaced", "competitor"]
    for change in changes:
        work = root / change
        apply_fixture(work)
        process = paused(app, work, "staged")
        try:
            if change == "competitor":
                (work / "inspection").mkdir()
                (work / "inspection/sentinel").write_bytes(b"keep")
            elif change == "removed":
                (work / "input-0.txt").unlink()
            elif change == "replaced":
                (work / "input-0.txt").rename(work / "original")
                (work / "input-0.txt").symlink_to(work / "original")
            else:
                (work / change).write_bytes(b"changed")
            (work.parent / (work.name + "-release")).touch()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 2 and stderr and not stdout
            if change == "competitor":
                assert (work / "inspection/sentinel").read_bytes() == b"keep"
                assert len(list((work / "inspection").iterdir())) == 1
            else:
                assert not (work / "inspection").exists()
            assert not list(work.glob(".headers-*"))
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    return {
        "atomic_fault_or_kill_boundaries": 4,
        "input_changes_or_output_races": len(changes),
        "nested_staging_cleanup": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    entries = [
        (name, kind)
        for name in ["headers-job.json", "patches.json", "input-0.txt"]
        for kind in ["symlink", "hardlink", "fifo", "unreadable"]
    ]
    for number, (name, kind) in enumerate(entries):
        work = root / str(number)
        apply_fixture(work)
        target, sentinel = work / name, work / "sentinel"
        sentinel.write_bytes(b"keep")
        if kind == "unreadable":
            assert os.getuid() != 0
            target.chmod(0)
        else:
            target.unlink()
            if kind == "symlink":
                target.symlink_to(sentinel)
            elif kind == "hardlink":
                os.link(sentinel, target)
            else:
                os.mkfifo(target)
        try:
            reject(app, work)
            assert sentinel.read_bytes() == b"keep"
        finally:
            if kind == "unreadable":
                target.chmod(0o600)
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / kind
        fixture(work, {})
        target, sentinel = work / "inspection", work / "sentinel"
        sentinel.write_bytes(b"keep")
        if kind == "file":
            target.write_bytes(b"original")
        elif kind == "directory":
            target.mkdir()
        elif kind == "symlink":
            target.symlink_to(sentinel)
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {}, timeout=10)
            assert result.returncode == 2 and result.stderr and not result.stdout
            assert sentinel.read_bytes() == b"keep"
            if kind == "file":
                assert target.read_bytes() == b"original"
            elif kind == "directory":
                assert not list(target.iterdir())
            elif kind == "symlink":
                assert target.is_symlink()
            else:
                assert not target.exists()
        finally:
            work.chmod(0o700)
    return {"guarded_paths_and_permissions": len(entries) + 4}


def check(app: Application, directory: Path) -> dict:
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid": invalid(app, directory / "invalid"),
        "limits": limits(app, directory / "limits"),
        "publication": publication(app, directory / "publication"),
        "filesystem": filesystem(app, directory / "filesystem"),
        "independent_byte_and_finding_oracles": True,
    }
