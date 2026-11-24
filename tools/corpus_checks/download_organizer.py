"""Independent destination oracle, crash recovery, contention and filesystem faults."""

from __future__ import annotations

import copy
import datetime as dt
import fcntl
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
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def hashed(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def metadata(path: Path) -> dict:
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode)
    return {
        "kind": "file",
        "device": info.st_dev,
        "inode": info.st_ino,
        "size": info.st_size,
        "mode": stat.S_IMODE(info.st_mode),
        "links": info.st_nlink,
        "mtime_ns": info.st_mtime_ns,
        "sha256": hashed(path),
    }


def identity(path: Path) -> dict:
    info = path.lstat()
    assert stat.S_ISDIR(info.st_mode)
    return {"device": info.st_dev, "inode": info.st_ino}


def write(path: Path, data: bytes, stamp: int = 1709164800000000123) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, ns=(stamp, stamp))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@dataclass
class Fixture:
    directory: Path
    root: Path
    config: dict
    envelope: dict | None = None

    @property
    def plan(self) -> Path:
        return self.directory / "plan.json"

    @property
    def journal(self) -> Path:
        return self.directory / "journal.json"

    def save(self) -> None:
        (self.directory / "organize.json").write_text(json.dumps(self.config, ensure_ascii=False))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def settings(self, mode: str = "preview", **extra: str) -> dict[str, str]:
        return dict(
            ORGANIZE_CONFIG=str(self.directory / "organize.json"),
            ORGANIZE_PLAN=str(self.plan),
            ORGANIZE_JOURNAL=str(self.journal),
            ORGANIZE_MODE=mode,
            ORGANIZE_APPROVE=self.envelope["id"] if self.envelope else "",
            **extra,
        )


def fixture(directory: Path, name: str, minimal: bool = True) -> Fixture:
    work = directory / name
    root = work / "downloads"
    root.mkdir(parents=True)
    config = {
        "root": str(root),
        "categories": {
            "documents": [".txt", ".pdf", ".md"],
            "images": [".png", ".jpg"],
            "archives": [".zip", ".tar.gz", ".gz"],
        },
        "date_format": "%Y/%m",
        "include_hidden": False,
        "skip_suffixes": [".part", ".tmp", ".crdownload"],
        "max_entries": 10000,
        "max_files": 1000,
        "max_bytes": 17179869184,
    }
    result = Fixture(work, root, config)
    result.save()
    write(root / "a.txt", b"first download\0\xff")
    write(root / "b.txt", "second 世界\n".encode())
    if not minimal:
        write(root / "a (1).txt", b"planned collision")
        write(root / "documents/2024/02/a.txt", b"existing document")
        write(root / "bundle.tar.GZ", b"archive")
        write(root / "mystery.bin", bytes(range(256)) * 257)
        write(root / "old.TXT", b"pre-epoch", -1)
        write(root / "epoch.png", b"", 0)
        write(root / "future.jpg", b"future", 2147483648000000000)
        write(root / "README", b"extensionless")
        write(root / "trailing.", b"dot")
        write(root / ".notes.md", b"hidden")
        write(root / "still.PART", b"unfinished")
        write(root / "already/keep.txt", b"nested untouched")
        long_name = "😀" * 62 + ".pdf"
        write(root / long_name, b"long UTF-8 name")
        write(root / "documents/2024/02" / long_name, b"existing long name")
        write(root / "linked-a.bin", b"shared inode")
        os.link(root / "linked-a.bin", root / "linked-b.bin")
        (root / "link.txt").symlink_to(root / "a.txt")
        (root / "dangling.txt").symlink_to("absent")
        (root / "cycle").symlink_to(".")
        os.mkfifo(root / "special.fifo")
    return result


