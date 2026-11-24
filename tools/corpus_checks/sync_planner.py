"""Independent tree oracle and real execution of dry-run plans in disposable fixtures."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import os
import re
import selectors
import shutil
import stat
import subprocess
from pathlib import Path

from .common import Application


def signature(path: Path) -> dict:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return {"kind": "symlink", "target": os.readlink(path)}
    if stat.S_ISDIR(info.st_mode):
        return {"kind": "directory", "mode": stat.S_IMODE(info.st_mode) & 0o777}
    assert stat.S_ISREG(info.st_mode)
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            hashed.update(chunk)
    return {
        "kind": "file",
        "mode": stat.S_IMODE(info.st_mode) & 0o777,
        "size": info.st_size,
        "sha256": hashed.hexdigest(),
    }


def inventory(root: Path, exclude: list[str] | None = None) -> dict:
    result = {}
    pending = [root]
    while pending:
        path = pending.pop()
        name = path.relative_to(root).as_posix()
        name = "" if name == "." else name
        if name and any(re.search(pattern, name, re.ASCII) for pattern in exclude or []):
            continue
        result[name] = signature(path)
        if result[name]["kind"] == "directory":
            pending.extend(path.iterdir())
    return result


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def setup(directory: Path) -> tuple[Path, Path, dict]:
    directory.mkdir(parents=True)
    source = directory / "source"
    destination = directory / "destination"
    source.mkdir(mode=0o755)
    destination.mkdir(mode=0o755)
    config = {
        "source": str(source),
        "destination": str(destination),
        "exclude": [],
        "max_entries": 10000,
        "max_bytes": 1073741824,
    }
    (directory / "sync.json").write_text(json.dumps(config))
    return source, destination, config


def invoke(app: Application, work: Path, mode: str = "plan", **extra: str) -> dict:
    result = app.run(work, dict(SYNC_MODE=mode, **extra), timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    envelope = json.loads(result.stdout)
    body = envelope["plan" if mode == "plan" else "baseline"]
    assert envelope["id"] == digest(body)
    assert json.loads((work / ("sync-" + mode + ".json")).read_text()) == envelope
    return body


def fail(app: Application, work: Path, mode: str = "plan", **extra: str) -> None:
    old = (work / "sync-plan.json").read_bytes() if (work / "sync-plan.json").is_file() else None
    result = app.run(work, dict(SYNC_MODE=mode, **extra), timeout=20)
    assert result.returncode != 0, result.stdout
    if old is not None:
        assert (work / "sync-plan.json").read_bytes() == old, "failure replaced an earlier valid plan"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def execute(source: Path, destination: Path, plan: dict) -> None:
    """The checker applies each reported operation using OS APIs, never application helpers."""
    assert plan["validated"] is True and plan["requires_revalidation"] is True
    for action in plan["operations"]:
        name = action["path"]
        target = destination / name
        current = signature(target) if target.exists() or target.is_symlink() else None
        assert current == action["before"], action
        for conflict in plan["conflicts"]:
            assert name != conflict["path"] and not name.startswith(conflict["path"] + "/")
        if action["op"] == "remove":
            if current["kind"] == "directory":
                target.rmdir()  # A bad order or an excluded child makes this fail.
            else:
                target.unlink()
        elif action["op"] == "mkdir":
            target.mkdir(mode=0o700)
        elif action["op"] == "copy":
            assert not target.exists() and not target.is_symlink()
            with (source / name).open("rb") as incoming, target.open("xb") as output:
                shutil.copyfileobj(incoming, output, 65536)
            target.chmod(action["after"]["mode"])
        elif action["op"] == "symlink":
            target.symlink_to(action["after"]["target"])
        else:
            assert action["op"] == "chmod" and current["kind"] == "directory"
            target.chmod(action["after"]["mode"])
        after = signature(target) if target.exists() or target.is_symlink() else None
        assert after == action["after"], action
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def state(root: Path, value: str) -> None:
    item = root / "item"
    if item.is_dir() and not item.is_symlink():
        shutil.rmtree(item)
    elif item.exists() or item.is_symlink():
        item.unlink()
    if value.startswith("file"):
        item.write_bytes(value.encode())
        item.chmod(0o640)
    elif value == "directory":
        item.mkdir(mode=0o755)
        (item / "child").write_bytes(b"child data")
    elif value == "symlink":
        item.symlink_to("../outside/missing")
    else:
        assert value == "missing"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def acceptance(app: Application, directory: Path) -> dict:
    source, destination, config = setup(directory / "matrix")
    work = source.parent
    matrix_count = 0
    kinds = ["missing", "file-A", "file-B", "directory", "symlink"]
    for old, desired, current in itertools.product(kinds, repeat=3):
        state(source, old)
        baseline = {
            "format": 1,
            "source": str(source),
            "destination": str(destination),
            "exclude": [],
            "entries": inventory(source),
        }
        (work / "sync-baseline.json").write_text(json.dumps({"id": digest(baseline), "baseline": baseline}))
        state(source, desired)
        state(destination, current)
        source_before = inventory(source)
        destination_before = inventory(destination)
        plan = invoke(app, work)
        assert bool(plan["conflicts"]) == (desired != current and current != old), (old, desired, current, plan)
        assert inventory(source) == source_before and inventory(destination) == destination_before
        execute(source, destination, plan)
        expected = source_before if current == old or desired == current else destination_before
        assert inventory(destination) == expected, (old, desired, current, plan)
        repeated = invoke(app, work)
        assert repeated["operations"] == [] and repeated["conflicts"] == plan["conflicts"]
        matrix_count += 1

    # No baseline: add missing source files but preserve every destination-only or differing entry.
    (work / "sync-baseline.json").unlink()
    state(source, "file-A")
    state(destination, "file-B")
    plan = invoke(app, work)
    assert plan["operations"] == [] and plan["conflicts"][0]["reason"] == "untracked_difference"
    fail(app, work, "baseline")
    state(destination, "missing")
    execute(source, destination, invoke(app, work))
    assert inventory(source) == inventory(destination)
    captured = invoke(app, work, "baseline")
    assert captured["entries"] == inventory(source)
    for mode, setting in [("plan", "SYNC_PLAN"), ("baseline", "SYNC_BASELINE")]:
        alias = work / "aliased-output"
        alias.hardlink_to(source / "item")
        before = (source / "item").stat()
        fail(app, work, mode, **{setting: str(alias)})
        after = (source / "item").stat()
        assert (before.st_ino, before.st_nlink, before.st_ctime_ns) == (after.st_ino, after.st_nlink, after.st_ctime_ns)
        assert alias.read_bytes() == (source / "item").read_bytes() == b"file-A"
        alias.unlink()
    state(source, "missing")
    plan = invoke(app, work)
    assert plan["conflicts"] == [] and [a["op"] for a in plan["operations"]] == ["remove"]

    # A real mixed tree covers subtree edits, exclusions, timestamps and ordered directory changes.
    source, destination, config = setup(directory / "mixed")
    work = source.parent
    for name in [
        "source-change",
        "destination-change",
        "both",
        "converged",
        "deleted-safe",
        "deleted-destination",
        "file-to-dir",
        "same-time",
    ]:
        (source / name).write_bytes(b"original")
    for name in ["dir-to-file", "dir-to-link", "delete-conflict", "protected", "mode-dir"]:
        (source / name).mkdir(mode=0o755)
        (source / name / "child").write_bytes(b"old child")
    (source / "link").symlink_to("before")
    (source / "protected/keep").mkdir()
    (source / "protected/keep/private").write_bytes(b"excluded data")
    (source / "empty").mkdir()
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=True)
    config["exclude"] = ["(^|/)keep($|/)"]
    (work / "sync.json").write_text(json.dumps(config))
    assert invoke(app, work, "baseline")["entries"] == inventory(source, config["exclude"])
    (source / "source-change").write_bytes(b"new source")
    (destination / "destination-change").write_bytes(b"new destination")
    (source / "both").write_bytes(b"source conflict")
    (destination / "both").write_bytes(b"destination conflict")
    for root in [source, destination]:
        (root / "converged").write_bytes(b"same new contents")
    (source / "deleted-safe").unlink()
    (destination / "deleted-destination").unlink()
    (destination / "delete-conflict/child").write_bytes(b"must preserve descendant")
    shutil.rmtree(source / "delete-conflict")
    shutil.rmtree(source / "protected")
    shutil.rmtree(source / "dir-to-file")
    (source / "dir-to-file").write_bytes(b"replacement file")
    shutil.rmtree(source / "dir-to-link")
    (source / "dir-to-link").symlink_to("../outside")
    (source / "file-to-dir").unlink()
    (source / "file-to-dir").mkdir()
    (source / "file-to-dir/世界😀").write_bytes(b"\x00\xffCRLF\r\n")
    (source / "link").unlink()
    (source / "link").symlink_to("after")
    (source / "mode-dir").chmod(0o500)
    (source / "mode-dir/child").chmod(0o400)
    before = (source / "same-time").stat()
    (source / "same-time").write_bytes(b"changed!")
    os.utime(source / "same-time", ns=(before.st_atime_ns, before.st_mtime_ns))
    source_before = inventory(source)
    destination_before = inventory(destination)
    first = invoke(app, work)
    report = (work / "sync-plan.json").read_bytes()
    assert invoke(app, work) == first and (work / "sync-plan.json").read_bytes() == report
    assert inventory(source) == source_before and inventory(destination) == destination_before
    conflicts = {row["path"]: row["reason"] for row in first["conflicts"]}
    assert conflicts == {
        "both": "both_changed",
        "delete-conflict": "destination_subtree_changed",
        "deleted-destination": "destination_changed",
        "destination-change": "destination_changed",
        "protected": "excluded_descendant",
    }, conflicts
    execute(source, destination, first)
    after = inventory(destination)
    expected = copy.deepcopy(source_before)
    for name in list(expected):
        if any(name == root or name.startswith(root + "/") for root in conflicts):
            del expected[name]
    for name, value in destination_before.items():
        if any(name == root or name.startswith(root + "/") for root in conflicts):
            expected[name] = value
    assert after == expected
    assert invoke(app, work)["operations"] == []
    assert (destination / "protected/keep/private").read_bytes() == b"excluded data"

    baseline_path = work / "sync-baseline.json"
    good_baseline = baseline_path.read_bytes()
    envelope = json.loads(good_baseline)
    malformed = []
    bad = copy.deepcopy(envelope)
    bad["id"] = "0" * 64
    malformed.append(bad)
    for field, value in [("source", "/different"), ("exclude", []), ("format", 2)]:
        bad = copy.deepcopy(envelope)
        bad["baseline"][field] = value
        bad["id"] = digest(bad["baseline"])
        malformed.append(bad)
    for name in ["../escape", "/absolute", "a//b", "unknown/child"]:
        bad = copy.deepcopy(envelope)
        bad["baseline"]["entries"][name] = {"kind": "file", "mode": 420, "size": 0, "sha256": "0" * 64}
        bad["id"] = digest(bad["baseline"])
        malformed.append(bad)
    for bad in malformed:
        baseline_path.write_text(json.dumps(bad))
        fail(app, work)
    baseline_path.write_bytes(good_baseline)
    failures = len(malformed)
    for key, values in {
        "max_entries": [0, 1, 10001, True],
        "max_bytes": [0, 1, True],
        "destination": [str(source), str(source / "empty")],
        "exclude": ["not-array", ["["]],
    }.items():
        for value in values:
            (work / "sync.json").write_text(json.dumps(dict(config, **{key: value})))
            fail(app, work)
            failures += 1
    (work / "sync.json").write_text(json.dumps(config))
    for value in [str(source / "plan"), str(destination / "plan"), str(work / "sync.json"), str(baseline_path)]:
        fail(app, work, SYNC_PLAN=value)
        failures += 1
    (work / "linked-plan").symlink_to(source / "source-change")
    fail(app, work, SYNC_PLAN=str(work / "linked-plan"))
    os.mkfifo(source / "pipe")
    fail(app, work)
    (source / "pipe").unlink()
    (source / "denied").mkdir(mode=0)
    fail(app, work)
    (source / "denied").chmod(0o700)
    (source / "denied").rmdir()

    # A changed tree cannot replace the last good report after the paused scan.
    signal = work / "continue"
    process = subprocess.Popen(
        app.command,
        cwd=work,
        env=app.environment({"SYNC_PAUSE": "scanned", "SYNC_CONTINUE": str(signal)}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    old_report = (work / "sync-plan.json").read_bytes()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(10), "planner did not reach pause"
            assert process.stdout.readline().strip() == "PAUSED scanned"
        (source / "source-change").write_bytes(b"changed during planning")
        signal.touch()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode != 0, stdout + stderr
        assert (work / "sync-plan.json").read_bytes() == old_report
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()

    # Large source/destination hashing is streamed; lookups scale to many actual paths.
    source, destination, config = setup(directory / "large")
    work = source.parent
    size = 160 * 1024 * 1024 + 31
    with (source / "large").open("wb") as stream:
        stream.write(b"header")
        stream.seek(size - 4)
        stream.write(b"tail")
    for index in range(1000):
        (source / f"file-{index:04}").write_bytes(str(index).encode())
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    planned = invoke(limited, work)
    assert len(planned["operations"]) == 1001 and planned["conflicts"] == []
    execute(source, destination, planned)
    assert inventory(source) == inventory(destination)
    assert invoke(limited, work)["operations"] == []
    return {
        "three_way_cases": matrix_count,
        "mixed_conflicts": conflicts,
        "invalid_requests": failures + 3,
        "idempotence": "repeated plans and independently executed plans",
        "changed_tree": "report preserved",
        "preserved": "conflicts, excluded descendants and both original trees during planning",
        "output_hardlink_guards": 2,
        "large_file_bytes": size,
        "scale_files": 1001,
        "address_space_bytes": 134217728,
    }


def check(app: Application, directory: Path) -> dict:
    try:
        return acceptance(app, directory)
    finally:
        for root, _directories, _files in os.walk(directory, followlinks=False):
            os.chmod(root, stat.S_IMODE(os.stat(root).st_mode) | 0o700)
