"""Independent filesystem, approval, collision and interrupted-journal oracles."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import selectors
import stat
import subprocess
from pathlib import Path

from .common import Application


def snapshot(root: Path) -> dict:
    result = {}
    for parent, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            if name == ".py2rust-rename.lock":
                continue
            path = Path(parent) / name
            info = path.lstat()
            payload = "directory"
            if stat.S_ISREG(info.st_mode):
                payload = hashlib.sha512(path.read_bytes()).hexdigest()
            elif stat.S_ISLNK(info.st_mode):
                payload = os.readlink(path)
            result[path.relative_to(root).as_posix()] = (
                info.st_ino,
                stat.S_IMODE(info.st_mode),
                stat.S_IFMT(info.st_mode),
                payload,
            )
    return result


def settings(work: Path, mode: str, identifier: str = "", **extra: str) -> dict:
    return {
        "RENAME_CONFIG": str(work / "rename.json"),
        "RENAME_PLAN": str(work / "plan.json"),
        "RENAME_JOURNAL": str(work / "journal.json"),
        "RENAME_MODE": mode,
        "RENAME_APPROVE": identifier,
        "RENAME_STOP": "",
        "RENAME_PAUSE": "",
        **extra,
    }


def invoke(app: Application, work: Path, mode: str, identifier: str = "", **extra: str) -> dict:
    result = app.run(work, settings(work, mode, identifier, **extra), timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def rejected(app: Application, work: Path, mode: str, identifier: str = "", **extra: str) -> str:
    before = snapshot(work / "tree")
    sidecars = {name: (work / name).read_bytes() for name in ["plan.json", "journal.json"] if (work / name).is_file()}
    result = app.run(work, settings(work, mode, identifier, **extra))
    assert result.returncode != 0, result.stdout
    assert snapshot(work / "tree") == before, result.stderr
    for name, content in sidecars.items():
        assert (work / name).read_bytes() == content, name
    return result.stderr


def fixture(work: Path, complex_tree: bool = False) -> tuple[dict, dict]:
    root = work / "tree"
    root.mkdir(parents=True)
    files = {"a": b"first\x00", "b": b"second\xff", "old-世界.txt": "Hello 😀\r\n".encode()}
    paths = list(files)
    if complex_tree:
        files.update(
            {"left/old-data.bin": bytes(range(256)), "old-folder/child": b"in directory", "keep": b"unchanged"}
        )
        paths.extend(["left/old-data.bin", "old-folder", "old-link", "keep", "old-hard"])
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o640)
        os.utime(path, ns=(1555555555000000000, 1666666666123456789))
    if complex_tree:
        (root / "right").mkdir()
        (root / "old-link").symlink_to("no target")
        (root / "old-hard").hardlink_to(root / "a")
    raw = {
        "root": str(root),
        "paths": paths,
        "rules": [{"pattern": "^old-", "replace": "new-"}],
        "overrides": {"a": "b", "b": "a"},
    }
    if complex_tree:
        raw["overrides"]["left/old-data.bin"] = "right/moved.bin"
    (work / "rename.json").write_text(json.dumps(raw))
    return raw, snapshot(root)


def approval(app: Application, work: Path) -> dict:
    envelope = invoke(app, work, "preview")
    assert json.loads((work / "plan.json").read_text()) == envelope
    payload = json.dumps(envelope["plan"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(payload).hexdigest() == envelope["id"]
    for row in envelope["plan"]["rows"]:
        path = work / "tree" / row["source"]
        if path.is_file() and not path.is_symlink():
            assert row["signature"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert not (work / "journal.json").exists()
    return envelope


def renamed(original: dict, rows: list[dict]) -> dict:
    expected = {}
    for name, value in original.items():
        target = name
        for row in rows:
            source = row["source"]
            if name == source or name.startswith(source + "/"):
                target = row["target"] + name[len(source) :]
                break
        expected[target] = value
    return expected


def check_round_trip(app: Application, work: Path) -> None:
    raw, original = fixture(work, True)
    envelope = approval(app, work)
    assert snapshot(work / "tree") == original
    assert approval(app, work) == envelope
    identifier = envelope["id"]
    rejected(app, work, "apply")
    rejected(app, work, "apply", "incorrect approval")
    rejected(app, work, "reverse", identifier)
    applied = invoke(app, work, "apply", identifier)
    assert applied == {"id": identifier, "action": "applied", "moves": len(raw["paths"]) - 1}
    assert snapshot(work / "tree") == renamed(original, envelope["plan"]["rows"])
    assert invoke(app, work, "apply", identifier) == applied
    rejected(app, work, "preview")
    result = invoke(app, work, "reverse", identifier)
    assert result == {**applied, "action": "reversed"}
    assert snapshot(work / "tree") == original
    assert invoke(app, work, "reverse", identifier) == result
    rejected(app, work, "apply", identifier)
    receipt = json.loads((work / "journal.json").read_text())["receipt"]
    assert receipt["complete"] and receipt["reverse"] and receipt["step"] == 2 * applied["moves"]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_interruptions(app: Application, work: Path) -> int:
    boundaries = ["journal:0"]
    boundaries += [f"{label}:{step}" for step in range(6) for label in ["before", "renamed", "synced"]]
    boundaries += [f"saved:{step}" for step in range(1, 7)]
    for reverse in [False, True]:
        for index, boundary in enumerate(boundaries):
            case = work / f"{reverse}-{index}"
            raw, original = fixture(case)
            envelope = approval(app, case)
            identifier = envelope["id"]
            expected = renamed(original, envelope["plan"]["rows"])
            if reverse:
                invoke(app, case, "apply", identifier)
            mode = "reverse" if reverse else "apply"
            stopped = app.run(case, settings(case, mode, identifier, RENAME_STOP=boundary))
            assert stopped.returncode == 75 and "INTERRUPTED" in stopped.stdout, stopped.stderr
            if not reverse:
                rejected(app, case, "reverse", identifier)
            result = invoke(app, case, mode, identifier)
            assert result["moves"] == len(raw["paths"])
            assert snapshot(case / "tree") == (original if reverse else expected)
            if not reverse:
                invoke(app, case, "reverse", identifier)
            assert snapshot(case / "tree") == original
    return 2 * len(boundaries)


def check_conflicts(app: Application, work: Path) -> int:
    cases = [
        "existing",
        "dangling",
        "directory",
        "duplicate",
        "noop",
        "changed",
        "replaced",
        "permissions",
        "parent",
        "stage",
        "journal",
        "plan",
        "approval",
        "reverse-change",
        "staged-intruder",
        "late-file",
        "late-link",
        "late-directory",
        "reverse-collision",
    ]
    for name in cases:
        case = work / name
        raw, original = fixture(case)
        root = case / "tree"
        if name in ["existing", "dangling", "directory"]:
            target = root / "new-世界.txt"
            if name == "existing":
                target.write_bytes(b"keep existing")
            elif name == "dangling":
                target.symlink_to("missing")
            else:
                target.mkdir()
            rejected(app, case, "preview")
            assert not (case / "plan.json").exists()
            continue
        if name in ["duplicate", "noop"]:
            raw["overrides"] = {"a": "same", "b": "same"} if name == "duplicate" else {"a": "b"}
            (case / "rename.json").write_text(json.dumps(raw))
            rejected(app, case, "preview")
            continue
        envelope = approval(app, case)
        identifier = envelope["id"]
        mode = "apply"
        if name.startswith("late-"):
            target = root / "new-世界.txt"
            if name == "late-file":
                target.write_bytes(b"appeared after preview")
            elif name == "late-link":
                target.symlink_to("missing")
            else:
                target.mkdir()
        elif name == "reverse-collision":
            invoke(app, case, "apply", identifier)
            (root / "old-世界.txt").write_bytes(b"appeared after apply")
            mode = "reverse"
        elif name == "changed":
            info = (root / "a").stat()
            (root / "a").write_bytes(b"other\x00")
            os.utime(root / "a", ns=(info.st_atime_ns, info.st_mtime_ns))
        elif name == "replaced":
            # Keep the old inode alive so the filesystem cannot recycle its number.
            (root / "a").rename(root / "previous")
            (root / "a").write_bytes(b"first\x00")
            (root / "a").chmod(0o640)
            os.utime(root / "a", ns=(0, 1666666666123456789))
        elif name == "permissions":
            (root / "a").chmod(0o600)
        elif name == "parent":
            root.rename(case / "old-tree")
            root.mkdir()
            for path in (case / "old-tree").iterdir():
                path.rename(root / path.name)
        elif name == "stage":
            (root / f".py2rust-rename-{identifier}-0").write_bytes(b"foreign staging entry")
        elif name == "journal":
            (case / "journal.json").write_text('{"corrupt":true}')
        elif name == "plan":
            envelope["plan"]["rows"][0]["target"] = "unreviewed"
            (case / "plan.json").write_text(json.dumps(envelope))
        elif name == "approval":
            identifier = "0" * 64
        elif name == "reverse-change":
            invoke(app, case, "apply", identifier)
            (root / "b").write_bytes(b"subsequent changes")
            mode = "reverse"
        elif name == "staged-intruder":
            stopped = app.run(case, settings(case, "apply", identifier, RENAME_STOP="renamed:2"))
            assert stopped.returncode == 75, stopped.stderr
            (root / "b").write_bytes(b"new occupant")
        rejected(app, case, mode, identifier)
        if name == "staged-intruder":
            (root / "b").unlink()
            invoke(app, case, "apply", identifier)
            invoke(app, case, "reverse", identifier)
            assert snapshot(root) == original
    return len(cases)


def check_configuration(app: Application, work: Path) -> int:
    invalid = [
        {"unknown": 1},
        {"paths": []},
        {"paths": ["a", "a"]},
        {"paths": [1]},
        {"paths": ["missing"]},
        {"paths": ["/absolute"]},
        {"paths": ["../outside"]},
        {"paths": ["."]},
        {"paths": [""]},
        {"paths": ["a/"]},
        {"paths": ["a//b"]},
        {"paths": ["a/../b"]},
        {"paths": ["nul\x00"]},
        {"paths": [".py2rust-rename.lock"]},
        {"paths": ["pipe"]},
        {"paths": ["link/child"]},
        {"paths": ["nested", "nested/child"]},
        {"paths": ["a"] * 129},
        {"overrides": {"a": "../escape"}},
        {"overrides": {"a": "/absolute"}},
        {"overrides": {"unknown": "b"}},
        {"overrides": {"a": "missing-parent/b"}},
        {"overrides": {"a": "link/other"}},
        {"overrides": {"a": "z" * 256}},
        {"overrides": {"a": ".py2rust-rename-foreign"}},
        {"rules": [{"pattern": "[", "replace": "x"}]},
        {"rules": [{"pattern": "^", "replace": "x"}]},
        {"rules": [{"pattern": "a", "replace": "x", "unknown": 1}]},
        {"rules": [{"pattern": "a", "replace": 1}]},
        {"rules": [{"pattern": "a", "replace": "x"}] * 33},
        {"max_bytes": -1},
        {"max_bytes": 67108865},
        {"max_bytes": True},
        {"max_bytes": 1},
        {"root": "missing"},
        {"root": "/"},
    ]
    for index, changes in enumerate(invalid):
        case = work / str(index)
        raw, _original = fixture(case)
        root = case / "tree"
        (root / "nested").mkdir()
        (root / "nested/child").write_bytes(b"child")
        (root / "link").symlink_to("nested", target_is_directory=True)
        os.mkfifo(root / "pipe")
        raw.update(changes)
        (case / "rename.json").write_text(json.dumps(raw))
        rejected(app, case, "preview")
        assert not (case / "plan.json").exists()
    return len(invalid)


def check_paths_and_locks(app: Application, work: Path) -> int:
    _raw, original = fixture(work)
    root = work / "tree"
    count = 0
    for extra in [
        {"RENAME_PLAN": str(root / "inside.json")},
        {"RENAME_JOURNAL": str(root / "inside.json")},
        {"RENAME_PLAN": str(work / "rename.json")},
        {"RENAME_JOURNAL": str(work / "rename.json")},
        {"RENAME_JOURNAL": str(work / "plan.json")},
    ]:
        rejected(app, work, "preview", **extra)
        count += 1
    for kind in ["symlink", "hardlink", "directory", "fifo"]:
        sidecar = work / "plan.json"
        if kind == "symlink":
            sidecar.symlink_to(work / "rename.json")
        elif kind == "hardlink":
            sidecar.hardlink_to(work / "rename.json")
        elif kind == "directory":
            sidecar.mkdir()
        else:
            os.mkfifo(sidecar)
        rejected(app, work, "preview")
        if kind == "directory":
            sidecar.rmdir()
        else:
            sidecar.unlink()
        count += 1
    lock_path = root / ".py2rust-rename.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rejected(app, work, "preview")
    envelope = approval(app, work)
    with lock_path.open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Root-wide lock serializes writers even with a different journal path.
        rejected(app, work, "apply", envelope["id"], RENAME_JOURNAL=str(work / "other-journal.json"))
    assert not (work / "other-journal.json").exists()
    invoke(app, work, "apply", envelope["id"])
    invoke(app, work, "reverse", envelope["id"])
    assert snapshot(root) == original
    return count + 2


def check_killed_process(app: Application, work: Path) -> None:
    _raw, original = fixture(work)
    envelope = approval(app, work)
    identifier = envelope["id"]
    command_env = settings(work, "apply", identifier, RENAME_PAUSE="renamed:3")
    child = subprocess.Popen(
        app.command,
        cwd=work,
        env=app.environment(command_env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=10), "rename did not pause"
            line = child.stdout.readline()
            assert line.startswith("PAUSED renamed 3"), line + child.stderr.read()
        assert child.poll() is None
        child.kill()
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=5)
    receipt = json.loads((work / "journal.json").read_text())["receipt"]
    assert receipt["step"] == 3 and not receipt["complete"]
    invoke(app, work, "apply", identifier)
    assert snapshot(work / "tree") == renamed(original, envelope["plan"]["rows"])
    invoke(app, work, "reverse", identifier)
    assert snapshot(work / "tree") == original
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_real_io_failures(app: Application, work: Path) -> None:
    assert os.geteuid() != 0, "permission failures require an unprivileged user"
    for kind in ["publish", "journal"]:
        case = work / kind
        _raw, original = fixture(case, True)
        envelope = approval(app, case)
        identifier = envelope["id"]
        protected = case / "tree/right" if kind == "publish" else case
        if kind == "journal":
            stopped = app.run(case, settings(case, "apply", identifier, RENAME_STOP="journal:0"))
            assert stopped.returncode == 75, stopped.stderr
        original_mode = stat.S_IMODE(protected.stat().st_mode)
        protected.chmod(0o555)
        try:
            failed = app.run(case, settings(case, "apply", identifier))
            assert failed.returncode != 0, failed.stdout
            assert snapshot(case / "tree") != original
            receipt = json.loads((case / "journal.json").read_text())["receipt"]
            assert not receipt["complete"]
            assert receipt["step"] == (0 if kind == "journal" else 10)
        finally:
            protected.chmod(original_mode)
        invoke(app, case, "apply", identifier)
        invoke(app, case, "reverse", identifier)
        assert snapshot(case / "tree") == original
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check_noop_and_directory_scope(app: Application, work: Path) -> None:
    raw, original = fixture(work)
    raw.update(rules=[], overrides={})
    (work / "rename.json").write_text(json.dumps(raw))
    envelope = approval(app, work)
    assert invoke(app, work, "apply", envelope["id"])["moves"] == 0
    assert invoke(app, work, "reverse", envelope["id"])["moves"] == 0
    assert snapshot(work / "tree") == original
    case = work / "directory-scope"
    root = case / "tree"
    root.mkdir(parents=True)
    (root / "old-directory").mkdir()
    (root / "old-directory/child").write_text("before")
    raw = {"root": str(root), "paths": ["old-directory"], "overrides": {"old-directory": "new-directory"}}
    (case / "rename.json").write_text(json.dumps(raw))
    envelope = approval(app, case)
    invoke(app, case, "apply", envelope["id"])
    # Directory renames guard the directory entry, not a recursive content snapshot.
    (root / "new-directory/child").write_text("edited child survives reverse")
    invoke(app, case, "reverse", envelope["id"])
    assert (root / "old-directory/child").read_text() == "edited child survives reverse"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    check_round_trip(app, directory / "round-trip")
    interruptions = check_interruptions(app, directory / "interruptions")
    conflicts = check_conflicts(app, directory / "conflicts")
    configuration = check_configuration(app, directory / "configuration")
    path_checks = check_paths_and_locks(app, directory / "paths")
    check_killed_process(app, directory / "killed")
    check_real_io_failures(app, directory / "io-errors")
    check_noop_and_directory_scope(app, directory / "noop")
    return {
        "round_trip": "files, Unicode, directories, symlinks, hard links, swaps, relocation and no-op",
        "interruption_boundaries": interruptions,
        "conflicts": conflicts,
        "invalid_configurations": configuration,
        "sidecar_and_lock_checks": path_checks,
        "process_termination": "recovered after rename before journal",
        "io_errors": "resumed after denied publication and denied journal update",
        "directory_scope": "child edits preserved; directory entry guarded",
    }
