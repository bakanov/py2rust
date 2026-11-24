"""Independent inode/content oracles, deliberate digest-bucket collisions and memory limits."""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import shutil
import stat
import subprocess
from collections import defaultdict
from pathlib import Path

from .common import Application


def stamp(path: Path) -> dict:
    info = path.lstat()
    return {
        "kind": "file",
        "size": info.st_size,
        "mode": stat.S_IMODE(info.st_mode),
        "device": info.st_dev,
        "inode": info.st_ino,
        "links": info.st_nlink,
        "mtime_ns": info.st_mtime_ns,
        "ctime_ns": info.st_ctime_ns,
    }


def configuration(work: Path, **changes: object) -> dict:
    raw = {"root": str(work / "tree"), **changes}
    (work / "duplicates.json").write_text(json.dumps(raw))
    return raw


def settings(work: Path, **changes: str) -> dict:
    return {
        "DUPLICATE_CONFIG": str(work / "duplicates.json"),
        "DUPLICATE_REPORT": str(work / "report.json"),
        "DUPLICATE_PLAN": str(work / "plan.json"),
        "DUPLICATE_PAUSE": "",
        "DUPLICATE_CONTINUE": "",
        **changes,
    }


def verify_envelope(work: Path, output: str, code: int) -> dict:
    report = json.loads((work / "report.json").read_text())
    identifier = report.pop("id")
    encoded = json.dumps(report, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert identifier == hashlib.sha256(encoded).hexdigest()
    report["id"] = identifier
    assert report["version"] == 1 and report["complete"] == (code == 0)
    assert json.loads(output) == {
        "id": identifier,
        "complete": report["complete"],
        "groups": len(report["groups"]),
        "reclaimable_logical_bytes": report["reclaimable_logical_bytes"],
    }
    plan = json.loads((work / "plan.json").read_text())
    assert plan == {
        "version": 1,
        "root": report["root"],
        "report_id": identifier,
        "ready": code == 0,
        "requires_revalidation": True,
        "actions": report["actions"],
    }
    if code != 0:
        assert report["actions"] == []
        assert report["errors"] or report["omissions"]
    return report


def invoke(app: Application, work: Path, code: int = 0) -> dict:
    result = app.run(work, settings(work), timeout=40)
    assert result.returncode == code, result.stdout + result.stderr
    return verify_envelope(work, result.stdout, code)


def fixture(work: Path) -> dict:
    root = work / "tree"
    root.mkdir(parents=True)
    binary = b"\x00alpha\xff\r\n"
    values = {
        "a.bin": binary,
        "nested/copy.bin": binary,
        "z-extra.bin": binary,
        "世界😀.bin": binary,
        "other.bin": b"\x00bravo\xff\r\n",
        "empty-one": b"",
        "empty-two": b"",
        "unique.txt": b"unique-size-contents",
        "ignored.skip": binary,
        ".git/hidden": binary,
        "notes-crlf": b"hello\r\n",
        "notes-lf": b"hello\n",
    }
    for name, content in values.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (root / "alias-a.bin").hardlink_to(root / "a.bin")
    (root / "empty-hard").hardlink_to(root / "empty-one")
    (work / "external-hard-link").hardlink_to(root / "z-extra.bin")
    (root / "file-link").symlink_to("a.bin")
    (root / "directory-link").symlink_to("nested", target_is_directory=True)
    (root / "broken").symlink_to("missing")
    (root / "cycle").symlink_to(".", target_is_directory=True)
    os.symlink(b"invalid\xff", os.fsencode(root / "raw-target"))
    os.mkfifo(root / "pipe")
    with (root / "too-big").open("wb") as stream:
        stream.truncate(1048576)
    return configuration(work, exclude=[r"(^|/)\.git(/|$)", r"\.skip$"], max_size=1024)


def oracle(root: Path, policy: dict) -> tuple[list[dict], list[dict], list[dict], int, int]:
    by_inode = {}
    by_size = defaultdict(list)
    contents = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            excluded = any(re.search(pattern, relative, re.ASCII) for pattern in policy.get("exclude", []))
            info = path.lstat()
            if excluded and name in directories:
                directories.remove(name)
            if excluded or not stat.S_ISREG(info.st_mode):
                continue
            if not policy.get("min_size", 0) <= info.st_size <= policy.get("max_size", 1073741824):
                continue
            key = (info.st_dev, info.st_ino)
            if key not in by_inode:
                by_inode[key] = {"paths": [], "stamp": stamp(path)}
                contents[key] = path.read_bytes()
            by_inode[key]["paths"].append(relative)
    ordered = sorted(by_inode, key=lambda key: min(by_inode[key]["paths"]))
    for key in ordered:
        by_inode[key]["paths"].sort()
        by_size[len(contents[key])].append(key)
    hashed = sum(len(keys) for keys in by_size.values() if len(keys) > 1)
    reserved = sum(size * len(keys) for size, keys in by_size.items() if len(keys) > 1)
    identical = defaultdict(list)
    for key in ordered:
        identical[contents[key]].append(key)
    groups = []
    actions = []
    for content, keys in identical.items():
        if len(keys) < 2:
            continue
        copies = [{**by_inode[key], "sha256": hashlib.sha256(content).hexdigest()} for key in keys]
        keeper = copies[0]
        reclaimable = sum(len(content) for row in copies[1:] if len(row["paths"]) == row["stamp"]["links"])
        groups.append(
            {
                "keep": keeper["paths"][0],
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "copies": copies,
                "redundant_paths": [name for row in copies[1:] for name in row["paths"]],
                "reclaimable_logical_bytes": reclaimable,
            }
        )
        actions.extend(
            {
                "keep": keeper["paths"][0],
                "remove": row["paths"],
                "keep_stamp": keeper["stamp"],
                "remove_stamp": row["stamp"],
                "sha256": keeper["sha256"],
            }
            for row in copies[1:]
        )
    aliases = [
        {"paths": by_inode[key]["paths"], "links": by_inode[key]["stamp"]["links"], "size": len(contents[key])}
        for key in ordered
        if len(by_inode[key]["paths"]) > 1
    ]
    return sorted(groups, key=lambda row: row["keep"]), aliases, actions, hashed, reserved


def check_groups(report: dict, root: Path, raw: dict) -> None:
    groups, aliases, actions, hashed, reserved = oracle(root, raw)
    assert report["groups"] == groups
    assert report["hard_links"] == aliases
    assert sorted(report["actions"], key=lambda row: row["remove"]) == sorted(actions, key=lambda row: row["remove"])
    assert report["hashed_files"] == hashed and report["hash_bytes_reserved"] == reserved
    assert report["reclaimable_logical_bytes"] == sum(row["reclaimable_logical_bytes"] for row in groups)
    for row in report["groups"]:
        originals = [(root / name).read_bytes() for copy in row["copies"] for name in copy["paths"]]
        assert len(set(originals)) == 1
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_basic(app: Application, work: Path) -> None:
    raw = fixture(work)
    root = work / "tree"
    before = {path: stamp(path) for path in root.rglob("*") if path.is_file() and not path.is_symlink()}
    result = invoke(app, work)
    check_groups(result, root, raw)
    assert result["excluded"] == [".git", "ignored.skip"]
    assert {row["reason"] for row in result["ignored"]} == {"symlink", "fifo", "size_policy"}
    assert result["reclaimable_logical_bytes"] == 2 * len(b"\x00alpha\xff\r\n")
    assert result["comparisons"] == sum(len(row["copies"]) - 1 for row in result["groups"])
    report_bytes, plan_bytes = (work / "report.json").read_bytes(), (work / "plan.json").read_bytes()
    assert invoke(app, work) == result
    assert (work / "report.json").read_bytes() == report_bytes and (work / "plan.json").read_bytes() == plan_bytes
    assert before == {path: stamp(path) for path in before}
    # Existing hard links alone are not independent copies and need no content read.
    case = work / "aliases-only"
    tree = case / "tree"
    tree.mkdir(parents=True)
    (tree / "a").write_bytes(b"same inode")
    (tree / "b").hardlink_to(tree / "a")
    configuration(case, max_hash_bytes=0, max_compare_bytes=0, max_comparisons=0)
    alias_report = invoke(app, case)
    assert alias_report["unique_files"] == 1 and alias_report["groups"] == [] and alias_report["hashed_files"] == 0
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_collisions(app: Application, work: Path) -> None:
    root = work / "tree"
    root.mkdir(parents=True)
    prefixes = defaultdict(list)
    values = []
    for number in range(256):
        data = number.to_bytes(8, "little")
        bucket = prefixes[hashlib.sha256(data).hexdigest()[0]]
        bucket.append(data)
        if len(bucket) == 3:
            values = bucket
            break
    assert len(values) == 3 and len(set(values)) == 3
    for name, content in zip(["a0", "a1", "b0", "b1", "c0"], [values[0], values[0], values[1], values[1], values[2]]):
        (root / name).write_bytes(content)
    raw = configuration(work, digest_chars=1, chunk_bytes=3)
    collided = invoke(app, work)
    check_groups(collided, root, raw)
    assert len(collided["groups"]) == 2 and collided["comparisons"] == 6
    assert collided["compare_bytes_reserved"] == 96
    raw = configuration(work, digest_chars=64, chunk_bytes=3)
    complete_digest = invoke(app, work)
    check_groups(complete_digest, root, raw)
    assert complete_digest["groups"] == collided["groups"] and complete_digest["comparisons"] == 2
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def simple_tree(work: Path) -> None:
    root = work / "tree"
    root.mkdir(parents=True)
    (root / "a").write_bytes(b"duplicate")
    (root / "b").write_bytes(b"duplicate")
    (root / "nested").mkdir()
    (root / "nested/c").write_bytes(b"duplicate")
    configuration(work)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_incomplete(app: Application, work: Path) -> int:
    cases = [
        ("depth", {"max_depth": 1}, "depth_limit"),
        ("entries", {"max_entries": 2}, "entry_limit"),
        ("children", {"max_children": 2}, "list"),
        ("hash", {"max_hash_bytes": 9}, "hash_budget"),
        ("compare-bytes", {"max_compare_bytes": 17}, "comparison_budget"),
        ("compare-count", {"max_comparisons": 1}, "comparison_budget"),
    ]
    for name, changes, reason in cases:
        case = work / name
        simple_tree(case)
        configuration(case, **changes)
        report = invoke(app, case, 2)
        assert reason in [row.get("reason", row.get("operation")) for row in report["errors"] + report["omissions"]]
        assert report["actions"] == []
    assert os.geteuid() != 0, "permission fixtures require an unprivileged user"
    for name in ["unreadable-file", "unreadable-directory", "invalid-name"]:
        case = work / name
        simple_tree(case)
        root = case / "tree"
        blocked = root / ("a" if name == "unreadable-file" else "nested")
        mode = stat.S_IMODE(blocked.stat().st_mode)
        if name == "invalid-name":
            fd = os.open(os.fsencode(root) + b"/bad\xff", os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd)
        else:
            blocked.chmod(0)
        try:
            report = invoke(app, case, 2)
            operation = "hash" if name == "unreadable-file" else "list"
            assert operation in [row["operation"] for row in report["errors"]]
        finally:
            blocked.chmod(mode)
    return len(cases) + 3


def check_boundaries(app: Application, work: Path) -> None:
    case = work / "exact-budgets"
    simple_tree(case)
    configuration(case, max_hash_bytes=27, max_compare_bytes=36, max_comparisons=2, chunk_bytes=1)
    complete = invoke(app, case)
    assert complete["hash_bytes_reserved"] == 27 and complete["compare_bytes_reserved"] == 36
    assert complete["comparisons"] == 2 and len(complete["actions"]) == 2
    configuration(case, max_hash_bytes=0)
    partial = invoke(app, case, 2)
    assert partial["id"] != complete["id"] and partial["groups"] == []
    assert json.loads((case / "plan.json").read_text())["actions"] == []
    configuration(case, max_comparisons=1)
    assert invoke(app, case, 2)["groups"] == []
    case = work / "empty-tree"
    (case / "tree").mkdir(parents=True)
    configuration(case, max_hash_bytes=0, max_compare_bytes=0, max_comparisons=0)
    empty = invoke(app, case)
    assert empty["groups"] == [] and empty["unique_files"] == 0 and empty["visited_entries"] == 1
    (case / "tree/first").touch()
    (case / "tree/second").touch()
    configuration(case, max_hash_bytes=0, max_compare_bytes=0, max_comparisons=1)
    zero = invoke(app, case)
    assert zero["hash_bytes_reserved"] == zero["compare_bytes_reserved"] == 0
    assert zero["comparisons"] == 1 and len(zero["groups"]) == 1 and zero["reclaimable_logical_bytes"] == 0
    case = work / "unique-unreadable"
    simple_tree(case)
    path = case / "tree/unique"
    path.write_bytes(b"not read: different size")
    mode = stat.S_IMODE(path.stat().st_mode)
    path.chmod(0)
    try:
        unique = invoke(app, case)
        assert unique["complete"] and unique["unique_files"] == 4 and unique["hashed_files"] == 3
    finally:
        path.chmod(mode)
    configuration(case, min_size=9, max_size=9)
    exact_size = invoke(app, case)
    assert exact_size["unique_files"] == 3 and len(exact_size["groups"]) == 1
    assert {row["reason"] for row in exact_size["ignored"]} == {"size_policy"}
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_changes(app: Application, work: Path) -> int:
    for phase, change in [("scanned", "replace"), ("hashed", "contents"), ("compared", "directory")]:
        case = work / phase
        simple_tree(case)
        resume = case / "continue"
        process = subprocess.Popen(
            app.command,
            cwd=case,
            env=app.environment(settings(case, DUPLICATE_PAUSE=phase, DUPLICATE_CONTINUE=str(resume))),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                assert selector.select(timeout=10), "scan did not reach its pause"
                line = process.stdout.readline()
                assert line == "PAUSED " + phase + "\n", line
            path = case / "tree/a"
            if change == "replace":
                path.rename(case / "retained-original")
                path.symlink_to(case / "retained-original")
            elif change == "contents":
                info = path.stat()
                path.write_bytes(b"different")
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
            else:
                (case / "tree/nested/new-child").write_text("late entry")
            resume.touch()
            out, err = process.communicate(timeout=20)
            assert process.returncode == 2, out + err
            report = verify_envelope(case, out, 2)
            assert report["actions"] == []
            assert "revalidate" in [row["operation"] for row in report["errors"]]
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
    return 3


def check_bad_configuration(app: Application, work: Path) -> int:
    invalid = [
        {"unknown": True},
        {"max_depth": -1},
        {"max_depth": 257},
        {"max_entries": 0},
        {"max_children": 0},
        {"min_size": -1},
        {"max_size": -1},
        {"min_size": 5, "max_size": 4},
        {"max_size": 1099511627777},
        {"max_hash_bytes": -1},
        {"max_compare_bytes": -1},
        {"max_comparisons": -1},
        {"max_comparisons": 1000001},
        {"digest_chars": 0},
        {"digest_chars": 65},
        {"digest_chars": True},
        {"chunk_bytes": 0},
        {"chunk_bytes": 1048577},
        {"max_report_bytes": 1000},
        {"max_report_bytes": 134217729},
        {"exclude": ["["]},
        {"exclude": [1]},
        {"exclude": ["x"] * 129},
        {"exclude": ["x" * 1025]},
        {"root": "missing"},
        {"root": "/"},
        {"max_report_bytes": 1024},
    ]
    for index, changes in enumerate(invalid):
        case = work / str(index)
        simple_tree(case)
        configuration(case, **changes)
        (case / "report.json").write_bytes(b"old report")
        (case / "plan.json").write_bytes(b"old plan")
        result = app.run(case, settings(case))
        assert result.returncode != 0, result.stdout
        assert (case / "report.json").read_bytes() == b"old report" and (case / "plan.json").read_bytes() == b"old plan"
    return len(invalid)


def check_outputs(app: Application, work: Path) -> int:
    simple_tree(work)
    root = work / "tree"
    cases = [
        {"DUPLICATE_REPORT": str(root / "report.json")},
        {"DUPLICATE_PLAN": str(root / "plan.json")},
        {"DUPLICATE_REPORT": str(work / "duplicates.json")},
        {"DUPLICATE_PLAN": str(work / "duplicates.json")},
        {"DUPLICATE_PLAN": str(work / "report.json")},
    ]
    for extra in cases:
        result = app.run(work, settings(work, **extra))
        assert result.returncode != 0, result.stdout
        assert not (work / "report.json").exists() and not (work / "plan.json").exists()
    for kind in ["symlink", "hardlink", "directory", "fifo"]:
        path = work / "report.json"
        if kind == "symlink":
            path.symlink_to(work / "duplicates.json")
        elif kind == "hardlink":
            path.hardlink_to(work / "duplicates.json")
        elif kind == "directory":
            path.mkdir()
        else:
            os.mkfifo(path)
        result = app.run(work, settings(work))
        assert result.returncode != 0, result.stdout
        if kind == "directory":
            path.rmdir()
        else:
            path.unlink()
    result = app.run(work, settings(work, DUPLICATE_PLAN=""))
    assert result.returncode == 0 and not (work / "plan.json").exists(), result.stderr
    prior = invoke(app, work)
    protected = work / "blocked"
    protected.mkdir()
    old_plan = (work / "plan.json").read_bytes()
    (protected / "plan.json").write_bytes(old_plan)
    (root / "extra").write_bytes(b"duplicate")
    mode = stat.S_IMODE(protected.stat().st_mode)
    protected.chmod(0o555)
    try:
        result = app.run(work, settings(work, DUPLICATE_PLAN=str(protected / "plan.json")))
        assert result.returncode != 0
        current = json.loads((work / "report.json").read_text())
        assert current["id"] != prior["id"]
        assert (protected / "plan.json").read_bytes() == old_plan
        assert current["id"] != json.loads(old_plan)["report_id"]
    finally:
        protected.chmod(mode)
    return len(cases) + 6


def check_bounded_memory(app: Application, work: Path) -> dict:
    limiter = shutil.which("prlimit")
    assert limiter, "Linux prlimit is required for this streaming verification"
    root = work / "tree"
    root.mkdir(parents=True)
    length = 160 * 1024 * 1024 + 7
    for name in ["one", "two"]:
        with (root / name).open("wb") as stream:
            stream.seek(length - 1)
            stream.write(b"z")
    configuration(work, max_size=length, max_hash_bytes=length * 2, max_compare_bytes=length * 2)
    bounded = Application([limiter, "--as=134217728", "--", *app.command], app.engine)
    report = invoke(bounded, work)
    assert len(report["groups"]) == 1 and report["reclaimable_logical_bytes"] == length
    assert report["hash_bytes_reserved"] == report["compare_bytes_reserved"] == length * 2
    assert report["comparisons"] == 1 and report["hashed_files"] == 2
    expected = hashlib.sha256()
    with (root / "one").open("rb") as stream:
        while chunk := stream.read(65536):
            expected.update(chunk)
    assert report["groups"][0]["sha256"] == expected.hexdigest()
    return {"file_bytes": length, "address_space_bytes": 134217728, "copies": 2}


def check_scaling(app: Application, work: Path) -> int:
    root = work / "tree"
    root.mkdir(parents=True)
    count = 1000
    content = b"identical content"
    for index in range(count):
        (root / f"file-{index:04d}").write_bytes(content)
    configuration(work)
    limiter = shutil.which("prlimit")
    assert limiter
    bounded = Application([limiter, "--as=134217728", "--", *app.command], app.engine)
    report = invoke(bounded, work)
    assert len(report["groups"]) == 1 and report["unique_files"] == count
    group = report["groups"][0]
    assert group["keep"] == "file-0000" and len(group["copies"]) == count
    assert group["sha256"] == hashlib.sha256(content).hexdigest()
    assert group["reclaimable_logical_bytes"] == (count - 1) * len(content)
    assert report["comparisons"] == count - 1 and report["hashed_files"] == count
    assert report["hash_bytes_reserved"] == count * len(content)
    assert report["compare_bytes_reserved"] == (count - 1) * 2 * len(content)
    for index, row in enumerate(group["copies"]):
        name = f"file-{index:04d}"
        assert row["paths"] == [name] and row["stamp"] == stamp(root / name)
    assert len(report["actions"]) == count - 1
    assert [row["remove"] for row in report["actions"]] == [[f"file-{index:04d}"] for index in range(1, count)]
    return count


def check(app: Application, directory: Path) -> dict:
    check_basic(app, directory / "basic")
    check_collisions(app, directory / "collisions")
    incomplete = check_incomplete(app, directory / "incomplete")
    changes = check_changes(app, directory / "changes")
    check_boundaries(app, directory / "boundaries")
    invalid = check_bad_configuration(app, directory / "invalid")
    outputs = check_outputs(app, directory / "outputs")
    memory = check_bounded_memory(app, directory / "memory")
    scale = check_scaling(app, directory / "scale")
    return {
        "exact_groups": "independent inode/content oracle including external hard links, empty files and Unicode",
        "digest_collision": "three different contents in one prefix bucket; byte comparison keeps them distinct",
        "incomplete_scans": incomplete,
        "concurrent_changes": changes,
        "invalid_configurations": invalid,
        "output_checks": outputs,
        "boundaries": "exact byte/count limits, stale-plan invalidation, empty files/trees and unique-size pruning",
        "streaming": memory,
        "scaling_files_under_128_mib": scale,
    }
