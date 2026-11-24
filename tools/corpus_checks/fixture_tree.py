"""Independent fixture bytes, ownership receipts and interrupted cleanup checks."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import selectors
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application


def checksum(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def identity(path: Path) -> dict:
    info = path.lstat()
    assert stat.S_ISDIR(info.st_mode)
    return {"device": info.st_dev, "inode": info.st_ino}


def file_stamp(path: Path) -> dict:
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode)
    with path.open("rb") as stream:
        hashed = hashlib.file_digest(stream, "sha256").hexdigest()
    return {
        "kind": "file",
        "device": info.st_dev,
        "inode": info.st_ino,
        "size": info.st_size,
        "mode": stat.S_IMODE(info.st_mode),
        "links": info.st_nlink,
        "mtime_ns": info.st_mtime_ns,
        "sha256": hashed,
    }


def snapshot(root: Path) -> dict:
    if not os.path.lexists(root):
        return {}
    found = {}
    pending = [root]
    while pending:
        path = pending.pop()
        name = str(path.relative_to(root))
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            found[name] = ("symlink", os.readlink(path), info.st_ino)
        elif stat.S_ISDIR(info.st_mode):
            found[name] = ("directory", info.st_ino, stat.S_IMODE(info.st_mode))
            pending.extend(path.iterdir())
        elif stat.S_ISREG(info.st_mode):
            found[name] = file_stamp(path)
        else:
            found[name] = ("special", info.st_mode, info.st_ino)
    return found


@dataclass
class Fixture:
    directory: Path
    root: Path
    manifest: dict

    @property
    def source(self) -> Path:
        return self.directory / "fixtures.json"

    @property
    def receipt(self) -> Path:
        return self.directory / "receipt.json"

    def save(self) -> None:
        self.source.write_text(json.dumps(self.manifest, ensure_ascii=False))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def settings(self, mode: str, **extra: str) -> dict[str, str]:
        settings = {"FIXTURE_MANIFEST": str(self.source), "FIXTURE_RECEIPT": str(self.receipt), "FIXTURE_MODE": mode}
        settings.update(extra)
        return settings


def fixture(directory: Path, name: str, existing: bool = False, simple: bool = False) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    root = work / "tree"
    if existing:
        (root / "shared").mkdir(parents=True)
        (root / "keep.txt").write_bytes(b"pre-existing root file")
        (root / "shared/old.bin").write_bytes(b"untouched\0\xff")
        (root / "unrelated").mkdir()
        (root / "unrelated/link").symlink_to("../keep.txt")
    entries = [
        {"path": "shared/new.txt", "kind": "text", "data": "Hello, 世界 😀!\r\n\nNUL:\u0000\n"},
        {"path": "data/bytes.bin", "kind": "base64", "data": base64.b64encode(bytes(range(256)) * 257).decode()},
        {"path": "empty/nested", "kind": "directory"},
        {"path": "shared", "kind": "directory"},
        {"path": "data/zero.bin", "kind": "base64", "data": ""},
        {"path": "é.txt", "kind": "text", "data": "composed"},
        {"path": "é.txt", "kind": "text", "data": "decomposed"},
        {"path": ".hidden/with space.txt", "kind": "text", "data": "literal ${HOME}"},
        {"path": 'quotes"and\nnewline.txt', "kind": "text", "data": ""},
    ]
    if simple:
        entries = [
            {"path": "a.txt", "kind": "text", "data": "first"},
            {"path": "folder/b.bin", "kind": "base64", "data": "AAECA/7/"},
        ]
    result = Fixture(work, root, {"root": str(root), "entries": entries, "max_entries": 1000, "max_bytes": 4194304})
    result.save()
    return result


def expected(fix: Fixture) -> tuple[set[str], dict[str, bytes]]:
    directories, files = {""}, {}
    for entry in fix.manifest["entries"]:
        name = entry["path"]
        if entry["kind"] == "directory":
            directories.add(name)
        else:
            files[name] = (
                entry["data"].encode() if entry["kind"] == "text" else base64.b64decode(entry["data"], validate=True)
            )
        for parent in Path(name).parents:
            if str(parent) != ".":
                directories.add(str(parent))
    return directories, files


def invoke(app: Application, fix: Fixture, mode: str, timeout: int = 30, **extra: str) -> dict:
    result = app.run(fix.directory, fix.settings(mode, **extra), timeout=timeout)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def receipt(fix: Fixture) -> dict:
    envelope = json.loads(fix.receipt.read_bytes())
    assert envelope["checksum"] == checksum(envelope["receipt"])
    return envelope["receipt"]


def construct(app: Application, fix: Fixture, timeout: int = 30) -> dict:
    before = snapshot(fix.root)
    directories, files = expected(fix)
    manifest_bytes = fix.source.read_bytes()
    plan = invoke(app, fix, "preview", timeout=timeout)
    assert not fix.receipt.exists() and snapshot(fix.root) == before
    assert plan["version"] == 1 and plan["root"] == str(fix.root) and plan["phase"] == "building" and plan["step"] == 0
    assert plan["parent"] == identity(fix.root.parent)
    assert plan["bytes"] == sum(map(len, files.values()))
    assert set(plan["entries"]) == directories | files.keys()
    for name, entry in plan["entries"].items():
        path = fix.root / name
        if name in files:
            assert entry == {
                "kind": "file",
                "owned": True,
                "stamp": None,
                "size": len(files[name]),
                "sha256": hashlib.sha256(files[name]).hexdigest(),
            }
        else:
            assert entry == {
                "kind": "directory",
                "owned": not path.exists(),
                "stamp": identity(path) if path.exists() else None,
                "size": 0,
                "sha256": "",
            }
    report = invoke(app, fix, "create", timeout=timeout)
    saved = receipt(fix)
    assert saved["phase"] == "ready" and saved["step"] == 0
    assert report == {
        "phase": "ready",
        "root": str(fix.root),
        "created": sum(row["owned"] for row in saved["entries"].values()),
        "bytes": sum(map(len, files.values())),
        "cleanup_step": 0,
    }
    for name, entry in saved["entries"].items():
        assert entry["owned"] == plan["entries"][name]["owned"]
        assert entry["stamp"] == (file_stamp(fix.root / name) if name in files else identity(fix.root / name))
        if name in files:
            assert (fix.root / name).read_bytes() == files[name]
    for name, entry in before.items():
        assert snapshot(fix.root)[name] == entry
    assert fix.source.read_bytes() == manifest_bytes
    encoded = fix.receipt.read_bytes()
    assert invoke(app, fix, "verify", timeout=timeout) == report and fix.receipt.read_bytes() == encoded
    return before


def clean(app: Application, fix: Fixture, before: dict, timeout: int = 30) -> None:
    report = invoke(app, fix, "cleanup", timeout=timeout)
    assert report["phase"] == "cleaned"
    assert snapshot(fix.root) == before
    assert receipt(fix)["phase"] == "cleaned"
    assert invoke(app, fix, "cleanup", timeout=timeout) == report
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def reject(app: Application, fix: Fixture, mode: str, message: str = "", **extra: str) -> None:
    before = snapshot(fix.root)
    saved = fix.receipt.read_bytes() if fix.receipt.exists() else None
    result = app.run(fix.directory, fix.settings(mode, **extra), timeout=30)
    assert result.returncode != 0, result.stdout
    assert message in result.stderr, result.stderr
    assert snapshot(fix.root) == before
    assert (fix.receipt.read_bytes() if fix.receipt.exists() else None) == saved
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def pause(app: Application, fix: Fixture, mode: str, point: str, signal: Path | None = None) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.directory,
        env=app.environment(
            fix.settings(mode, FIXTURE_PAUSE=point, FIXTURE_CONTINUE=str(signal or fix.directory / "continue"))
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(15), "fixture process did not pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + point
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def check_basics(app: Application, directory: Path) -> None:
    for existing in [False, True]:
        fix = fixture(directory, "existing" if existing else "new", existing=existing)
        before = construct(app, fix)
        reject(app, fix, "create")
        clean(app, fix, before)
        reject(app, fix, "verify", "not ready")
        if not existing:
            # An old cleanup receipt must not claim a replacement tree at the same path.
            fix.root.mkdir()
            (fix.root / "new-owner.txt").write_bytes(b"keep")
            reject(app, fix, "cleanup")
    empty = fixture(directory, "empty")
    empty.manifest["entries"] = []
    empty.manifest.update(max_entries=1, max_bytes=0)
    empty.save()
    clean(app, empty, construct(app, empty))
    maximum_name = fixture(directory, "maximum-name")
    maximum_name.manifest["entries"] = [
        {"path": "a" * 255, "kind": "text", "data": ""},
        {"path": "/".join(["x" * 250] * 4 + ["y" * 20]), "kind": "directory"},
        {"path": "/".join(["depth"] * 16), "kind": "directory"},
    ]
    maximum_name.save()
    clean(app, maximum_name, construct(app, maximum_name))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_invalid(app: Application, directory: Path) -> int:
    count = 0
    bad_names = [
        "",
        "/absolute",
        "..",
        "a/../b",
        "a/./b",
        "a//b",
        "a/",
        "nul\0name",
        "x" * 256,
        "😀" * 64,
        "/".join(["depth"] * 17),
        "/".join(["x" * 250] * 4 + ["y" * 21]),
    ]
    bad_entries = [[{"path": name, "kind": "text", "data": "value"}] for name in bad_names]
    bad_entries += [
        [{"path": "x", "kind": "text", "data": "a"}, {"path": "x", "kind": "directory"}],
        [{"path": "x", "kind": "directory"}, {"path": "x", "kind": "directory"}],
        [{"path": "x", "kind": "text", "data": "a"}, {"path": "x/y", "kind": "text", "data": "b"}],
        [{"path": "x", "kind": "text", "data": 1}],
        [{"path": "x", "kind": "directory", "data": ""}],
        [{"path": "x", "kind": "symlink", "data": "elsewhere"}],
        [{"path": "x", "kind": "text"}],
        [{"path": "x", "kind": "text", "data": "x" * 1048577}],
    ]
    bad_entries += [
        [{"path": "x", "kind": "base64", "data": text}] for text in ["A", "%%", "Zh==", "AA=", "AAAA\n", "_-8="]
    ]
    for index, entries in enumerate(bad_entries):
        fix = fixture(directory, f"bad-entries-{index}")
        fix.manifest["entries"] = entries
        fix.save()
        reject(app, fix, "create")
        assert not fix.root.exists() and not fix.receipt.exists()
        count += 1
    for index, changes in enumerate(
        [
            {"max_entries": 0},
            {"max_entries": 1001},
            {"max_entries": True},
            {"max_bytes": -1},
            {"max_bytes": 4194305},
            {"max_bytes": 1.0},
            {"entries": {}},
            {"extra": True},
            {"root": "/"},
            {"root": ""},
            {"root": "nul\0root"},
        ]
    ):
        fix = fixture(directory, f"bad-config-{index}")
        fix.manifest.update(changes)
        fix.save()
        reject(app, fix, "create")
        count += 1
    for index, data in enumerate([b"[]", b"{invalid", b"\xff", b'{"x":"\\ud800"}', b"{}" + b" " * 8388608]):
        fix = fixture(directory, f"bad-json-{index}")
        fix.source.write_bytes(data)
        reject(app, fix, "create")
        count += 1
    for index, kind in enumerate(["file", "directory", "symlink", "dangling", "fifo", "parent-file", "parent-symlink"]):
        fix = fixture(directory, f"collision-{index}", simple=True)
        fix.root.mkdir()
        target = fix.root / ("folder" if kind.startswith("parent") else "a.txt")
        if kind in {"file", "parent-file"}:
            target.write_bytes(b"existing")
        elif kind == "directory":
            target.mkdir()
        elif kind == "fifo":
            os.mkfifo(target)
        else:
            target.symlink_to(fix.directory if kind != "dangling" else fix.directory / "absent")
        reject(app, fix, "create")
        assert not fix.receipt.exists()
        count += 1
    exact = fixture(directory, "exact", simple=True)
    exact.manifest.update(max_entries=4, max_bytes=11)
    exact.save()
    for field, number in [("max_entries", 3), ("max_bytes", 10)]:
        before = exact.manifest[field]
        exact.manifest[field] = number
        exact.save()
        reject(app, exact, "create")
        exact.manifest[field] = before
        count += 1
    exact.save()
    clean(app, exact, construct(app, exact))
    return count


def check_conflicts(app: Application, directory: Path) -> int:
    cases = ["content", "mode", "hardlink", "replacement", "symlink", "foreign-root", "foreign-directory"]
    for kind in cases:
        fix = fixture(directory, "changed-" + kind, simple=True)
        construct(app, fix)
        target = fix.root / "a.txt"
        if kind == "content":
            stamp = target.stat()
            target.write_bytes(b"other")
            os.utime(target, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        elif kind == "mode":
            target.chmod(target.stat().st_mode ^ stat.S_IXUSR)
        elif kind == "hardlink":
            os.link(target, fix.directory / "extra-link")
        elif kind == "replacement":
            target.rename(fix.directory / "original")
            target.write_bytes(b"first")
        elif kind == "symlink":
            target.rename(fix.directory / "original")
            target.symlink_to(fix.directory / "original")
        else:
            parent = fix.root if kind == "foreign-root" else fix.root / "folder"
            (parent / "unrelated.txt").write_bytes(b"keep")
        reject(app, fix, "verify")
        reject(app, fix, "cleanup")
    reused = fixture(directory, "reused-changes", existing=True)
    construct(app, reused)
    (reused.root / "keep.txt").write_bytes(b"edited pre-existing file")
    (reused.root / "shared/unrelated.txt").write_bytes(b"new unrelated file")
    before = snapshot(reused.root)
    for name, entry in receipt(reused)["entries"].items():
        if entry["owned"]:
            before.pop(name or ".")
    clean(app, reused, before)
    for index, change in enumerate(["checksum", "step", "phase", "null", "missing-parent", "size", "reused-file"]):
        fix = fixture(directory, f"bad-receipt-{index}", simple=True)
        before = construct(app, fix)
        original = fix.receipt.read_bytes()
        body = receipt(fix)
        if change == "step":
            body["step"] = 5
        elif change == "phase":
            body["phase"] = "unknown"
        elif change == "null":
            body["entries"]["a.txt"]["stamp"] = None
        elif change == "missing-parent":
            del body["entries"]["folder"]
        elif change == "size":
            body["entries"]["a.txt"]["size"] = -1
        elif change == "reused-file":
            body["entries"]["a.txt"]["owned"] = False
        fix.receipt.write_text(
            json.dumps({"checksum": "bad" if change == "checksum" else checksum(body), "receipt": body})
        )
        reject(app, fix, "cleanup")
        fix.receipt.write_bytes(original)
        clean(app, fix, before)
    return len(cases) + 8


def check_control_paths(app: Application, directory: Path) -> int:
    for kind in ["same", "hardlink", "receipt-inside", "manifest-inside", "source-symlink", "receipt-symlink", "lock"]:
        fix = fixture(directory, "control-" + kind, simple=True)
        extra = {}
        if kind == "same":
            extra["FIXTURE_RECEIPT"] = str(fix.source)
        elif kind == "hardlink":
            os.link(fix.source, fix.receipt)
        elif kind == "receipt-inside":
            fix.root.mkdir()
            extra["FIXTURE_RECEIPT"] = str(fix.root / "receipt.json")
        elif kind == "manifest-inside":
            fix.root.mkdir()
            inside = fix.root / "fixtures.json"
            inside.write_bytes(fix.source.read_bytes())
            extra["FIXTURE_MANIFEST"] = str(inside)
        elif kind == "source-symlink":
            link = fix.directory / "linked.json"
            link.symlink_to(fix.source)
            extra["FIXTURE_MANIFEST"] = str(link)
        elif kind == "receipt-symlink":
            fix.receipt.symlink_to(fix.directory / "absent")
        else:
            extra["FIXTURE_RECEIPT"] = str(fix.directory / (".py2rust-fixture-" + checksum(str(fix.root)) + ".lock"))
        source = fix.source.read_bytes()
        reject(app, fix, "create", **extra)
        assert fix.source.read_bytes() == source
    fix = fixture(directory, "lock-contention", simple=True)
    process = pause(app, fix, "create", "receipt:0")
    try:
        reject(app, fix, "create")
        reject(app, fix, "cleanup")
        (fix.directory / "continue").touch()
        output, error = process.communicate(timeout=20)
        assert process.returncode == 0, (output, error)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    clean(app, fix, {})
    return 8


def interrupted(app: Application, fix: Fixture, mode: str, point: str, kill: bool = False) -> None:
    if kill:
        process = pause(app, fix, mode, point)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode == -9
    else:
        result = app.run(fix.directory, fix.settings(mode, FIXTURE_FAIL=point))
        assert result.returncode != 0 and "injected failure: " + point in result.stderr, result.stderr
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_creation_interruptions(app: Application, directory: Path) -> int:
    points = ["receipt:0"] + [f"{label}:{index}" for label in ["before", "written", "recorded"] for index in range(4)]
    cases = [(point, False) for point in points] + [("recorded:1", True), ("written:1", True)]
    for number, (point, kill) in enumerate(cases):
        fix = fixture(directory, f"create-stop-{number}", simple=True)
        interrupted(app, fix, "create", point, kill)
        body = receipt(fix)
        assert body["phase"] == "building"
        if point.startswith("written:"):
            reject(app, fix, "cleanup", "unrecorded")
            # No ownership stamp was saved for this object. Only the independent
            # fixture operator removes it; the application must never adopt it.
            name = sorted(body["entries"])[int(point.split(":")[1])]
            assert body["entries"][name]["stamp"] is None
            path = fix.root / name
            path.rmdir() if path.is_dir() else path.unlink()
        clean(app, fix, {})
    return len(cases)


def check_cleanup_interruptions(app: Application, directory: Path) -> int:
    points = ["cleaning:0"] + [f"{label}:{index}" for label in ["removing", "removed"] for index in range(4)]
    points += [f"saved:{index}" for index in range(1, 5)]
    cases = [(point, False) for point in points] + [("removed:0", True), ("removed:3", True)]
    for number, (point, kill) in enumerate(cases):
        fix = fixture(directory, f"cleanup-stop-{number}", simple=True)
        before = construct(app, fix)
        interrupted(app, fix, "cleanup", point, kill)
        assert receipt(fix)["phase"] == "cleaning"
        clean(app, fix, before)
    return len(cases)


def check_permissions(app: Application, directory: Path) -> int:
    assert os.getuid() != 0, "permission checks require an unprivileged account"
    fix = fixture(directory, "receipt-permission", simple=True)
    fix.root = fix.directory / "writable-parent/tree"
    fix.root.parent.mkdir()
    fix.manifest["root"] = str(fix.root)
    fix.save()
    fix.directory.chmod(0o500)
    try:
        result = app.run(fix.directory, fix.settings("create"))
        assert result.returncode != 0 and not fix.root.exists() and not fix.receipt.exists()
    finally:
        fix.directory.chmod(0o700)
    clean(app, fix, construct(app, fix))
    fix = fixture(directory, "create-permission", simple=True)
    fix.root.mkdir()
    fix.root.chmod(0o500)
    try:
        result = app.run(fix.directory, fix.settings("create"))
        assert result.returncode != 0 and receipt(fix)["phase"] == "building"
        clean(app, fix, snapshot(fix.root))
    finally:
        fix.root.chmod(0o700)
    fix = fixture(directory, "cleanup-permission", simple=True)
    before = construct(app, fix)
    folder = fix.root / "folder"
    folder.chmod(0o500)
    try:
        original = snapshot(fix.root)
        result = app.run(fix.directory, fix.settings("cleanup"))
        assert result.returncode != 0 and receipt(fix)["phase"] == "cleaning"
        assert snapshot(fix.root) == original
    finally:
        folder.chmod(0o700)
    clean(app, fix, before)
    fix = fixture(directory, "receipt-update-permission", simple=True)
    signal = directory / "continue-permission"
    process = pause(app, fix, "create", "before:1", signal)
    try:
        fix.directory.chmod(0o500)
        signal.touch()
        output, error = process.communicate(timeout=20)
        assert process.returncode != 0, (output, error)
        assert (fix.root / "a.txt").read_bytes() == b"first"
        assert receipt(fix)["entries"]["a.txt"]["stamp"] is None
    finally:
        fix.directory.chmod(0o700)
        if process.poll() is None:
            process.kill()
            process.communicate()
    reject(app, fix, "cleanup", "unrecorded")
    (fix.root / "a.txt").unlink()
    clean(app, fix, {})
    return 4


def check_limits(app: Application, directory: Path) -> dict:
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    large = fixture(directory, "byte-limit")
    data = bytes(range(256)) * 4096
    large.manifest["entries"] = [
        {"path": f"{index}.bin", "kind": "base64", "data": base64.b64encode(data).decode()} for index in range(4)
    ]
    large.manifest["max_entries"] = 5
    large.save()
    clean(limited, large, construct(limited, large, timeout=120), timeout=120)
    too_large = fixture(directory, "over-byte-limit")
    too_large.manifest["entries"] = copy.deepcopy(large.manifest["entries"]) + [
        {"path": "extra", "kind": "text", "data": "x"}
    ]
    too_large.save()
    reject(limited, too_large, "create", "budget")
    many = fixture(directory, "entry-limit")
    many.manifest["entries"] = [
        {"path": f"file-{index:04d}", "kind": "text", "data": str(index)} for index in range(999)
    ]
    many.manifest["max_entries"] = 999
    many.save()
    reject(limited, many, "create", "entry budget")
    many.manifest["max_entries"] = 1000
    many.save()
    clean(limited, many, construct(limited, many, timeout=180), timeout=180)
    return {"memory_limit": 134217728, "payload_bytes": 4194304, "entries": 1000}


def check(app: Application, directory: Path) -> dict:
    check_basics(app, directory)
    invalid = check_invalid(app, directory)
    conflicts = check_conflicts(app, directory)
    control_paths = check_control_paths(app, directory)
    creation = check_creation_interruptions(app, directory)
    cleanup = check_cleanup_interruptions(app, directory)
    permissions = check_permissions(app, directory)
    limits = check_limits(app, directory)
    return {
        "bytes_and_receipts": "passed",
        "invalid_manifests": invalid,
        "ownership_conflicts": conflicts,
        "control_paths_and_lock": control_paths,
        "creation_interruptions": creation,
        "cleanup_interruptions": cleanup,
        "permission_failures": permissions,
        "limits": limits,
    }
