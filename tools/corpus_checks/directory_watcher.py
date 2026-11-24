"""Independent filesystem/event model and real restart, cancellation and publication checks."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
from __future__ import annotations

import copy
import hashlib
import json
import os
import queue
import random
import resource
import shutil
import stat
import subprocess
import threading
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

from .common import Application


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: normalize(item) for key, item in value.items() if key not in ["device", "inode", "mtime_ns", "binding"]
        }
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


def snapshot(root: Path) -> dict:
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(parent, name)
            info = path.lstat()
            kind = "directory" if stat.S_ISDIR(info.st_mode) else "symlink" if stat.S_ISLNK(info.st_mode) else "file"
            assert kind != "file" or stat.S_ISREG(info.st_mode)
            result[path.relative_to(root).as_posix()] = {
                "kind": kind,
                "device": info.st_dev,
                "inode": info.st_ino,
                "mode": stat.S_IMODE(info.st_mode),
                "links": info.st_nlink if kind == "file" else 0,
                "size": info.st_size if kind == "file" else 0,
                "mtime_ns": 0 if kind == "directory" else info.st_mtime_ns,
                "digest": digest(path.read_bytes()) if kind == "file" else "",
                "target": os.readlink(path) if kind == "symlink" else "",
            }
    return result


def identity(entry: dict) -> tuple:
    return entry["device"], entry["inode"], entry["kind"]


def delta(before: dict, after: dict) -> list[tuple[str, str, str, dict | None, dict | None]]:
    left = Counter(identity(item) for item in before.values())
    right = Counter(identity(item) for item in after.values())
    destinations = {identity(item): path for path, item in after.items() if right[identity(item)] == 1}
    moves = []
    for old_path, entry in before.items():
        token = identity(entry)
        if left[token] == right[token] == 1:
            new_path = destinations[token]
            if new_path != old_path and (entry["kind"] != "file" or entry["links"] == after[new_path]["links"] == 1):
                moves.append((old_path, new_path))
    sources, targets = {a for a, _ in moves}, {b for _, b in moves}
    result = [
        ("deleted", path, "", before[path], None)
        for path in sorted(set(before) - sources)
        if path not in after or path in targets
    ]
    result += [("renamed", b, a, before[a], after[b]) for a, b in sorted(moves)]
    for path in sorted(set(after) - targets):
        if path not in before or path in sources:
            result.append(("created", path, "", None, after[path]))
        elif before[path] != after[path]:
            result.append(("modified", path, "", before[path], after[path]))
    return result


@dataclass
class Pending:
    kind: str
    path: str
    before: dict | None
    after: dict
    first: int
    last: int

    def row(self) -> dict:
        return {
            "id": 0,
            "kind": self.kind,
            "path": self.path,
            "previous_path": "",
            "before": self.before,
            "after": self.after,
            "first_ms": self.first,
            "last_ms": self.last,
            "emitted_ms": 0,
        }


@dataclass
class Model:
    delay: int
    retain: int
    clock: int = 0
    next_id: int = 1
    seen: dict = field(default_factory=dict)
    pending: dict[str, Pending] = field(default_factory=dict)
    journal: deque = field(default_factory=deque)

    def deliver(self, row: dict) -> None:
        self.journal.append(dict(row, id=self.next_id, emitted_ms=self.clock))
        self.next_id += 1
        while len(self.journal) > self.retain:
            self.journal.popleft()
        return

    def flush(self, path: str) -> None:
        if path in self.pending:
            self.deliver(self.pending.pop(path).row())
        return

    def step(self, current: dict, observed: int) -> None:
        self.clock = max(self.clock, observed)
        for path in sorted(self.pending):
            if self.clock - self.pending[path].last >= self.delay:
                self.flush(path)
        changes = delta(self.seen, current)
        for kind, path, previous, _before, _after in changes:
            if kind in ["deleted", "renamed"]:
                self.flush(path)
                self.flush(previous)
        for kind, path, previous, before, after in changes:
            if kind in ["deleted", "renamed"]:
                self.deliver(
                    {
                        "id": 0,
                        "kind": kind,
                        "path": path,
                        "previous_path": previous,
                        "before": before,
                        "after": after,
                        "first_ms": self.clock,
                        "last_ms": self.clock,
                        "emitted_ms": 0,
                    }
                )
            else:
                original = self.pending.get(path)
                self.pending[path] = Pending(
                    original.kind if original else kind,
                    path,
                    original.before if original else before,
                    after,
                    original.first if original else self.clock,
                    self.clock,
                )
        for path in sorted(self.pending):
            if self.clock - self.pending[path].last >= self.delay:
                self.flush(path)
        self.seen = copy.deepcopy(current)
        return


@dataclass
class Fixture:
    work: Path
    config: dict
    model: Model

    @property
    def tree(self) -> Path:
        return self.work / self.config["root"]

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def settings(self, now: int | None = None, **extra: str) -> dict:
        result = {"WATCH_CONFIG": str(self.work / "job.json")}
        if now is not None:
            result["WATCH_NOW_MS"] = str(now)
        result.update(extra)
        return result

    def write(self) -> None:
        (self.work / "job.json").write_text(canonical(self.config))
        return

    def binding(self) -> dict:
        root = self.tree.resolve()
        info = root.stat()
        return {
            "root": str(root),
            "identity": f"{info.st_dev}:{info.st_ino}:directory",
            "debounce_ms": self.config["debounce_ms"],
            "retain": self.config["retain"],
        }

    def expected(self) -> dict:
        return {
            "version": 1,
            "binding": self.binding(),
            "clock_ms": self.model.clock,
            "next_id": self.model.next_id,
            "snapshot": self.model.seen,
            "pending": {path: item.row() for path, item in self.model.pending.items()},
            "journal": list(self.model.journal),
        }


def fixture(work: Path, delay: int = 100, retain: int = 256) -> Fixture:
    work.mkdir(parents=True)
    (work / "tree").mkdir()
    value = {"version": 1, "root": "tree", "output": "state", "debounce_ms": delay, "retain": retain}
    result = Fixture(work, value, Model(delay, retain))
    result.write()
    return result


def write(fix: Fixture, path: str, data: bytes, tick: int = 0) -> None:
    target = fix.tree / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(0o644)
    os.utime(target, ns=(1700000000000000000 + tick, 1700000000000000000 + tick))
    return


def report(state: dict) -> dict:
    return {
        "clock_ms": state["clock_ms"],
        "observed_entries": len(state["snapshot"]),
        "pending": len(state["pending"]),
        "first_id": state["next_id"] - len(state["journal"]),
        "next_id": state["next_id"],
        "events": state["journal"],
    }


def verify(fix: Fixture) -> dict:
    raw = (fix.output / "state.json").read_bytes()
    envelope = json.loads(raw)
    expected = fix.expected()
    assert envelope == {"value": expected, "sha256": digest(canonical(expected).encode())}, (envelope, expected)
    assert raw == (canonical(envelope) + "\n").encode()
    assert not (fix.output / "control.tmp").exists()
    return expected


def poll(app: Application, fix: Fixture, now: int) -> dict:
    current = snapshot(fix.tree)
    result = app.run(fix.work, fix.settings(now))
    assert result.returncode == 0, (result.stdout, result.stderr)
    fix.model.step(current, now)
    state = verify(fix)
    assert json.loads(result.stdout) == report(state)
    return state


def trace(state: dict) -> list[tuple]:
    return [
        (
            item["id"],
            item["kind"],
            item["previous_path"],
            item["path"],
            item["first_ms"],
            item["last_ms"],
            item["emitted_ms"],
        )
        for item in state["journal"]
    ]


def semantics(app: Application, root: Path) -> dict:
    fix = fixture(root / "debounce")
    hashes = []
    poll(app, fix, 0)
    for now, data in [(10, b"draft"), (40, b"first")]:
        write(fix, "note.txt", data, now)
        state = poll(app, fix, now)
        assert len(state["pending"]) == 1 and not state["journal"]
    assert not poll(app, fix, 139)["journal"]
    assert trace(poll(app, fix, 140)) == [(1, "created", "", "note.txt", 10, 40, 140)]
    write(fix, "note.txt", b"other", 150)
    poll(app, fix, 150)
    saved = (fix.tree / "note.txt").stat().st_mtime_ns
    write(fix, "note.txt", b"later", 180)
    os.utime(fix.tree / "note.txt", ns=(saved, saved))
    poll(app, fix, 180)
    (fix.tree / "note.txt").rename(fix.tree / "saved.txt")
    state = poll(app, fix, 200)
    assert trace(state)[1:] == [
        (2, "modified", "", "note.txt", 150, 180, 200),
        (3, "renamed", "note.txt", "saved.txt", 200, 200, 200),
    ]
    assert state["journal"][1]["before"]["digest"] == digest(b"first") and state["journal"][1]["after"][
        "digest"
    ] == digest(b"later")
    write(fix, "saved.txt", b"deleted soon", 210)
    poll(app, fix, 210)
    (fix.tree / "saved.txt").unlink()
    state = poll(app, fix, 215)
    assert [row["kind"] for row in state["journal"][-2:]] == ["modified", "deleted"]
    write(fix, "brief.txt", b"visible between polls", 220)
    poll(app, fix, 220)
    (fix.tree / "brief.txt").unlink()
    state = poll(app, fix, 221)
    assert [row["kind"] for row in state["journal"][-2:]] == ["created", "deleted"]
    assert poll(app, fix, 100)["clock_ms"] == 221
    write(fix, "resume.txt", b"pending across restart", 222)
    poll(app, fix, 222)
    assert poll(app, fix, 321)["pending"]
    state = poll(app, fix, 322)
    assert state["next_id"] == 9 and trace(state)[-1] == (8, "created", "", "resume.txt", 222, 222, 322)
    hashes.append(digest(canonical(normalize(state)).encode()))
    # At the exact quiet-window boundary, finish the prior event before observing a new edit.
    write(fix, "resume.txt", b"one", 400)
    poll(app, fix, 400)
    write(fix, "resume.txt", b"two", 500)
    state = poll(app, fix, 500)
    assert trace(state)[-1] == (9, "modified", "", "resume.txt", 400, 400, 500)
    assert state["pending"]["resume.txt"]["first_ms"] == 500
    poll(app, fix, 600)
    # Metadata-only changes remain observable, even when the content hash is equal.
    (fix.tree / "resume.txt").chmod(0o600)
    poll(app, fix, 610)
    state = poll(app, fix, 710)
    assert state["journal"][-1]["before"]["mode"] == 0o644 and state["journal"][-1]["after"]["mode"] == 0o600
    hashes.append(digest(canonical(normalize(state)).encode()))
    return {
        "observations": 21,
        "emitted_events": state["next_id"] - 1,
        "same_size_restored_mtime_edit_detected": True,
        "exact_quiet_boundary": True,
        "rollback_clamped": True,
        "trace_sha256": digest(canonical(hashes).encode()),
    }


def renames(app: Application, root: Path) -> dict:
    fix = fixture(root / "moves")
    for path in ["a", "b", "c", "folder/child"]:
        write(fix, path, path.encode(), 0)
    poll(app, fix, 0)
    # Moving into an occupied destination preserves the overwritten file's deletion.
    os.replace(fix.tree / "a", fix.tree / "b")
    state = poll(app, fix, 10)
    assert [(e["kind"], e["previous_path"], e["path"]) for e in state["journal"]] == [
        ("created", "", "b"),
        ("created", "", "a"),
        ("deleted", "", "b"),
        ("renamed", "a", "b"),
    ]
    # Swap names through a temporary name between polls: both identities are retained.
    (fix.tree / "b").rename(fix.tree / "swap")
    (fix.tree / "c").rename(fix.tree / "b")
    (fix.tree / "swap").rename(fix.tree / "c")
    state = poll(app, fix, 20)
    assert [(e["previous_path"], e["path"]) for e in state["journal"] if e["kind"] == "renamed"][-2:] == [
        ("b", "c"),
        ("c", "b"),
    ]
    # A move and content edit in one observation is a rename with both images.
    (fix.tree / "b").rename(fix.tree / "renamed")
    write(fix, "renamed", b"changed while moving", 30)
    state = poll(app, fix, 30)
    assert state["journal"][-1]["kind"] == "renamed"
    assert state["journal"][-1]["before"]["digest"] != state["journal"][-1]["after"]["digest"]
    (fix.tree / "folder").rename(fix.tree / "moved")
    state = poll(app, fix, 40)
    assert [(e["previous_path"], e["path"]) for e in state["journal"] if e["kind"] == "renamed"][-2:] == [
        ("folder", "moved"),
        ("folder/child", "moved/child"),
    ]
    # Ambiguous hardlink identities are represented as a deletion and creation.
    write(fix, "hard-one", b"hardlinked", 50)
    os.link(fix.tree / "hard-one", fix.tree / "hard-two")
    poll(app, fix, 50)
    (fix.tree / "hard-one").rename(fix.tree / "hard-new")
    state = poll(app, fix, 60)
    assert not any(e["kind"] == "renamed" and e["path"] == "hard-new" for e in state["journal"])
    assert any(e["kind"] == "deleted" and e["path"] == "hard-one" for e in state["journal"])
    (fix.tree / "cycle").symlink_to(".", target_is_directory=True)
    (fix.tree / "dangling").symlink_to("missing")
    poll(app, fix, 70)
    (fix.tree / "dangling").rename(fix.tree / "link-renamed")
    state = poll(app, fix, 80)
    assert state["journal"][-1]["kind"] == "renamed" and state["journal"][-1]["after"]["kind"] == "symlink"
    state = poll(app, fix, 180)
    assert not any(path.startswith("cycle/") for path in state["snapshot"])
    # Replacing an occupant at the same path is a debounced modification.
    replacement = fix.work / "replacement"
    replacement.write_bytes(b"new inode")
    os.replace(replacement, fix.tree / "renamed")
    poll(app, fix, 190)
    state = poll(app, fix, 290)
    assert state["journal"][-1]["kind"] == "modified"
    assert identity(state["journal"][-1]["before"]) != identity(state["journal"][-1]["after"])
    return {
        "observations": 12,
        "overwritten_destination_preserved": True,
        "rename_cycles": True,
        "rename_and_edit": True,
        "hardlink_ambiguity_preserved": True,
        "symlinks_not_followed": True,
        "trace_sha256": digest(canonical(normalize(state)).encode()),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(8701)
    fix = fixture(root, delay=75, retain=17)
    hashes = []
    known: set[str] = set()
    now = 0
    for index in range(160):
        now += rng.choice([0, 1, 25, 74, 75, 100])
        path = "item-" + str(rng.randrange(12)) + "-世界.txt"
        if path in known and rng.randrange(3) == 0:
            (fix.tree / path).unlink()
            known.remove(path)
        elif path in known and rng.randrange(3) == 0:
            target = "item-" + str(rng.randrange(12)) + "-世界.txt"
            if target != path:
                os.replace(fix.tree / path, fix.tree / target)
                known.remove(path)
                known.add(target)
        else:
            write(fix, path, rng.randbytes(rng.randrange(50)), index)
            known.add(path)
        state = poll(app, fix, now)
        hashes.append(digest(canonical(normalize(state)).encode()))
    state = poll(app, fix, now + 75)
    assert not state["pending"] and len(state["journal"]) == 17 and state["next_id"] > 100
    return {
        "observations": 161,
        "retained": 17,
        "total_events": state["next_id"] - 1,
        "trace_sha256": digest(canonical(hashes).encode()),
    }


def rejected(app: Application, fix: Fixture, now: int = 0, diagnostic: str = "", **settings: str) -> None:
    state = (fix.output / "state.json").read_bytes() if (fix.output / "state.json").is_file() else None
    source = (
        {
            path.relative_to(fix.tree).as_posix(): path.read_bytes()
            for path in fix.tree.rglob("*")
            if not path.is_symlink() and path.is_file()
        }
        if fix.tree.is_dir()
        else {}
    )
    result = app.run(fix.work, fix.settings(now, **settings))
    assert result.returncode == 2 and diagnostic in result.stderr, (result.returncode, result.stdout, result.stderr)
    if state is not None:
        assert (fix.output / "state.json").read_bytes() == state
    assert all((fix.tree / name).read_bytes() == data for name, data in source.items())
    return


def invalid(app: Application, root: Path) -> dict:
    mutations = [
        lambda c: c.update(version=2),
        lambda c: c.update(version=True),
        lambda c: c.update(extra=0),
        lambda c: c.update(debounce_ms=-1),
        lambda c: c.update(debounce_ms=60001),
        lambda c: c.update(debounce_ms=1.0),
        lambda c: c.update(retain=0),
        lambda c: c.update(retain=257),
        lambda c: c.update(retain=False),
        lambda c: c.update(root="missing"),
        lambda c: c.update(root="job.json"),
        lambda c: c.update(root=""),
        lambda c: c.update(output="tree/state"),
        lambda c: c.update(output="tree"),
        lambda c: c.update(output="."),
        lambda c: c.update(output="job.json"),
        lambda c: c.update(output=""),
        lambda c: c.pop("retain"),
    ]
    for index, mutate in enumerate(mutations):
        fix = fixture(root / f"config-{index}")
        mutate(fix.config)
        fix.write()
        rejected(app, fix)
    values = [b"{", b"null", b"[]", b"{}", b"\xff", b'{"version":NaN}']
    for index, data in enumerate(values):
        fix = fixture(root / f"raw-{index}")
        (fix.work / "job.json").write_bytes(data)
        rejected(app, fix)
    settings = [
        {"WATCH_POLLS": "-1"},
        {"WATCH_POLLS": "100001"},
        {"WATCH_POLLS": "true"},
        {"WATCH_INTERVAL_MS": "9"},
        {"WATCH_INTERVAL_MS": "60001"},
        {"WATCH_INTERVAL_MS": "1.5"},
        {"WATCH_NOW_MS": "-1"},
        {"WATCH_NOW_MS": "9000000000000001"},
        {"WATCH_NOW_MS": "false"},
        {"WATCH_POLLS": "0"},
        {"WATCH_STOP": "tree/stop"},
        {"WATCH_STOP": "state/stop"},
    ]
    for index, values in enumerate(settings):
        fix = fixture(root / f"setting-{index}")
        rejected(app, fix, **values)
    malformed = [
        lambda s: s.update(version=2),
        lambda s: s.update(extra=0),
        lambda s: s.update(clock_ms=-1),
        lambda s: s.update(clock_ms=9000000000000001),
        lambda s: s.update(next_id=0),
        lambda s: s.update(next_id=s["next_id"] + 1),
        lambda s: s["binding"].update(debounce_ms=1),
        lambda s: s["binding"].update(identity="wrong"),
        lambda s: s["snapshot"]["a"].update(kind="fifo"),
        lambda s: s["snapshot"]["a"].update(mode=4096),
        lambda s: s["snapshot"]["a"].update(size=1048577),
        lambda s: s["snapshot"]["a"].update(device=-1),
        lambda s: s["snapshot"]["a"].update(digest="bad"),
        lambda s: s["snapshot"]["a"].update(links=0),
        lambda s: s["snapshot"]["a"].update(target="not a link"),
        lambda s: s["snapshot"].update({"../escape": s["snapshot"]["a"]}),
        lambda s: s["snapshot"].update({"missing/child": s["snapshot"]["a"]}),
        lambda s: s["pending"]["b"].update(path="a"),
        lambda s: s["pending"]["b"].update(kind="renamed"),
        lambda s: s["pending"]["b"].update(emitted_ms=1),
        lambda s: s["pending"]["b"].update(id=1),
        lambda s: s["pending"]["b"].update(after=s["snapshot"]["a"]),
        lambda s: s["pending"]["b"].update(first_ms=999),
        lambda s: s["pending"]["b"].update(last_ms=999),
        lambda s: s["journal"][0].update(id=99),
        lambda s: s["journal"][0].update(kind="unknown"),
        lambda s: s["journal"][0].update(previous_path="a"),
        lambda s: s["journal"][0].update(before={}),
        lambda s: s["journal"][0].update(after=None),
        lambda s: s["journal"][0].update(emitted_ms=-1),
    ]
    for index, mutate in enumerate(malformed):
        fix = fixture(root / f"state-{index}")
        write(fix, "a", b"a")
        poll(app, fix, 0)
        poll(app, fix, 100)
        write(fix, "b", b"b")
        poll(app, fix, 110)
        state = json.loads((fix.output / "state.json").read_bytes())["value"]
        mutate(state)
        (fix.output / "state.json").write_text(canonical({"value": state, "sha256": digest(canonical(state).encode())}))
        rejected(app, fix, 120)
    fix = fixture(root / "checksum")
    poll(app, fix, 0)
    value = json.loads((fix.output / "state.json").read_bytes())
    value["sha256"] = "0" * 64
    (fix.output / "state.json").write_text(canonical(value))
    rejected(app, fix, diagnostic="checksum mismatch")
    return {"configurations": len(mutations) + 6, "settings": len(settings), "corrupt_states": len(malformed) + 1}


class Limited(Application):
    def run(self, directory: Path, settings: dict[str, str], timeout: int = 30) -> subprocess.CompletedProcess:
        def limited() -> None:
            resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
            return

        return subprocess.run(
            self.command,
            cwd=directory,
            env=self.environment(settings),
            capture_output=True,
            text=True,
            timeout=timeout,
            preexec_fn=limited,
            check=False,
        )


def capacity(app: Application, root: Path) -> dict:
    limited = Limited(app.command, app.engine)
    fix = fixture(root / "full", delay=0, retain=256)
    long_path = "/".join(["d" * 63] * 15 + ["f" * 64])
    assert len(long_path.encode()) == 1024
    write(fix, long_path, b"")
    for index in range(240):
        write(fix, f"file-{index:03}", b"x" * 1048576 if index < 4 else b"", index)
    state = poll(limited, fix, 0)
    assert len(state["snapshot"]) == len(state["journal"]) == 256 and state["next_id"] == 257
    write(fix, "file-000", b"y" * 1048576, 1)
    state = poll(limited, fix, 1)
    assert state["next_id"] == 258 and report(state)["first_id"] == 2
    write(fix, "too-many", b"")
    rejected(app, fix, 2, "256")
    (fix.tree / "too-many").unlink()
    write(fix, "file-000", b"x" * 1048577)
    rejected(app, fix, 2, "1 MiB")
    write(fix, "file-000", b"x" * 1048576)
    write(fix, "file-004", b"x")
    rejected(app, fix, 2, "4 MiB")
    hashes = [digest(canonical(normalize(state)).encode())]
    for name, limit in [("job.json", 65536), ("state/state.json", 2097152)]:
        other = fixture(root / name.replace("/", "-"))
        poll(app, other, 0)
        path = other.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (limit - len(raw)))
        poll(limited, other, 1)
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (limit + 1 - len(raw)))
        rejected(app, other, 2, "byte limit")
    for name, path in [("path", long_path + "x"), ("depth", "/".join(["d"] * 17))]:
        other = fixture(root / name)
        write(other, path, b"")
        rejected(app, other, diagnostic="relative path")
    link = fixture(root / "link", delay=60000, retain=1)
    (link.tree / "link").symlink_to("x" * 1024)
    poll(limited, link, 0)
    assert poll(limited, link, 59999)["pending"]
    assert len(poll(limited, link, 60000)["journal"]) == 1
    (link.tree / "link").unlink()
    (link.tree / "link").symlink_to("x" * 1025)
    rejected(app, link, 60001, "1024 bytes")
    fifo = fixture(root / "fifo")
    os.mkfifo(fifo.tree / "pipe")
    rejected(app, fifo, diagnostic="unsupported filesystem")
    return {
        "entries": 256,
        "retained_events": 256,
        "individual_bytes": 1048576,
        "scan_bytes": 4194304,
        "path_bytes": 1024,
        "depth": 16,
        "symlink_target_bytes": 1024,
        "memory_limit": 268435456,
        "control_limits": {"config": 65536, "state": 2097152},
        "trace_sha256": digest(canonical(hashes).encode()),
    }


def paused(app: Application, fix: Fixture, label: str, now: int) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(now, WATCH_PAUSE=label, WATCH_RELEASE=str(fix.work / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
            if line.strip() == "PAUSED " + label:
                return
        lines.put(None)
        return

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=10)
            assert line is not None, "exited before checkpoint"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, root: Path) -> dict:
    count = 0
    for checkpoint in ["scanned", "staged", "committed"]:
        for killed in [False, True]:
            fix = fixture(root / f"{checkpoint}-{killed}", delay=0)
            poll(app, fix, 0)
            old = (fix.output / "state.json").read_bytes()
            write(fix, "note", b"change", 10)
            if killed:
                process = paused(app, fix, checkpoint, 10)
                process.kill()
                process.communicate(timeout=5)
            else:
                result = app.run(fix.work, fix.settings(10, WATCH_FAULT=checkpoint))
                assert result.returncode == 2
            if checkpoint == "committed":
                fix.model.step(snapshot(fix.tree), 10)
                verify(fix)
            else:
                assert (fix.output / "state.json").read_bytes() == old
            state = poll(app, fix, 11)
            assert state["next_id"] == 2 and len(state["journal"]) == 1
            count += 1
    # Changing a source after its bytes were read causes a fresh bounded scan.
    fix = fixture(root / "scan-retry", delay=0)
    write(fix, "note", b"before")
    process = paused(app, fix, "scanned", 10)
    write(fix, "note", b"after", 1)
    (fix.work / "release").write_text("resume")
    output, _ = process.communicate(timeout=10)
    assert process.returncode == 0, output
    fix.model.step(snapshot(fix.tree), 10)
    state = verify(fix)
    assert state["snapshot"]["note"]["digest"] == digest(b"after")
    count += 1
    # A post-scan edit belongs to the next poll, not to a partially rewritten checkpoint.
    fix = fixture(root / "next-poll", delay=0)
    write(fix, "note", b"before")
    captured = snapshot(fix.tree)
    process = paused(app, fix, "staged", 10)
    write(fix, "note", b"after", 1)
    (fix.work / "release").write_text("resume")
    output, _ = process.communicate(timeout=10)
    assert process.returncode == 0, output
    fix.model.step(captured, 10)
    verify(fix)
    state = poll(app, fix, 11)
    assert [item["kind"] for item in state["journal"]] == ["created", "modified"]
    count += 1
    fix = fixture(root / "exclusive", delay=0)
    write(fix, "note", b"locked")
    process = paused(app, fix, "staged", 0)
    temporary = (fix.output / "control.tmp").read_bytes()
    try:
        for _ in range(8):
            rejected(app, fix)
            assert (fix.output / "control.tmp").read_bytes() == temporary
        (fix.work / "release").write_text("resume")
        output, _ = process.communicate(timeout=10)
        assert process.returncode == 0, output
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
    fix.model.step(snapshot(fix.tree), 0)
    assert verify(fix)["next_id"] == 2
    return {"interruption_and_scan_checks": count, "competing_processes_rejected": 8, "one_durable_event": True}


def paths(app: Application, root: Path) -> int:
    count = 0
    for name in ["job.json", "state/state.json", "state/control.tmp", "state.lock"]:
        for kind in ["symlink", "hardlink"]:
            fix = fixture(root / (name.replace("/", "-") + "-" + kind))
            poll(app, fix, 0)
            path = fix.work / name
            if not path.exists():
                path.write_text("temporary")
            original = fix.work / "original"
            path.rename(original)
            if kind == "symlink":
                path.symlink_to(original)
            else:
                os.link(original, path)
            rejected(app, fix, 1)
            count += 1
    for kind in ["output-link", "output-file", "unknown-file", "root-replaced", "changed-settings"]:
        fix = fixture(root / kind)
        poll(app, fix, 0)
        if kind == "output-link":
            fix.output.rename(fix.work / "original-state")
            fix.output.symlink_to(fix.work / "original-state", target_is_directory=True)
        elif kind == "output-file":
            shutil.rmtree(fix.output)
            fix.output.write_text("preserved")
        elif kind == "unknown-file":
            (fix.output / "unowned").write_text("preserved")
        elif kind == "root-replaced":
            fix.tree.rename(fix.work / "original-tree")
            fix.tree.mkdir()
        else:
            fix.config["retain"] = 1
            fix.write()
        rejected(app, fix, 1)
        count += 1
    if os.getuid() != 0:
        for path in ["tree", "state"]:
            fix = fixture(root / ("permissions-" + path))
            poll(app, fix, 0)
            write(fix, "note", b"permission check")
            target = fix.work / path
            target.chmod(0 if path == "tree" else 0o500)
            try:
                rejected(app, fix, 1)
            finally:
                target.chmod(0o700)
            count += 1
    return count


def continuous(app: Application, root: Path) -> dict:
    fix = fixture(root, delay=500)
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(WATCH_POLLS="0", WATCH_INTERVAL_MS="20", WATCH_STOP=str(fix.work / "stop"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        first = json.loads(lines.get(timeout=10))
        assert not first["events"]
        write(fix, "live", b"first", 1)
        while True:
            current = json.loads(lines.get(timeout=10))
            if current["pending"]:
                break
        write(fix, "live", b"second", 2)
        while True:
            current = json.loads(lines.get(timeout=10))
            if current["events"]:
                break
        assert len(current["events"]) == 1 and current["events"][0]["after"]["digest"] == digest(b"second")
        assert current["events"][0]["emitted_ms"] - current["events"][0]["last_ms"] >= 500
        write(fix, "pending", b"survives cancellation", 3)
        while True:
            current = json.loads(lines.get(timeout=10))
            if current["pending"]:
                break
        (fix.work / "stop").write_text("stop")
        process.wait(timeout=5)
        thread.join(timeout=5)
        assert process.returncode == 0 and not thread.is_alive(), process.stderr.read()
        saved = json.loads((fix.output / "state.json").read_bytes())["value"]
        assert "pending" in saved["pending"] and saved["next_id"] == 2
        (fix.work / "stop").unlink()
        resumed = app.run(fix.work, fix.settings(saved["clock_ms"] + 500))
        assert resumed.returncode == 0, resumed.stderr
        result = json.loads(resumed.stdout)
        assert result["pending"] == 0 and result["next_id"] == 3
        assert result["events"][-1]["path"] == "pending"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        thread.join(timeout=5)
        process.stdout.close()
        process.stderr.close()
    return {
        "continuous_polling": True,
        "debounced_live_edit": True,
        "cancellation_preserves_pending": True,
        "restart_delivers_once": True,
    }


def cancellation_bounds(app: Application, root: Path) -> dict:
    fix = fixture(root / "long-wait", delay=60000)
    write(fix, "pending", b"stop without waiting one minute")
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(
            fix.settings(WATCH_POLLS="0", WATCH_INTERVAL_MS="60000", WATCH_STOP=str(fix.work / "stop"))
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready: queue.Queue = queue.Queue()

    def first_line() -> None:
        ready.put(process.stdout.readline())
        return

    thread = threading.Thread(target=first_line, daemon=True)
    thread.start()
    try:
        value = json.loads(ready.get(timeout=10))
        thread.join(timeout=1)
        assert value["pending"] == 1 and value["next_id"] == 1
        (fix.work / "stop").write_text("stop")
        output, error = process.communicate(timeout=2)
        assert process.returncode == 0 and not output, (output, error)
        saved = json.loads((fix.output / "state.json").read_bytes())["value"]
        assert list(saved["pending"]) == ["pending"] and not saved["journal"]
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        thread.join(timeout=5)
    stopped = fixture(root / "maximum-polls")
    (stopped.work / "stop").write_text("already cancelled")
    result = app.run(
        stopped.work,
        stopped.settings(WATCH_POLLS="100000", WATCH_INTERVAL_MS="60000", WATCH_STOP=str(stopped.work / "stop")),
    )
    assert result.returncode == 0 and not result.stdout, result.stderr
    assert not (stopped.output / "state.json").exists()
    return {"cancellation_during_60_second_wait": True, "maximum_poll_count_accepted": 100000}


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "renames": renames(app, directory / "renames"),
        "generated": generated(app, directory / "generated"),
        "invalid": invalid(app, directory / "invalid"),
        "capacity": capacity(app, directory / "capacity"),
        "publication": publication(app, directory / "publication"),
        "path_checks": paths(app, directory / "paths"),
        "continuous": continuous(app, directory / "continuous"),
        "cancellation_bounds": cancellation_bounds(app, directory / "cancellation-bounds"),
        "independent_snapshot_and_event_model": True,
    }
