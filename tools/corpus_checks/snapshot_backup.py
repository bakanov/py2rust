"""Independent filesystem oracle, persistence, corruption and crash acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import selectors
import stat
import subprocess
from pathlib import Path

from .common import Application


def tree(root: Path) -> dict:
    result = {}
    links: dict[tuple[int, int], list[str]] = {}
    pending = [root]
    while pending:
        path = pending.pop()
        metadata = path.lstat()
        name = str(path.relative_to(root))
        common = (stat.S_IMODE(metadata.st_mode) & 0o777, metadata.st_mtime_ns)
        if path.is_symlink():
            result[name] = ("symlink", *common, os.readlink(path))
        elif path.is_dir():
            result[name] = ("directory", *common)
            pending.extend(path.iterdir())
        else:
            assert path.is_file()
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
            result[name] = ("file", *common, metadata.st_size, digest.hexdigest())
            links.setdefault((metadata.st_dev, metadata.st_ino), []).append(name)
    for names in links.values():
        for name in names:
            result[name] = (*result[name][:-1], tuple(sorted(names)), result[name][-1])
    return result


def fixture(directory: Path) -> tuple[Path, Path, dict]:
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "source"
    repo = directory / "store"
    source.mkdir()
    repo.mkdir()
    (source / "empty-dir").mkdir()
    (source / "nested").mkdir()
    (source / "nested/世界.bin").write_bytes(b"\x00\xff\xfeCRLF\r\n" * 8001)
    (source / "text").write_text("bold **words** and _italics_ 😀\r\n", newline="")
    (source / "empty").touch()
    (source / "duplicate").write_bytes((source / "text").read_bytes())
    (source / "hard-link").hardlink_to(source / "text")
    (source / "link").symlink_to("nested/世界.bin")
    (source / "dangling").symlink_to("does-not-exist")
    (source / "cycle").symlink_to(".")
    for index, path in enumerate(sorted([source, *source.rglob("*")])):
        if not path.is_symlink():
            path.chmod(0o750 if path.is_dir() else 0o640)
        os.utime(path, ns=(1700000000000000000 + index, 1700000000123456700 + index), follow_symlinks=False)
    config = {"repository": str(repo), "source": str(source), "keep": 3, "max_entries": 10000, "max_bytes": 1073741824}
    (directory / "backup.json").write_text(json.dumps(config))
    return source, repo, config


def invoke(app: Application, directory: Path, mode: str, version: str = "", **extra: str) -> dict | list:
    result = app.run(directory, dict(BACKUP_MODE=mode, BACKUP_VERSION=version, **extra), timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def fail(app: Application, directory: Path, mode: str, version: str = "", **extra: str) -> None:
    result = app.run(directory, dict(BACKUP_MODE=mode, BACKUP_VERSION=version, **extra), timeout=20)
    assert result.returncode != 0, result.stdout
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def objects(repo: Path) -> dict:
    return {
        path.name: (path.stat().st_ino, path.stat().st_mtime_ns, path.read_bytes())
        for path in (repo / "objects").iterdir()
    }


def paused(app: Application, directory: Path, mode: str, version: str, label: str, action, **extra: str) -> None:
    signal = directory / "continue"
    signal.unlink(missing_ok=True)
    process = subprocess.Popen(
        app.command,
        cwd=directory,
        env=app.environment(
            dict(BACKUP_MODE=mode, BACKUP_VERSION=version, BACKUP_PAUSE=label, BACKUP_CONTINUE=str(signal), **extra)
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(10), "pause was never reached"
            assert process.stdout.readline().strip() == "PAUSED " + label
        action(process, signal)
        stdout, stderr = process.communicate(timeout=20)
        assert process.returncode != 0, stdout + stderr
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def kill(process, signal: Path) -> None:
    process.kill()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def acceptance(app: Application, directory: Path) -> dict:
    source, repo, config = fixture(directory / "versions")
    work = source.parent
    baseline = tree(source)
    invoke(app, work, "init")
    first = invoke(app, work, "snapshot", "first")
    expected_hashes = {value[-1] for value in baseline.values() if value[0] == "file"}
    assert first == {"name": "first", "sequence": 1, "entries": len(baseline), "objects_copied": len(expected_hashes)}
    stored = objects(repo)
    assert set(stored) == expected_hashes
    assert tree(source) == baseline
    assert invoke(app, work, "snapshot", "unchanged")["objects_copied"] == 0
    assert objects(repo) == stored, "unchanged data was rewritten"
    assert tree(source) == baseline
    restored = work / "restored-first"
    invoke(app, work, "restore", "first", BACKUP_DEST=str(restored))
    assert tree(restored) == baseline
    fail(app, work, "restore", "first", BACKUP_DEST=str(restored))
    assert tree(restored) == baseline
    fail(app, work, "snapshot", "first")
    # Same size and restored mtime still requires hashing the actual contents.
    before = (source / "text").stat()
    (source / "text").write_bytes(b"Z" * before.st_size)
    os.utime(source / "text", ns=(before.st_atime_ns, before.st_mtime_ns))
    (source / "nested/世界.bin").unlink()
    (source / "empty-dir/new").write_bytes(b"new version")
    changed = tree(source)
    assert invoke(app, work, "snapshot", "changed")["objects_copied"] == 2
    invoke(app, work, "restore", "changed", BACKUP_DEST=str(work / "restored-changed"))
    assert tree(work / "restored-changed") == changed
    for hashed, old in stored.items():
        assert objects(repo)[hashed] == old
    # Metadata-only changes reuse the object; the selected historical version remains exact.
    (source / "duplicate").chmod(0o400)
    os.utime(source / "duplicate", ns=(9, 1700000000999999999))
    (source / "empty-dir").chmod(0o500)
    final_tree = tree(source)
    assert invoke(app, work, "snapshot", "metadata")["objects_copied"] == 0
    assert [item["name"] for item in invoke(app, work, "list")] == ["unchanged", "changed", "metadata"]
    invoke(app, work, "restore", "unchanged", BACKUP_DEST=str(work / "restored-old"))
    assert tree(work / "restored-old") == baseline
    invoke(app, work, "restore", "metadata", BACKUP_DEST=str(work / "restored-metadata"))
    assert tree(work / "restored-metadata") == final_tree
    config["keep"] = 1
    (work / "backup.json").write_text(json.dumps(config))
    invoke(app, work, "snapshot", "only")
    retained_hashes = {value[-1] for value in final_tree.values() if value[0] == "file"}
    assert set(objects(repo)) == retained_hashes
    assert invoke(app, work, "list") == [{"name": "only", "sequence": 5}]
    fail(app, work, "restore", "first", BACKUP_DEST=str(work / "missing-version"))
    assert not (work / "missing-version").exists()

    boundaries = ["scanned", "copied", "object", "manifest", "published", "retained", "collected"]
    for label in boundaries:
        crash_source, crash_repo, _config = fixture(directory / ("fail-" + label))
        current = crash_source.parent
        expected = tree(crash_source)
        invoke(app, current, "init")
        fail(app, current, "snapshot", "interrupted", BACKUP_FAIL=label)
        listing = invoke(app, current, "list")
        committed = label in {"published", "retained", "collected"}
        assert listing == ([{"name": "interrupted", "sequence": 1}] if committed else [])
        assert list((crash_repo / "staging").iterdir()) == []
        if not committed:
            invoke(app, current, "snapshot", "interrupted")
        invoke(app, current, "restore", "interrupted", BACKUP_DEST=str(current / "restored"))
        assert tree(current / "restored") == expected

    # SIGKILL while data or a manifest is staged; restart owns cleanup under its lock.
    for label in ["copied", "manifest", "published"]:
        killed_source, killed_repo, _config = fixture(directory / ("kill-" + label))
        current = killed_source.parent
        invoke(app, current, "init")
        paused(app, current, "snapshot", "killed", label, kill)
        listing = invoke(app, current, "list")
        assert bool(listing) == (label == "published")
        invoke(app, current, "snapshot", "recovered")
        invoke(app, current, "restore", "recovered", BACKUP_DEST=str(current / "restored"))
        assert tree(current / "restored") == tree(killed_source)
        assert list((killed_repo / "staging").iterdir()) == []

    # Lock contention and changes to the source during a snapshot.
    for change in ["content", "directory", "symlink"]:
        changed_source, _repo, _config = fixture(directory / ("race-" + change))
        current = changed_source.parent
        invoke(app, current, "init")

        def mutate(process, signal: Path, current=current, change=change, changed_source=changed_source) -> None:
            fail(app, current, "snapshot", "competitor")
            if change == "content":
                original = (changed_source / "text").stat()
                (changed_source / "text").write_bytes(b"R" * original.st_size)
                os.utime(changed_source / "text", ns=(original.st_atime_ns, original.st_mtime_ns))
            elif change == "directory":
                (changed_source / "new-entry").write_text("new")
            else:
                (changed_source / "link").unlink()
                (changed_source / "link").symlink_to("changed-target")
            signal.touch()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        paused(app, current, "snapshot", "racing", "scanned", mutate)
        assert invoke(app, current, "list") == []

    # A failed restore never exposes its target, including process death at publication.
    for label in ["restore-entry", "restore-ready"]:
        target = work / label
        fail(app, work, "restore", "only", BACKUP_DEST=str(target), BACKUP_FAIL=label)
        assert not target.exists() and (work / ("." + label + ".backup-incomplete")).is_dir()
        fail(app, work, "restore", "only", BACKUP_DEST=str(target))
    paused(app, work, "restore", "only", "restore-ready", kill, BACKUP_DEST=str(work / "killed-restore"))
    assert not (work / "killed-restore").exists()

    # Object corruption: checksum and size are checked, and data cannot follow a symlink.
    object_path = next((repo / "objects").iterdir())
    original_object = object_path.read_bytes()
    for corruption in ["bytes", "size", "symlink", "missing"]:
        if corruption == "bytes":
            object_path.write_bytes(bytes(byte ^ 1 for byte in original_object) if original_object else b"x")
        elif corruption == "size":
            object_path.write_bytes(original_object + b"x")
        elif corruption == "symlink":
            object_path.unlink()
            object_path.symlink_to(source / "text")
        else:
            object_path.unlink()
        target = work / ("corrupt-" + corruption)
        fail(app, work, "restore", "only", BACKUP_DEST=str(target))
        assert not target.exists()
        if object_path.is_symlink() or object_path.exists():
            object_path.unlink()
        object_path.write_bytes(original_object)

    manifest = repo / "versions/only.json"
    original_manifest = manifest.read_bytes()
    envelope = json.loads(original_manifest)
    mutations = []
    bad = copy.deepcopy(envelope)
    bad["id"] = "0" * 64
    mutations.append(bad)
    for field, value in [
        ("path", "../escape"),
        ("path", "/absolute"),
        ("path", "a//b"),
        ("mode", 4095),
        ("kind", "fifo"),
        ("mtime_ns", True),
    ]:
        bad = copy.deepcopy(envelope)
        bad["snapshot"]["entries"][1][field] = value
        bad["id"] = hashlib.sha256(
            json.dumps(bad["snapshot"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        mutations.append(bad)
    for bad in mutations:
        manifest.write_text(json.dumps(bad))
        fail(app, work, "list")
        fail(app, work, "snapshot", "unsafe")
        assert not (repo / "versions/unsafe.json").exists()
    manifest.write_bytes(original_manifest)

    invalid_source, invalid_repo, valid_config = fixture(directory / "invalid")
    current = invalid_source.parent
    invoke(app, current, "init")
    invalid_count = 0
    for key, values in {
        "keep": [0, -1, 1001, True, "3"],
        "max_entries": [0, 10001, True],
        "max_bytes": [0, 1099511627777, True],
        "source": [str(invalid_repo), str(current)],
    }.items():
        for value in values:
            bad = dict(valid_config, **{key: value})
            (current / "backup.json").write_text(json.dumps(bad))
            fail(app, current, "snapshot", "bad")
            invalid_count += 1
    for key, value in [("max_entries", 1), ("max_bytes", 1)]:
        (current / "backup.json").write_text(json.dumps(dict(valid_config, **{key: value})))
        fail(app, current, "snapshot", "budget")
        invalid_count += 1
    (current / "backup.json").write_text(json.dumps(valid_config))
    for name in ["", "../escape", "with space", "a" * 65, "世界"]:
        fail(app, current, "snapshot", name)
        invalid_count += 1
    os.mkfifo(invalid_source / "pipe")
    fail(app, current, "snapshot", "special")
    (invalid_source / "pipe").unlink()
    (invalid_source / "unreadable").write_bytes(b"protected")
    (invalid_source / "unreadable").chmod(0)
    fail(app, current, "snapshot", "unreadable")
    (invalid_source / "unreadable").chmod(0o600)
    assert invoke(app, current, "list") == []

    # Retention interruption may leave extra data, but never deletes a live version's objects.
    retention_source, retention_repo, retention_config = fixture(directory / "retention-crash")
    current = retention_source.parent
    retention_config["keep"] = 1
    (current / "backup.json").write_text(json.dumps(retention_config))
    invoke(app, current, "init")
    invoke(app, current, "snapshot", "old")
    (retention_source / "nested/世界.bin").write_bytes(b"replacement object")
    retained_tree = tree(retention_source)
    fail(app, current, "snapshot", "new", BACKUP_FAIL="retained")
    assert invoke(app, current, "list") == [{"name": "new", "sequence": 2}]
    invoke(app, current, "restore", "new", BACKUP_DEST=str(current / "restored"))
    assert tree(current / "restored") == retained_tree
    invoke(app, current, "snapshot", "after-gc")
    assert set(objects(retention_repo)) == {value[-1] for value in retained_tree.values() if value[0] == "file"}

    # Actual filesystem write failures, as distinct from injected application exceptions.
    for blocked in ["staging", "objects", "versions"]:
        io_source, io_repo, _config = fixture(directory / ("io-" + blocked))
        current = io_source.parent
        invoke(app, current, "init")
        invoke(app, current, "snapshot", "before")
        (io_source / "additional").write_bytes(b"must be durably copied")
        before_versions = {p.name: p.read_bytes() for p in (io_repo / "versions").iterdir()}
        (io_repo / blocked).chmod(0o500)
        try:
            fail(app, current, "snapshot", "denied")
        finally:
            (io_repo / blocked).chmod(0o700)
        assert {p.name: p.read_bytes() for p in (io_repo / "versions").iterdir()} == before_versions
        invoke(app, current, "snapshot", "recovered")
        invoke(app, current, "restore", "recovered", BACKUP_DEST=str(current / "restored"))
        assert tree(current / "restored") == tree(io_source)

    # Restore budgets are checked before a staging directory is created.
    for key in ["max_entries", "max_bytes"]:
        (work / "backup.json").write_text(json.dumps(dict(config, **{key: 1})))
        fail(app, work, "restore", "only", BACKUP_DEST=str(work / "too-large"))
        assert not (work / ".too-large.backup-incomplete").exists()
    (work / "backup.json").write_text(json.dumps(config))

    # One file larger than the process address-space budget proves streaming copy and restore.
    large_source, large_repo, _large_config = fixture(directory / "large")
    current = large_source.parent
    large = large_source / "large.bin"
    size = 160 * 1024 * 1024 + 17
    with large.open("wb") as stream:
        stream.write(b"header")
        stream.seek(size - 4)
        stream.write(b"tail")
    invoke(app, current, "init")
    limited = Application(["/usr/bin/prlimit", "--as=134217728", "--", *app.command], app.engine)
    invoke(limited, current, "snapshot", "large")
    stored_large = next(path for path in (large_repo / "objects").iterdir() if path.stat().st_size == size)
    identity = stored_large.stat().st_ino
    assert invoke(limited, current, "snapshot", "large-again")["objects_copied"] == 0
    assert stored_large.stat().st_ino == identity
    invoke(limited, current, "restore", "large", BACKUP_DEST=str(current / "restored"))
    assert tree(current / "restored") == tree(large_source)
    # Keep evidence, but release the large physical copies after comparing both complete trees.
    stored_large.unlink()
    (current / "restored/large.bin").unlink()
    large.unlink()
    return {
        "versioned_restore": "files, Unicode, binary, links, empty directories, permissions and nanosecond mtime",
        "incremental": "same-size changes detected; unchanged objects retain bytes, inode and mtime",
        "retention": "newest versions and reachable objects only",
        "failure_boundaries": len(boundaries),
        "killed_snapshots": 3,
        "changed_source_cases": 3,
        "interrupted_restores": 3,
        "corrupt_objects": 4,
        "invalid_manifests": len(mutations),
        "invalid_requests": invalid_count,
        "retention_after_interruption": "restorable before and after orphan collection",
        "filesystem_write_failures": 3,
        "restore_budget_checks": 2,
        "large_file_bytes": size,
        "address_space_bytes": 134217728,
    }


def check(app: Application, directory: Path) -> dict:
    try:
        return acceptance(app, directory)
    finally:
        # The oracle has checked restored permissions, including read-only parents.
        # Permit the corpus runner to remove its disposable fixtures on the next run.
        for root, _directories, _files in os.walk(directory, followlinks=False):
            os.chmod(root, stat.S_IMODE(os.stat(root).st_mode) | 0o700)
