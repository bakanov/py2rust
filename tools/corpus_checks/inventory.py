"""Filesystem-backed inventory oracles independent of the application's traversal code."""

from __future__ import annotations

import json
import os
import re
import socket
import stat
from collections import defaultdict
from pathlib import Path

from .common import Application


def metadata(path: Path, relative: str) -> dict:
    row = path.lstat()
    kinds = [
        ("file", stat.S_ISREG),
        ("directory", stat.S_ISDIR),
        ("symlink", stat.S_ISLNK),
        ("fifo", stat.S_ISFIFO),
        ("socket", stat.S_ISSOCK),
        ("block", stat.S_ISBLK),
        ("char", stat.S_ISCHR),
    ]
    kind = next((name for name, check in kinds if check(row.st_mode)), "other")
    result = {
        "path": relative,
        "depth": 0 if relative == "." else relative.count("/") + 1,
        "status": "ok",
        "kind": kind,
        "size": row.st_size,
        "mode": stat.S_IMODE(row.st_mode),
        "mtime_ns": row.st_mtime_ns,
        "ctime_ns": row.st_ctime_ns,
        "device": row.st_dev,
        "inode": row.st_ino,
        "links": row.st_nlink,
    }
    if kind == "symlink":
        result["target"] = os.readlink(path)
    if kind == "directory":
        result["scan"] = "complete"
    return result


def oracle(root: Path, patterns: list[str]) -> tuple[list[dict], list[str], list[dict]]:
    rows = {".": metadata(root, ".")}
    exclusions = []
    failures = []

    def failed(error: OSError) -> None:
        relative = Path(error.filename).relative_to(root).as_posix()
        rows[relative]["scan"] = "error"
        failures.append({"path": relative, "operation": "list"})
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    for parent, directories, files in os.walk(root, followlinks=False, onerror=failed):
        for name in sorted(directories + files):
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            if any(re.search(pattern, relative, re.ASCII) for pattern in patterns):
                exclusions.append(relative)
                if name in directories:
                    directories.remove(name)
            else:
                rows[relative] = metadata(path, relative)
    return [rows[name] for name in sorted(rows)], sorted(exclusions), failures


