"""Independent minimal-edit, exact-byte, malformed-patch and atomic publication checks."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import shutil
import subprocess
from pathlib import Path

from .common import Application
from .patch_fixture import (
    canonical,
    digest,
    fixtures,
    grouped,
    identity,
    inspect_patch,
    lines,
    shortest,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def request(mode: str, output: str, base: str, other: str, context: int = 3) -> dict:
    result = {"version": 1, "mode": mode, "output": output, "base": base}
    result.update({"target": other, "context": context} if mode == "diff" else {"patch": other})
    return result


def fixture(root: Path, before: bytes = b"A\nB\nC\n", after: bytes = b"A\nnew\nC\n", context: int = 3) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "before.txt").write_bytes(before)
    (root / "after.txt").write_bytes(after)
    config = request("diff", "output", "before.txt", "after.txt", context)
    save(root / "patch-job.json", config)
    return config


def patch_for(before: bytes, after: bytes, context: int) -> dict:
    return {
        "version": 1,
        "format": "line-lcs",
        "context": context,
        "before": identity(before),
        "after": identity(after),
        "hunks": grouped(shortest(lines(before), lines(after)), context),
    }


def apply_fixture(
    root: Path, patch: dict | None = None, before: bytes = b"A\nB\nC\n", after: bytes = b"A\nnew\nC\n"
) -> dict:
    fixture(root, before, after)
    save(root / "patch.json", patch_for(before, after, 1) if patch is None else patch)
    config = request("apply", "output", "before.txt", "patch.json")
    save(root / "patch-job.json", config)
    return config


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def inspect(root: Path, config: dict, expected_after: bytes) -> dict:
    output = root / config["output"]
    before = (root / config["base"]).read_bytes()
    after = (root / config["target"]).read_bytes() if config["mode"] == "diff" else expected_after
    patch_bytes = (output / "patch.json").read_bytes()
    patch = json.loads(patch_bytes)
    context = config["context"] if config["mode"] == "diff" else patch["context"]
    statistics = inspect_patch(patch, before, after, context)
    report = {
        "version": 1,
        "mode": config["mode"],
        "changed": before != after,
        "before": identity(before),
        "after": identity(after),
        "patch_sha256": digest(patch_bytes),
        "statistics": statistics,
    }
    assert (output / "report.json").read_bytes() == canonical(report)
    review = ["Line diff: quoted UTF-8 tokens; offsets are zero-based"]
    for hunk in patch["hunks"]:
        review.append(f"@@ old {hunk['old_start']},{hunk['old_count']} new {hunk['new_start']},{hunk['new_count']} @@")
        review.extend(op["op"] + canonical(op["text"]).decode().rstrip("\n") for op in hunk["ops"])
    files = {
        "base.txt": before,
        "patch.json": patch_bytes,
        "report.json": canonical(report),
        "diff.txt": ("\n".join(review) + "\n").encode(),
    }
    if config["mode"] == "diff":
        assert patch_bytes == canonical(patch)
        files.update(
            {
                "target.txt": after,
                "apply.json": canonical(request("apply", "applied", "base.txt", "patch.json", context)),
                "replay.json": canonical(request("diff", "replayed", "base.txt", "target.txt", context)),
                "check-applied.json": canonical(
                    request("diff", "checked", "applied/result.txt", "target.txt", context)
                ),
            }
        )
    else:
        assert patch_bytes == (root / config["patch"]).read_bytes()
        files.update(
            {
                "result.txt": after,
                "replay.json": canonical(request("apply", "replayed", "base.txt", "patch.json", context)),
                "recheck.json": canonical(request("diff", "rechecked", "base.txt", "result.txt", context)),
            }
        )
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    assert snapshot(output) == files
    return report


def run(
    app: Application, root: Path, config: dict, after: bytes, selected: str = "patch-job.json", timeout: int = 20
) -> dict:
    result = app.run(root, {"PATCH_CONFIG": str(root / selected)}, timeout=timeout)
    before = (root / config["base"]).read_bytes()
    code = int(config["mode"] == "diff" and before != after)
    assert result.returncode == code and not result.stderr, (root, result)
    report = inspect(root, config, after)
    assert result.stdout == canonical(report["statistics"]).decode()
    return report


def consume(app: Application, root: Path, selected: str, after: bytes) -> tuple[dict, Path]:
    config = json.loads((root / selected).read_bytes())
    return run(app, root, config, after, selected), root / config["output"]


def reject(app: Application, root: Path, reason: str = "") -> None:
    result = app.run(root, {}, timeout=15)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert reason in result.stderr, (reason, result)
    assert not (root / "output").exists() and not list(root.glob(".patch-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    hand = fixtures()
    hashes = {}
    for name, (before, after) in hand.items():
        for context in [0, 1, 3, 16]:
            work = root / f"{name}-{context}"
            config = fixture(work, before, after, context)
            report = run(app, work, config, after)
            original = snapshot(work / "output")
            applied, applied_root = consume(app, work / "output", "apply.json", after)
            assert applied["statistics"] == report["statistics"]
            checked, _ = consume(app, work / "output", "check-applied.json", after)
            assert not checked["changed"] and checked["statistics"]["removed"] == checked["statistics"]["added"] == 0
            regenerated, regenerated_root = consume(app, applied_root, "recheck.json", after)
            assert (regenerated_root / "patch.json").read_bytes() == original["patch.json"]
            assert regenerated["statistics"] == report["statistics"]
            assert snapshot(work / "output") == original
            assert (work / "before.txt").read_bytes() == before and (work / "after.txt").read_bytes() == after
            if context == 3:
                replayed, replay_root = consume(app, work / "output", "replay.json", after)
                assert replayed == report and snapshot(replay_root) == original
                hashes[name] = digest(original["patch.json"])
    # Context windows merge when they touch; they remain separate beyond 2 * context unchanged tokens.
    for context in [0, 1, 3, 16]:
        for distance in [2 * context, 2 * context + 1]:
            before = ("first\n" + "keep\n" * distance + "last\n").encode()
            after = ("FIRST\n" + "keep\n" * distance + "LAST\n").encode()
            work = root / f"context-gap-{context}-{distance}"
            report = run(app, work, fixture(work, before, after, context), after)
            assert report["statistics"]["hunks"] == (1 if distance <= 2 * context else 2)
    return {
        "hand_pairs": len(hand),
        "contexts_per_pair": 4,
        "context_merge_boundaries": 8,
        "apply_and_zero_diff_check": True,
        "patch_regeneration_and_replay": True,
        "exact_original_inputs_preserved": True,
        "patch_sha256": hashes,
    }


def generated(app: Application, root: Path) -> dict:
    sequences = [()] + [tokens for count in range(1, 4) for tokens in itertools.product(["a\n", "b\n"], repeat=count)]
    count = 0
    for left, right in itertools.product(sequences, repeat=2):
        before, after = "".join(left).encode(), "".join(right).encode()
        work = root / str(count)
        run(app, work, fixture(work, before, after, count % 4), after)
        consume(app, work / "output", "apply.json", after)
        count += 1
    rng = random.Random(1000100)
    tokens = ["世界\n", "😀\r\n", "a\r", "\n", "\x00\n", "Á\n", "A\u0301\n"]
    for number in range(40):
        before = "".join(rng.choices(tokens, k=rng.randrange(7))).encode()
        after = "".join(rng.choices(tokens, k=rng.randrange(7))).encode()
        if number % 2:
            before += b"final"
        if number % 3:
            after += "尾".encode()
        work = root / f"unicode-{number}"
        run(app, work, fixture(work, before, after, rng.randrange(5)), after)
        consume(app, work / "output", "apply.json", after)
    return {
        "exhaustive_binary_sequence_pairs": count,
        "seeded_unicode_pairs": 40,
        "independent_shortest_path_and_prefix_lcs_oracles": True,
    }


def invalid(app: Application, root: Path) -> dict:
    original = patch_for(b"A\nB\nC\n", b"A\nnew\nC\n", 1)
    variants = []
    for key, value in [
        ("version", True),
        ("version", 2),
        ("format", "other"),
        ("context", True),
        ("context", -1),
        ("context", 17),
        ("hunks", {}),
        ("hunks", []),
        ("extra", 1),
    ]:
        patch = copy.deepcopy(original)
        patch[key] = value
        variants.append(patch)
    for side in ["before", "after"]:
        for key, value in [
            ("bytes", True),
            ("bytes", -1),
            ("bytes", 65537),
            ("lines", True),
            ("lines", 1025),
            ("sha256", "0" * 64),
            ("sha256", "A" * 64),
            ("ending", "other"),
            ("ending", "none"),
            ("extra", 1),
        ]:
            patch = copy.deepcopy(original)
            patch[side][key] = value
            variants.append(patch)
    for key, value in [
        ("old_start", -1),
        ("old_start", True),
        ("old_start", 99),
        ("old_count", 0),
        ("old_count", True),
        ("new_start", 1),
        ("new_start", True),
        ("new_count", 0),
        ("new_count", True),
        ("ops", []),
        ("ops", {}),
        ("extra", 1),
    ]:
        patch = copy.deepcopy(original)
        patch["hunks"][0][key] = value
        variants.append(patch)
    for operation in [
        {"op": "?", "text": "A\n"},
        {"op": " ", "text": "wrong\n"},
        {"op": " ", "text": ""},
        {"op": " ", "text": "two\nlines\n"},
        {"op": " ", "text": 1},
        {"op": " "},
        {"op": " ", "text": "A\n", "extra": 1},
    ]:
        patch = copy.deepcopy(original)
        patch["hunks"][0]["ops"][0] = operation
        variants.append(patch)
    patch = copy.deepcopy(original)
    patch["hunks"].append(copy.deepcopy(patch["hunks"][0]))
    variants.append(patch)
    for index, patch in enumerate(variants):
        work = root / f"patch-{index}"
        apply_fixture(work, patch)
        reject(app, work)
    # Correct result bytes are insufficient: alternate LCS ties and needless edits are noncanonical.
    before, after = b"A\nB\n", b"B\nA\n"
    patch = patch_for(before, after, 0)
    patch["hunks"] = grouped([("+", "B\n"), (" ", "A\n"), ("-", "B\n")], 0)
    work = root / "alternate-tie"
    apply_fixture(work, patch, before, after)
    reject(app, work, "noncanonical LCS")
    before, after = b"unchanged\n", b"unchanged\n"
    patch = patch_for(before, after, 0)
    patch["hunks"] = grouped([("-", "unchanged\n"), ("+", "unchanged\n")], 0)
    work = root / "nonminimal"
    apply_fixture(work, patch, before, after)
    reject(app, work, "noncanonical LCS")
    before, after = b"a\nb\nc\nd\n", b"a\nB\nc\nd\n"
    patch = patch_for(before, after, 0)
    patch["context"] = 1
    work = root / "missing-context"
    apply_fixture(work, patch, before, after)
    reject(app, work, "noncanonical LCS")
    before, after = b"", b"ab"
    patch = patch_for(before, after, 0)
    patch["hunks"] = [
        {
            "old_start": 0,
            "old_count": 0,
            "new_start": 0,
            "new_count": 2,
            "ops": [{"op": "+", "text": "a"}, {"op": "+", "text": "b"}],
        }
    ]
    work = root / "unterminated-middle"
    apply_fixture(work, patch, before, after)
    reject(app, work, "noncanonical line boundaries")
    before, after = b"a\nkeep\nb\n", b"A\nkeep\nB\n"
    patch = patch_for(before, after, 0)
    patch["hunks"].reverse()
    work = root / "unordered"
    apply_fixture(work, patch, before, after)
    reject(app, work)
    for name, changed_base in [("content", b"A\nwrong\nC\n"), ("newline", b"A\nB\nC"), ("size", b"")]:
        work = root / ("stale-" + name)
        apply_fixture(work, original, changed_base)
        reject(app, work, "base identity mismatch")
    requests = [
        ("version", True),
        ("version", 2),
        ("mode", "edit"),
        ("context", -1),
        ("context", 17),
        ("context", True),
        ("base", ""),
        ("target", "\0"),
        ("output", ""),
        ("extra", 1),
    ]
    for index, (key, value) in enumerate(requests):
        work = root / f"request-{index}"
        config = fixture(work)
        config[key] = value
        save(work / "patch-job.json", config)
        reject(app, work)
    documents = [b"{", b'{"version":1,"version":1}', b"\xff", b'"\\ud800"', b'{"v":NaN}', b'{"v":9223372036854775808}']
    for index, (name, raw) in enumerate(itertools.product(["patch-job.json", "patch.json"], documents)):
        work = root / f"encoding-{index}"
        apply_fixture(work)
        (work / name).write_bytes(raw)
        reject(app, work)
    for side in ["before.txt", "after.txt"]:
        work = root / ("invalid-utf8-" + side)
        fixture(work)
        (work / side).write_bytes(b"\xff")
        reject(app, work)
    return {
        "malformed_patch_variants": len(variants),
        "noncanonical_patch_cases": 5,
        "stale_bases": 3,
        "invalid_requests": len(requests),
        "invalid_json_encodings": 12,
        "invalid_utf8_texts": 2,
    }


def limits(app: Application, root: Path) -> dict:
    limiter = shutil.which("prlimit")
    assert limiter is not None
    bounded = Application([limiter, "--as=201326592", "--", *app.command], app.engine)
    before = "".join("line-" + str(i) + "\n" for i in range(1024)).encode()
    after = "".join("replacement-" + str(i) + "\r\n" for i in range(1024)).encode()
    work = root / "maximum-table"
    report = run(bounded, work, fixture(work, before, after, 16), after, timeout=45)
    assert report["statistics"] == {"removed": 1024, "added": 1024, "common": 0, "hunks": 1, "cells": 1050625}
    consume(bounded, work / "output", "apply.json", after)
    before, after = b"\0" * 65536, b"\1" * 65536
    work = root / "maximum-bytes-and-escaping"
    run(app, work, fixture(work, before, after, 16), after)
    consume(app, work / "output", "apply.json", after)
    patch_length = (work / "output/patch.json").stat().st_size
    assert 786432 < patch_length < 1048576
    for side, raw in itertools.product(["before.txt", "after.txt"], [b"x" * 65537, b"\n" * 1025]):
        work = root / f"over-{side}-{len(raw)}"
        fixture(work)
        (work / side).write_bytes(raw)
        reject(app, work)
    work = root / "exact-request-and-patch-bytes"
    config = apply_fixture(work)
    for name, limit in [("patch-job.json", 65536), ("patch.json", 1048576)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(limit, b" "))
    run(app, work, config, b"A\nnew\nC\n")
    for name, limit in [("patch-job.json", 65536), ("patch.json", 1048576)]:
        work = root / ("over-" + name)
        apply_fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(limit + 1, b" "))
        reject(app, work)
    # Many isolated changes exercise non-overlapping zero-context hunk positions.
    before = "".join("x\nkeep\n" for _ in range(512)).encode()
    after = "".join("y\nkeep\n" for _ in range(512)).encode()
    work = root / "many-hunks"
    report = run(app, work, fixture(work, before, after, 0), after, timeout=45)
    assert report["statistics"]["hunks"] == 512
    consume(app, work / "output", "apply.json", after)
    return {
        "text_bytes": 65536,
        "lines_per_input": 1024,
        "alignment_cells": 1050625,
        "operations": 2048,
        "context_lines": 16,
        "isolated_hunks": 512,
        "request_bytes": 65536,
        "patch_bytes": 1048576,
        "memory_limit_bytes": 201326592,
        "escaped_patch_bytes": patch_length,
        "over_boundaries": 6,
    }


def publication(app: Application, root: Path) -> dict:
    after = b"A\nnew\nC\n"
    for mode in ["diff", "apply"]:
        for stage in ["staged", "published"]:
            work = root / (mode + "-" + stage)
            config = fixture(work) if mode == "diff" else apply_fixture(work)
            result = app.run(work, {"PATCH_FAULT": stage})
            assert result.returncode == 2 and result.stderr and not result.stdout
            assert not list(work.glob(".patch-*"))
            assert (work / "output").exists() == (stage == "published")
            if stage == "published":
                inspect(work, config, after)
    for mutation in ["request", "base", "target", "patch", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = apply_fixture(work) if mutation == "patch" else fixture(work)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"PATCH_PAUSE": stage, "PATCH_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 5)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            if mutation.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert (work / "output").exists() == (stage == "published")
                if stage == "published":
                    inspect(work, config, after)
                else:
                    assert len(list(work.glob(".patch-*"))) == 1
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = {
                        "request": "patch-job.json",
                        "base": "before.txt",
                        "target": "after.txt",
                        "patch": "patch.json",
                    }[mutation]
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=5)
                assert process.returncode == 2 and stderr and not stdout
                assert not list(work.glob(".patch-*"))
                if mutation == "competitor":
                    assert (work / "output/keep").read_text() == "original"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return {
        "caught_faults": 4,
        "input_and_output_races": 5,
        "hard_kills": 2,
        "complete_or_absent_final_directory": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["patch-job.json", "before.txt", "after.txt", "patch.json"],
        ["symlink", "hardlink", "fifo", "directory", "unreadable"],
    ):
        work = root / str(count)
        if name == "patch.json":
            apply_fixture(work)
        else:
            fixture(work)
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work)
        target = work / "output"
        if kind == "file":
            target.write_text("keep")
        elif kind == "directory":
            target.mkdir()
        elif kind == "symlink":
            target.symlink_to(work / "before.txt")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr and not result.stdout
            if kind == "file":
                assert target.read_text() == "keep"
            elif kind == "directory":
                assert not list(target.iterdir())
            elif kind == "symlink":
                assert target.is_symlink()
            else:
                assert not target.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " text patch " + name + ": passed", flush=True)
    return observations