def oracle(fix: Fixture) -> tuple[list[dict], list[dict], dict]:
    rows, skipped = [], []
    parents = {".": identity(fix.root)}
    reserved = set()
    suffixes = sorted(
        ((suffix, category) for category, items in fix.config["categories"].items() for suffix in items),
        key=lambda pair: -len(pair[0]),
    )
    for path in sorted(fix.root.iterdir()):
        name = path.name
        mode = path.lstat().st_mode
        reason = ""
        if name.startswith(".py2rust-organize"):
            reason = "reserved"
        elif name.startswith(".") and not fix.config["include_hidden"]:
            reason = "hidden"
        elif stat.S_ISLNK(mode):
            reason = "symlink"
        elif stat.S_ISDIR(mode):
            reason = "directory"
        elif stat.S_ISFIFO(mode):
            reason = "fifo"
        elif any(name.lower().endswith(suffix) for suffix in fix.config["skip_suffixes"]):
            reason = "temporary"
        if reason:
            skipped.append({"source": name, "reason": reason})
            continue
        signature = metadata(path)
        category, extension = "other", path.suffix
        for suffix, label in suffixes:
            if len(name) > len(suffix) and name.lower().endswith(suffix):
                category, extension = label, name[-len(suffix) :]
                break
        date = dt.datetime.fromtimestamp(signature["mtime_ns"] // 1000000000, dt.timezone.utc).strftime(
            fix.config["date_format"]
        )
        stem = name[: -len(extension)] if extension else name
        for number in range(10001):
            addition = f" ({number})" if number else ""
            available = 255 - len((addition + extension).encode())
            filename = stem.encode()[:available].decode("utf-8", "ignore") + addition + extension
            target = str(Path(category) / date / filename)
            actual = fix.root / target
            if target not in reserved and not os.path.lexists(actual):
                break
        else:
            raise AssertionError("oracle collision budget")
        reserved.add(target)
        parent = Path(target).parent
        while str(parent) != ".":
            actual = fix.root / parent
            parents[str(parent)] = identity(actual) if os.path.lexists(actual) else None
            parent = parent.parent
        rows.append({"source": name, "target": target, "signature": signature, "category": category, "date": date})
    return rows, skipped, parents


def preview(app: Application, fix: Fixture) -> dict:
    originals = {
        p.name: metadata(p)
        for p in fix.root.iterdir()
        if p.is_file() and not p.is_symlink() and not p.name.startswith(".py2rust-organize")
    }
    result = app.run(fix.directory, fix.settings(), timeout=90)
    assert result.returncode == 0, result.stderr
    envelope = json.loads(result.stdout)
    rows, skipped, parents = oracle(fix)
    expected = {
        "version": 1,
        "root": str(fix.root),
        "max_bytes": fix.config["max_bytes"],
        "bytes": sum(row["signature"]["size"] for row in rows),
        "rows": rows,
        "skipped": skipped,
        "parents": parents,
    }
    assert envelope == {"id": checksum(expected), "plan": expected}, (envelope, expected)
    assert json.loads(fix.plan.read_bytes()) == envelope and not fix.journal.exists()
    for name, signature in originals.items():
        assert metadata(fix.root / name) == signature, "preview changed a source"
    fix.envelope = envelope
    return envelope