def verify_summary(report: dict, root: Path) -> None:
    kinds = dict.fromkeys(["file", "directory", "symlink", "fifo", "socket", "block", "char", "other"], 0)
    extensions = defaultdict(lambda: {"files": 0, "bytes": 0})
    unique = {}
    modified = []
    logical = 0
    empty = 0
    for row in report["entries"]:
        if row["status"] != "ok":
            continue
        kinds[row["kind"]] += 1
        if row["kind"] == "file":
            logical += row["size"]
            unique[(row["device"], row["inode"])] = row["size"]
            modified.append(row["mtime_ns"])
            suffix = Path(row["path"]).suffix.lower()
            group = suffix if suffix not in ["", "."] else "(none)"
            extensions[group]["files"] += 1
            extensions[group]["bytes"] += row["size"]
        elif row["kind"] == "directory" and row["scan"] == "complete" and not os.listdir(root / row["path"]):
            empty += 1
    assert report["counts"] == kinds
    assert report["logical_bytes"] == logical and report["unique_bytes"] == sum(unique.values())
    assert report["unique_files"] == len(unique) and report["empty_directories"] == empty
    assert report["extensions"] == dict(extensions)
    assert report["file_mtime_ns"] == {"oldest": min(modified, default=0), "newest": max(modified, default=0)}
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def invoke(app: Application, work: Path, root: Path, changes: dict | None = None, exit_code: int = 0) -> dict:
    config = work / "inventory.json"
    output = work / "report.json"
    policy = {"root": str(root), **(changes or {})}
    config.write_text(json.dumps(policy))
    result = app.run(
        work,
        {"INVENTORY_CONFIG": str(config), "INVENTORY_REPORT": str(output), "INVENTORY_ROOT": str(root)},
        timeout=30,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    report = json.loads(output.read_text())
    assert report["root"] == str(root.resolve()) and report["version"] == 1
    assert report["entries"] == sorted(report["entries"], key=lambda row: row["path"])
    compact = {
        key: report[key]
        for key in ["root", "complete", "counts", "logical_bytes", "unique_bytes", "errors", "omissions"]
    }
    assert json.loads(result.stdout) == compact
    assert report["complete"] == (exit_code == 0)
    return report


def check(app: Application, directory: Path) -> dict:
    assert os.geteuid() != 0, "the unreadable-directory oracle requires an unprivileged user"
    root = directory / "tree"
    root.mkdir()
    files = {
        "note.TXT": b"hello\n",
        "image.bin": bytes(range(256)),
        ".profile": b"hidden",
        "archive.tar.GZ": b"zip",
        "trailing.": b"",
        "世界.Ω": "😀".encode(),
        "nested/inner/data.txt": b"text",
        "nested/.config.JSON": b"{}",
        "no-read.dat": b"metadata only",
        ".git/config": b"excluded",
        "cache/old.tmp": b"excluded",
        "ignored-only/a.skip": b"excluded",
    }
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "empty").mkdir()
    (root / "nested" / "empty").mkdir()
    (root / "hard.DATA").hardlink_to(root / "note.TXT")
    sparse = root / "large.sparse"
    with sparse.open("wb") as stream:
        stream.seek(2**32 + 7)
        stream.write(b"x")
    (root / "link-file").symlink_to("note.TXT")
    (root / "link-directory").symlink_to("nested", target_is_directory=True)
    (root / "broken").symlink_to("no target")
    (root / "cycle").symlink_to("cycle")
    (root / "parent-loop").symlink_to(".", target_is_directory=True)
    outside = directory / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("outside the inventory")
    (root / "external").symlink_to(outside, target_is_directory=True)
    os.mkfifo(root / "pipe")
    locked = root / "locked"
    locked.mkdir()
    (locked / "secret").write_bytes(b"not observed")
    patterns = [r"(^|/)\.git(/|$)", r"^cache(/|$)", r"\.skip$"]
    # A Unix socket's pathname is bounded, so place the socket under a short
    # independent temporary tree and hard-link its inode into this fixture.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="p2r-inv-") as short, socket.socket(socket.AF_UNIX) as listener:
        listener.bind(str(Path(short) / "socket"))
        (root / "socket").hardlink_to(Path(short) / "socket")
        for index, path in enumerate(sorted(root.rglob("*"))):
            os.utime(path, ns=(1666666666123456789 + index, 1555555555987654321 + index), follow_symlinks=False)
        os.utime(root / "note.TXT", ns=(1, -1))
        (root / "no-read.dat").chmod(0)
        locked.chmod(0)
        try:
            expected, excluded, failures = oracle(root, patterns)
            report = invoke(app, directory, root, {"exclude": patterns}, 2)
            assert report["entries"] == expected
            assert report["excluded"] == excluded and report["errors"] == failures and report["omissions"] == []
            verify_summary(report, root)
            assert "locked/secret" not in [row["path"] for row in report["entries"]]
            assert report["logical_bytes"] - report["unique_bytes"] == len(files["note.TXT"])
            assert report["empty_directories"] == 2
            before = (directory / "report.json").read_bytes()
            assert invoke(app, directory, root, {"exclude": patterns}, 2) == report
            assert (directory / "report.json").read_bytes() == before
            # A caller-selected symlink root resolves once; interior links never follow.
            alias = directory / "root-link"
            alias.symlink_to(root, target_is_directory=True)
            assert invoke(app, directory, alias, {"exclude": patterns}, 2) == report
        finally:
            locked.chmod(0o700)
            (root / "no-read.dat").chmod(0o600)
        complete = invoke(app, directory, root, {"exclude": patterns})
        expected, excluded, failures = oracle(root, patterns)
        assert (
            complete["entries"] == expected
            and complete["excluded"] == excluded
            and complete["errors"] == failures == []
        )
        verify_summary(complete, root)
    bounds = check_limits(app, directory)
    failures = check_bad_entries(app, directory)
    configurations = check_configuration(app, directory)
    scale = directory / "scale"
    scale.mkdir()
    for index in range(2000):
        (scale / f"file-{index:05d}.txt").write_bytes(b"x")
    scaled = invoke(app, directory, scale)
    assert scaled["counts"]["file"] == scaled["logical_bytes"] == scaled["unique_bytes"] == 2000
    assert scaled["extensions"] == {".txt": {"files": 2000, "bytes": 2000}}
    assert len(scaled["entries"]) == 2001
    for row in scaled["entries"]:
        assert row == metadata(scale / row["path"], row["path"])
    return {
        "sparse_bytes": 2**32 + 8,
        "hardlink_savings": len(files["note.TXT"]),
        "empty_directories": 2,
        "symlinks": 6,
        "unreadable": "metadata retained; subtree error recorded",
        "repeat_manifest": "byte-identical",
        "bounds": bounds,
        "entry_failures": failures,
        "invalid_configurations": configurations,
        "scale": {"files": 2000, "entries": 2001, "logical_bytes": 2000},
    }


def check_limits(app: Application, directory: Path) -> dict:
    root = directory / "limits"
    (root / "a").mkdir(parents=True)
    (root / "a/x").write_bytes(b"x")
    (root / "a/y").mkdir()
    (root / "b").write_bytes(b"b")
    (root / "c.skip").write_bytes(b"c")
    depth = invoke(app, directory, root, {"max_depth": 0}, 2)
    assert [row["path"] for row in depth["entries"]] == ["."]
    assert depth["omissions"] == [{"path": ".", "reason": "depth_limit"}]
    assert depth["empty_directories"] == 0
    entries = invoke(app, directory, root, {"max_entries": 2}, 2)
    assert [row["path"] for row in entries["entries"]] == [".", "a"]
    assert entries["omissions"] == [{"path": ".", "reason": "entry_limit"}, {"path": "a", "reason": "entry_limit"}]
    excluded = invoke(app, directory, root, {"max_entries": 2, "exclude": ["^a$"]}, 2)
    assert len(excluded["entries"]) == 1 and excluded["excluded"] == ["a"]
    assert excluded["omissions"] == [{"path": ".", "reason": "entry_limit"}]
    children = invoke(app, directory, root, {"max_children": 2}, 2)
    assert len(children["entries"]) == 1 and children["errors"] == [{"path": ".", "operation": "list"}]
    report = invoke(app, directory, root, {"max_entries": 6, "max_children": 3})
    assert len(report["entries"]) == 6 and report["empty_directories"] == 1
    before = (directory / "report.json").read_bytes()
    config = directory / "inventory.json"
    config.write_text(json.dumps({"root": str(root), "max_report_bytes": 1024}))
    result = app.run(
        directory,
        {
            "INVENTORY_CONFIG": str(config),
            "INVENTORY_REPORT": str(directory / "report.json"),
            "INVENTORY_ROOT": str(root),
        },
    )
    assert result.returncode != 0 and (directory / "report.json").read_bytes() == before
    empty = directory / "empty-tree"
    empty.mkdir()
    result = invoke(app, directory, empty)
    assert result["empty_directories"] == 1 and result["unique_bytes"] == 0
    assert result["file_mtime_ns"] == {"oldest": 0, "newest": 0}
    return {
        "depth": True,
        "entries_include_exclusions": True,
        "all_or_error_directory_limit": True,
        "report_limit_preserves_output": True,
        "empty_tree": True,
    }


def check_bad_entries(app: Application, directory: Path) -> list[str]:
    root = directory / "bad-entries"
    root.mkdir()
    (root / "valid.txt").write_bytes(b"kept")
    future = root / "future"
    future.write_bytes(b"")
    os.utime(future, ns=(2**63 + 100, 2**63 + 100))
    os.symlink(b"invalid\xff", os.fsencode(root / "bad-target"))
    invalid = root / "bad-names"
    invalid.mkdir()
    (invalid / "valid").write_bytes(b"not a complete directory listing")
    fd = os.open(os.fsencode(invalid) + b"/invalid\xff", os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(fd)
    report = invoke(app, directory, root, exit_code=2)
    assert report["errors"] == [
        {"path": "bad-names", "operation": "list"},
        {"path": "bad-target", "operation": "read_link"},
        {"path": "future", "operation": "stat"},
    ]
    rows = {row["path"]: row for row in report["entries"]}
    assert rows["bad-target"]["target"] is None and rows["bad-target"]["kind"] == "symlink"
    assert rows["future"] == {"path": "future", "depth": 1, "status": "error", "operation": "stat"}
    assert "bad-names/valid" not in rows and rows["valid.txt"]["size"] == 4
    assert report["logical_bytes"] == 4
    return ["non-UTF8 directory name", "non-UTF8 symlink target", "out-of-range timestamp"]


def check_configuration(app: Application, directory: Path) -> int:
    root = directory / "config-tree"
    root.mkdir()
    (root / "data").write_bytes(b"untouched")
    config = directory / "inventory.json"
    report = directory / "report.json"
    env = {"INVENTORY_CONFIG": str(config), "INVENTORY_REPORT": str(report), "INVENTORY_ROOT": str(root)}
    invalid = [
        {"unknown": 1},
        {"root": True},
        {"exclude": True},
        {"exclude": [True]},
        {"exclude": ["(?=x)"]},
        {"exclude": ["["]},
        {"exclude": ["x" * 1025]},
        {"exclude": ["x"] * 129},
    ]
    bounds = {
        "max_depth": (0, 256),
        "max_entries": (1, 200000),
        "max_children": (1, 100000),
        "max_report_bytes": (1024, 134217728),
    }
    for key, (low, high) in bounds.items():
        invalid.extend([{key: low - 1}, {key: high + 1}, {key: True}, {key: 1.5}, {key: "2"}])
    payloads = [json.dumps(value) for value in invalid] + ["[]", "null", "not JSON", " " * 65537]
    for text in payloads:
        config.write_text(text)
        report.write_text("previous report")
        result = app.run(directory, env)
        assert result.returncode != 0 and report.read_text() == "previous report", text[:100]
    config.write_text(json.dumps({"root": str(root)}))
    for path in [root / "missing", root / "data", Path("/")]:
        result = app.run(directory, dict(env, INVENTORY_ROOT=str(path)))
        assert result.returncode != 0 and report.read_text() == "previous report"
    inside = root / "inside.json"
    inside.write_text("source preserved")
    target = directory / "target.json"
    target.write_text("target preserved")
    symlink = directory / "output-link"
    symlink.symlink_to(target)
    alias = directory / "config-alias"
    alias.hardlink_to(config)
    for path in [inside, symlink, alias, root]:
        result = app.run(directory, dict(env, INVENTORY_REPORT=str(path)))
        assert result.returncode != 0
    assert inside.read_text() == "source preserved" and target.read_text() == "target preserved"
    assert alias.read_bytes() == config.read_bytes() and symlink.is_symlink()
    assert (root / "data").read_bytes() == b"untouched"
    return len(payloads) + 7