def apply(app: Application, fix: Fixture) -> None:
    result = app.run(fix.directory, fix.settings("apply"), timeout=90)
    assert result.returncode == 0, result.stderr
    plan = fix.envelope["plan"]
    assert json.loads(result.stdout) == {
        "id": fix.envelope["id"],
        "status": "complete",
        "files": len(plan["rows"]),
        "bytes": plan["bytes"],
    }
    for row in plan["rows"]:
        assert not os.path.lexists(fix.root / row["source"])
        assert metadata(fix.root / row["target"]) == row["signature"]
    saved = json.loads(fix.journal.read_bytes())
    assert saved["checksum"] == checksum(saved["receipt"])
    assert saved["receipt"]["step"] == len(plan["rows"]) and saved["receipt"]["complete"] is True
    for parent, saved_identity in saved["receipt"]["parents"].items():
        assert identity(fix.root / parent) == saved_identity
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def rejection(app: Application, fix: Fixture, mode: str = "preview", needle: str = "") -> subprocess.CompletedProcess:
    result = app.run(fix.directory, fix.settings(mode), timeout=20)
    assert result.returncode != 0, result.stdout
    assert needle in result.stderr, result.stderr
    return result


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.directory,
        env=app.environment(
            fix.settings("apply", ORGANIZE_PAUSE=label, ORGANIZE_CONTINUE=str(fix.directory / "continue"))
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(15), "organizer did not reach requested pause"
        assert process.stdout.readline().rstrip() == "PAUSED " + label
        return process
    except BaseException:
        process.kill()
        process.communicate()
        raise


def resume(process: subprocess.Popen, fix: Fixture, succeeds: bool) -> None:
    try:
        (fix.directory / "continue").touch()
        output, error = process.communicate(timeout=15)
        assert (process.returncode == 0) == succeeds, output + error
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_basics(app: Application, directory: Path) -> None:
    fix = fixture(directory, "basics", minimal=False)
    envelope = preview(app, fix)
    names = {row["source"]: row["target"] for row in envelope["plan"]["rows"]}
    assert names["a.txt"] == "documents/2024/02/a (2).txt"
    assert names["bundle.tar.GZ"] == "archives/2024/02/bundle.tar.GZ"
    assert names["old.TXT"] == "documents/1969/12/old.TXT" and names["epoch.png"] == "images/1970/01/epoch.png"
    apply(app, fix)
    assert (fix.root / "documents/2024/02/a.txt").read_bytes() == b"existing document"
    assert (fix.root / "still.PART").read_bytes() == b"unfinished"
    assert (fix.root / ".notes.md").read_bytes() == b"hidden"
    assert (fix.root / "already/keep.txt").read_bytes() == b"nested untouched"
    assert (fix.root / "cycle").is_symlink() and stat.S_ISFIFO((fix.root / "special.fifo").lstat().st_mode)
    apply(app, fix)
    plan_before = fix.plan.read_bytes()
    rejection(app, fix, needle="keep the plan with its journal")
    assert fix.plan.read_bytes() == plan_before
    settings = dict(
        fix.settings(),
        ORGANIZE_PLAN=str(fix.directory / "next-plan.json"),
        ORGANIZE_JOURNAL=str(fix.directory / "next-journal.json"),
    )
    result = app.run(fix.directory, settings)
    assert result.returncode == 0 and json.loads(result.stdout)["plan"]["rows"] == []
    hidden = fixture(directory, "hidden")
    hidden.config["include_hidden"] = True
    hidden.config["date_format"] = "%Y-%m-%d"
    hidden.save()
    write(hidden.root / ".notes.md", b"include this")
    write(hidden.root / ".config", b"extensionless dotfile")
    preview(app, hidden)
    apply(app, hidden)
    assert (hidden.root / "documents/2024-02-29/.notes.md").is_file()
    assert (hidden.root / "other/2024-02-29/.config").is_file()
    empty = fixture(directory, "empty")
    (empty.root / "a.txt").unlink()
    (empty.root / "b.txt").unlink()
    preview(app, empty)
    apply(app, empty)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_interruptions(app: Application, directory: Path) -> int:
    labels = [
        "journal:0",
        "mkdir:1",
        "directory:1",
        "mkdir:2",
        "directory:2",
        "mkdir:3",
        "directory:3",
        "before:0",
        "renamed:0",
        "synced:0",
        "saved:1",
        "before:1",
        "renamed:1",
        "synced:1",
        "saved:2",
        "complete:2",
    ]
    for index, label in enumerate(labels):
        fix = fixture(directory, f"interruption-{index}")
        preview(app, fix)
        result = app.run(fix.directory, fix.settings("apply", ORGANIZE_STOP=label))
        assert result.returncode == 75, (label, result.stderr)
        for row in fix.envelope["plan"]["rows"]:
            candidates = [fix.root / row["source"], fix.root / row["target"]]
            assert sum(path.exists() for path in candidates) == 1
            assert metadata(next(path for path in candidates if path.exists())) == row["signature"]
        apply(app, fix)
        apply(app, fix)
    for index, label in enumerate(["mkdir:2", "renamed:0", "saved:1"]):
        fix = fixture(directory, f"killed-{index}")
        preview(app, fix)
        process = paused(app, fix, label)
        process.kill()
        process.communicate(timeout=10)
        assert process.returncode < 0
        apply(app, fix)
    return len(labels)


def check_conflicts(app: Application, directory: Path) -> int:
    for index, operation in enumerate(["source", "target", "symlink", "parent"]):
        fix = fixture(directory, f"concurrent-{index}")
        preview(app, fix)
        row = fix.envelope["plan"]["rows"][0]
        source, target = fix.root / row["source"], fix.root / row["target"]
        original = source.read_bytes()
        process = paused(app, fix, "before:0")
        try:
            if operation == "source":
                source.write_bytes(b"changed input")
                os.utime(source, ns=(row["signature"]["mtime_ns"], row["signature"]["mtime_ns"]))
            elif operation == "target":
                target.write_bytes(b"unrelated destination")
            elif operation == "symlink":
                target.symlink_to(fix.directory / "outside")
            else:
                target.parent.rename(fix.directory / "old-parent")
                target.parent.mkdir()
            resume(process, fix, False)
            assert source.exists() and (fix.root / "b.txt").exists()
            if operation == "source":
                assert source.read_bytes() == b"changed input"
                source.write_bytes(original)
                os.utime(source, ns=(row["signature"]["mtime_ns"], row["signature"]["mtime_ns"]))
            elif operation in {"target", "symlink"}:
                assert (
                    target.is_symlink() if operation == "symlink" else target.read_bytes() == b"unrelated destination"
                )
                target.unlink()
            else:
                assert not list(target.parent.iterdir())
                target.parent.rmdir()
                (fix.directory / "old-parent").rename(target.parent)
            apply(app, fix)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
    changed = fixture(directory, "changed-completed-prefix")
    preview(app, changed)
    assert app.run(changed.directory, changed.settings("apply", ORGANIZE_STOP="saved:1")).returncode == 75
    row = changed.envelope["plan"]["rows"][0]
    (changed.root / row["target"]).write_bytes(b"external edit")
    rejection(app, changed, "apply", "tree differs")
    assert (changed.root / "b.txt").exists()
    unrecorded = fixture(directory, "occupied-unrecorded-directory")
    preview(app, unrecorded)
    assert app.run(unrecorded.directory, unrecorded.settings("apply", ORGANIZE_STOP="mkdir:1")).returncode == 75
    write(unrecorded.root / "documents/intruder", b"keep me")
    rejection(app, unrecorded, "apply", "unrecorded directory is not empty")
    assert (unrecorded.root / "a.txt").exists()
    (unrecorded.root / "documents/intruder").unlink()
    apply(app, unrecorded)
    appeared = fixture(directory, "parent-appeared")
    preview(app, appeared)
    (appeared.root / "documents").mkdir()
    rejection(app, appeared, "apply", "unplanned directory appeared")
    assert not appeared.journal.exists()
    (appeared.root / "documents").rmdir()
    apply(app, appeared)

    locked = fixture(directory, "locked")
    preview(app, locked)
    process = paused(app, locked, "journal:0")
    try:
        rejection(app, locked, "apply")
        with (locked.root / ".py2rust-organize.lock").open("rb") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("organizer did not retain the root lock")
        resume(process, locked, True)
        apply(app, locked)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
    return 8


def check_invalid(app: Application, directory: Path) -> int:
    count = 0
    changes = [
        {"root": "/"},
        {"max_entries": 0},
        {"max_entries": 10001},
        {"max_files": 0},
        {"max_files": 1001},
        {"max_bytes": 0},
        {"max_bytes": 1099511627777},
        {"max_files": True},
        {"max_bytes": 1.0},
        {"include_hidden": 1},
        {"extra": 1},
        {"categories": []},
        {"categories": {"bad/name": [".txt"]}},
        {"categories": {"one": [".TXT"]}},
        {"categories": {"one": []}},
        {"categories": {"one": [".txt"], "two": [".txt"]}},
        {"categories": {"one": [".tar..gz"]}},
        {"categories": {"one": [7]}},
        {"skip_suffixes": ["tmp"]},
        {"date_format": "%"},
        {"date_format": "%Q"},
        {"date_format": "/absolute"},
        {"date_format": "%Y/../month"},
        {"date_format": ""},
        {"date_format": "x" * 1025},
    ]
    for index, updates in enumerate(changes):
        fix = fixture(directory, f"invalid-config-{index}")
        fix.config.update(updates)
        fix.save()
        rejection(app, fix)
        assert not fix.plan.exists() and (fix.root / "a.txt").exists()
        count += 1
    for index, contents in enumerate([b"{bad", b"[]", b'{"x":NaN}', b"\xff", b"{}" + b" " * 2097152]):
        fix = fixture(directory, f"invalid-json-{index}")
        (fix.directory / "organize.json").write_bytes(contents)
        rejection(app, fix)
        assert not fix.plan.exists()
        count += 1
    for index, conflict in enumerate(
        ["symlink-parent", "file-parent", "hardlink-plan", "symlink-plan", "same-sidecar"]
    ):
        fix = fixture(directory, f"invalid-path-{index}")
        settings = fix.settings()
        if conflict == "symlink-parent":
            (fix.root / "documents").symlink_to(fix.directory)
        elif conflict == "file-parent":
            write(fix.root / "documents", b"not a directory")
        elif conflict == "hardlink-plan":
            os.link(fix.root / "a.txt", fix.plan)
        elif conflict == "symlink-plan":
            fix.plan.symlink_to(fix.root / "a.txt")
        else:
            settings["ORGANIZE_JOURNAL"] = str(fix.plan)
        original = (fix.root / "a.txt").read_bytes()
        result = app.run(fix.directory, settings)
        assert result.returncode != 0 and (fix.root / "a.txt").read_bytes() == original
        count += 1
    for index, fault in enumerate(["digest", "source", "target", "wrong-id", "journal", "step", "completed"]):
        fix = fixture(directory, f"invalid-plan-{index}")
        preview(app, fix)
        if fault in {"digest", "source", "target"}:
            modified = copy.deepcopy(fix.envelope)
            if fault == "digest":
                modified["id"] = "0" * 64
            else:
                modified["plan"]["rows"][0][fault] = "../escape"
                modified["id"] = checksum(modified["plan"])
            fix.plan.write_text(json.dumps(modified))
            fix.envelope = modified
        elif fault == "wrong-id":
            fix.envelope["id"] = "0" * 64
        else:
            assert app.run(fix.directory, fix.settings("apply", ORGANIZE_STOP="journal:0")).returncode == 75
            if fault == "journal":
                fix.journal.write_text("{truncated")
            else:
                journal = json.loads(fix.journal.read_bytes())
                journal["receipt"]["step" if fault == "step" else "complete"] = 3 if fault == "step" else True
                journal["checksum"] = checksum(journal["receipt"])
                fix.journal.write_text(json.dumps(journal))
        rejection(app, fix, "apply")
        assert (fix.root / "a.txt").exists() and (fix.root / "b.txt").exists()
        count += 1
    exact = fixture(directory, "exact-budget")
    total = sum(path.stat().st_size for path in exact.root.iterdir())
    exact.config.update(max_entries=3, max_files=2, max_bytes=total)
    exact.save()
    preview(app, exact)
    for field, limit in [("max_entries", 2), ("max_files", 1), ("max_bytes", total - 1)]:
        before = exact.config[field]
        exact.config[field] = limit
        exact.save()
        previous = exact.plan.read_bytes()
        rejection(app, exact)
        assert exact.plan.read_bytes() == previous
        exact.config[field] = before
        count += 1
    exact.save()
    apply(app, exact)
    return count


def check_filesystem_failures(app: Application, directory: Path) -> int:
    for index, operation in enumerate(["read", "preview", "journal", "mkdir", "move"]):
        fix = fixture(directory, f"permission-{index}")
        if operation == "move":
            (fix.root / "documents/2024/02").mkdir(parents=True)
        if operation not in {"read", "preview"}:
            preview(app, fix)
        selected = {
            "read": fix.root / "a.txt",
            "preview": fix.directory,
            "journal": fix.directory,
            "mkdir": fix.root,
            "move": fix.root / "documents/2024/02",
        }[operation]
        mode = stat.S_IMODE(selected.stat().st_mode)
        selected.chmod(0 if operation == "read" else 0o500)
        try:
            rejection(app, fix, "preview" if operation in {"read", "preview"} else "apply")
            assert (fix.root / "a.txt").exists() and (fix.root / "b.txt").exists()
        finally:
            selected.chmod(mode)
        if operation in {"read", "preview"}:
            preview(app, fix)
        apply(app, fix)
    return 5


def check_large(app: Application, directory: Path) -> None:
    fix = fixture(directory, "large")
    for index in range(997):
        write(fix.root / f"small-{index:04}.txt", f"record {index}\n".encode())
    large = fix.root / "large.bin"
    block = bytes(range(256)) * 256
    with large.open("wb") as stream:
        for _ in range(2560):
            stream.write(block)
        stream.write(b"x" * 43)
    os.utime(large, ns=(1709164800000000123, 1709164800000000123))
    assert large.stat().st_size == 167772203
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    preview(limited, fix)
    assert len(fix.envelope["plan"]["rows"]) == 1000
    apply(limited, fix)
    # The retained plan/checksums suffice as evidence; release the large disposable fixture.
    (fix.root / "other/2024/02/large.bin").unlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    check_basics(app, directory)
    interruptions = check_interruptions(app, directory)
    conflicts = check_conflicts(app, directory)
    rejected = check_invalid(app, directory)
    failures = check_filesystem_failures(app, directory)
    check_large(app, directory)
    return {
        "collision_oracle": True,
        "preview_matches_execution": True,
        "source_inodes_preserved": True,
        "interruption_boundaries": interruptions,
        "killed_processes": 3,
        "conflict_cases": conflicts,
        "invalid_requests": rejected,
        "filesystem_failures": failures,
        "large_files": 1000,
        "large_blob_bytes": 167772203,
        "address_space_bytes": 134217728,
    }
