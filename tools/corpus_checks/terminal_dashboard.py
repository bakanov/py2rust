"""Real PTY refresh/resize/cancellation, snapshot recovery and portable native terminal transcripts."""

from __future__ import annotations

import itertools
import json
import os
import random
import select
import signal
import struct
import subprocess
import termios
import time
from pathlib import Path

from .common import Application
from .terminal_fixture import (
    canonical,
    digest,
    files_at,
    inspect,
    lines,
    observe,
    save,
    snapshot,
    task,
    width,
)


def fixture(
    root: Path, source: dict | bytes | None = None, columns: int = 80, refreshes: int = 2, interval: int = 20
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "mode": "watch",
        "input": "tasks.json",
        "output": "output",
        "columns": columns,
        "refreshes": refreshes,
        "interval_ms": interval,
    }
    save(root / "tasks-job.json", config)
    (root / "tasks.json").write_bytes(
        source if isinstance(source, bytes) else canonical(snapshot() if source is None else source)
    )
    return config


def run(app: Application, root: Path, config: dict, selected: str = "tasks-job.json") -> dict:
    preserved = {
        root / name: (root / name).read_bytes() for name in [selected, config["input"]] if (root / name).is_file()
    }
    result = app.run(root, {"TASK_DASHBOARD_CONFIG": str(root / selected)}, timeout=180)
    assert result.returncode in [0, 1] and not result.stderr, (root, result)
    directory = root / config["output"]
    archive = inspect(directory)
    errors = json.loads((directory / "report.json").read_bytes())["errors"]
    assert result.returncode == int(bool(errors) and config["mode"] == "watch")
    assert result.stdout.encode() == (directory / "transcript.txt").read_bytes() and "\x1b" not in result.stdout
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr and not (root / "output").exists() and not list(root.glob(".tasks-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: dict, columns: int, stem: str) -> dict:
    before = files_at(root)
    config = json.loads((root / "watch.json").read_bytes())
    config.update(input=stem + "-snapshot.json", output=stem, columns=columns)
    save(root / config["input"], source)
    save(root / (stem + "-job.json"), config)
    result = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in before.items())
    return result


def semantics(app: Application, root: Path) -> dict:
    original = run(app, root, fixture(root))
    assert consume(app, root / "output", "replay.json") == original
    assert consume(app, root / "output", "watch.json") == original
    values = [
        task("zero", "done", 0, 0),
        task("unknown", "running", 0, 0),
        task("last", "running", 999999999, 1000000000),
    ]
    cases = []
    for columns in [1, 2, 7, 23, 24, 49, 50, 80, 120, 200]:
        cases.append((columns, snapshot(values)))
        cases.append((columns, snapshot([])))
    for label in ["é東京", "👩🏽‍💻🇯🇵", "🏳️‍🌈1️⃣", "क्ष", "́leading", "A‍B", "x" * 120, "界" * 120, "é" * 60]:
        for columns in [2, 23, 24, 50, 80]:
            cases.append((columns, snapshot([task("label", label=label)])))
    for index, (columns, value) in enumerate(cases):
        work = root / str(index)
        run(app, work, fixture(work, value, columns, 1))
    work = root / "golden"
    archive = run(app, work, fixture(work, snapshot([task("u", done=1, total=4, label="Upload")], title="Jobs"), 24, 1))
    assert archive["events"][0]["lines"] == [
        "Jobs" + " " * 20,
        "1 tasks | 1 running | 0~",
        "> 25%  Upload" + " " * 11,
        "0 hidden | frame 1/1 | ~",
    ]

    return {
        "static_layout_cases": len(cases),
        "manual_compact_frame": True,
        "unknown_and_zero_total": True,
        "grapheme_safe_clipping": True,
        "exported_watch_and_replay": True,
        "archive_sha256": digest(canonical(original)),
    }


def resize(descriptor: int, columns: int, rows: int) -> None:
    import fcntl

    fcntl.ioctl(descriptor, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    return  # noqa: PLR1711


def read_exact(descriptor: int, count: int) -> bytes:
    chunks = bytearray()
    deadline = time.monotonic() + 15
    while len(chunks) < count:
        assert select.select([descriptor], [], [], max(0.0, deadline - time.monotonic()))[0], bytes(chunks)
        chunk = os.read(descriptor, count - len(chunks))
        assert chunk
        chunks.extend(chunk)
    return bytes(chunks)


def live(
    app: Application, root: Path, plans: list[tuple[bytes | None, int, int]], term: str = "xterm", stop: int = 0
) -> dict:
    count = 64 if stop else len(plans)
    fixture(root, {}, 200, count, 10000 if stop else 500)
    master, slave = os.openpty()
    attributes = termios.tcgetattr(slave)
    attributes[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attributes)
    interactive = term not in ["", "dumb", "unknown"]
    target = root / "tasks.json"

    def install(plan: tuple[bytes | None, int, int]) -> None:
        raw, columns, rows = plan
        resize(slave, columns, rows)
        if raw is None:
            if target.exists():
                target.unlink()
        else:
            temporary = root / "next.json"
            temporary.write_bytes(raw)
            temporary.replace(target)
        return  # noqa: PLR1711

    install(plans[0])
    process = subprocess.Popen(
        app.command,
        cwd=root,
        stdout=slave,
        stderr=subprocess.PIPE,
        env=app.environment({"TERM": term, "COLUMNS": "999", "LINES": "999"}),
    )
    captured = bytearray()
    state = None
    try:
        if interactive:
            opening = b"\x1b[?1049h\x1b[?25l"
            assert read_exact(master, len(opening)) == opening
            captured.extend(opening)
        for index, (raw, columns, rows) in enumerate(plans, 1):
            state, status = observe(state, b"" if raw is None else raw, raw is not None)
            cells = min(200, max(1, (columns or 80) - 1))
            height = min(132, max(1, (rows or 24) - 1)) if interactive else 132
            expected = lines(state, cells, height, index, count, status)
            encoded = (
                ("\x1b[H\x1b[2J" + "\r\n".join(expected)) if interactive else "\n".join(expected) + "\n\n"
            ).encode()
            actual = read_exact(master, len(encoded))
            assert actual == encoded, (index, actual, encoded)
            captured.extend(actual)
            assert len(expected) <= height and all(width(line) <= max(1, (columns or 80) - 1) for line in expected)
            if index < len(plans):
                install(plans[index])
        stopped = time.monotonic()
        if stop:
            process.send_signal(stop)
        if interactive:
            closing = b"\x1b[?25h\x1b[?1049l"
            assert read_exact(master, len(closing)) == closing
            captured.extend(closing)
        _, stderr = process.communicate(timeout=10)
        assert not stderr, stderr
        archive = inspect(root / "output")
        assert len(archive["events"]) == len(plans) and archive["signal"] == stop
        errors = json.loads((root / "output/report.json").read_bytes())["errors"]
        assert process.returncode == (128 + stop if stop else int(bool(errors)))
        if stop:
            assert time.monotonic() - stopped < 2.0
        else:
            assert consume(app, root / "output", "replay.json") == archive
        assert interactive or b"\x1b" not in captured
        (root / "terminal.bin").write_bytes(captured)
        return archive
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
        process.stderr.close()
        os.close(master)
        os.close(slave)


def interactive(app: Application, root: Path) -> dict:
    first = snapshot(sequence=10)
    next_value = snapshot([task("new", done=10, total=10, state="done", label="Complete 👩🏽‍💻 upload")], 11)
    conflicting = dict(next_value, title="conflict")
    plans = [
        (canonical(first), 81, 10),
        (canonical(first), 41, 7),
        (canonical(next_value), 25, 5),
        (canonical(conflicting), 13, 4),
        (canonical(first), 2, 3),
        (b'{"broken":', 1, 1),
        (None, 51, 5),
        (canonical(snapshot([], 12, "Recovered")), 201, 8),
    ]
    archive = live(app, root / "changes", plans)
    assert [r["status"] for r in archive["events"]] == [
        "updated",
        "unchanged",
        "updated",
        "conflicting sequence",
        "older sequence",
        "invalid snapshot",
        "unreadable",
        "updated",
    ]
    for i, term in enumerate(["", "dumb", "unknown"]):
        live(app, root / ("plain-" + str(i)), [(canonical(first), 13, 4)], term)
    for number in [signal.SIGINT, signal.SIGTERM]:
        live(app, root / str(number), [(canonical(first), 80, 10)], stop=int(number))
    return {
        "live_frames": 8,
        "resizes": 7,
        "monotonic_sequence_and_recovery": True,
        "plain_terminal_fallbacks": 3,
        "signal_cleanup_cases": 2,
        "terminal_bytes_checked": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(117)
    hashes, total = [], 0
    for i in range(16):
        tasks = []
        for j in range(rng.randint(0, 128)):
            state = rng.choice(["queued", "running", "done", "failed"])
            ceiling = rng.randint(0, 10**9)
            done = ceiling if state == "done" else 0 if state == "queued" else rng.randint(0, ceiling)
            tasks.append(task(str(j), state, done, ceiling, rng.choice(["東京", "évents", "👩🏽‍💻", "task"]) + str(j)))
        work = root / str(i)
        columns = rng.randint(1, 200)
        source = snapshot(tasks, i)
        first = run(app, work, fixture(work, source, columns, 1))
        assert consume(app, work / "output", "replay.json") == first
        changed = snapshot(list(reversed(tasks)), i + 1, "Reordered")
        edited = edit_export(app, work / "output", changed, 201 - columns, "edited")
        assert json.loads((work / "output/edited/snapshot.json").read_bytes()) == changed
        assert consume(app, work / "output/edited", "replay.json") == edited
        restored = edit_export(app, work / "output/edited", source, columns, "restored")
        assert restored == first
        total += len(tasks)
        hashes.append(digest(canonical(first)))
    return {
        "seed": 117,
        "generated_projects": 16,
        "tasks": total,
        "edit_relayout_restore": 16,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    base = root / "base"
    config = fixture(base)
    requests = [{k: v for k, v in config.items() if k != omitted} for omitted in config]
    for key, values in {
        "version": [True, 1.0, 2],
        "mode": [None, "render"],
        "input": [None, "", "a\0b"],
        "output": [None, "", "a\0b", "tasks.json"],
        "columns": [0, 201, True, 1.0, None],
        "refreshes": [0, 65, True, 1.0],
        "interval_ms": [19, 60001, True, 20.0],
        "extra": [1],
    }.items():
        requests.extend(dict(config, **{key: value}) for value in values)
    requests.append(dict(config, refreshes=64, interval_ms=60000))
    for i, changed in enumerate(requests):
        work = root / ("request-" + str(i))
        fixture(work)
        save(work / "tasks-job.json", changed)
        reject(app, work)
    source = snapshot([task("one")])
    sources = []
    for path in [(), ("tasks", 0)]:
        node = source if not path else source["tasks"][0]
        for omitted in [*node, None]:
            changed = json.loads(canonical(source))
            target = changed if not path else changed["tasks"][0]
            if omitted is None:
                target["extra"] = 1
            else:
                del target[omitted]
            sources.append(canonical(changed))
    for path, values in [
        (("version",), [True, 1.0, 2]),
        (("sequence",), [-1, True, 1.0, 2**63]),
        (("title",), [None, "", " ", "x" * 121, "bad\x1b[2J"]),
        (("tasks",), [None, {}, [None], source["tasks"] * 129, source["tasks"] * 2]),
        (("tasks", 0, "id"), [None, "", "x" * 33, "bad\n"]),
        (("tasks", 0, "label"), [None, "", "x" * 121, "bad\u202e", "bad\u2066", "\t"]),
        (("tasks", 0, "state"), [None, "unknown", True]),
        (("tasks", 0, "done"), [-1, 11, True, 1.0]),
        (("tasks", 0, "total"), [-1, 4, 1000000001, True, 10.0]),
    ]:
        for value in values:
            changed = json.loads(canonical(source))
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            sources.append(canonical(changed))
    sources += [
        canonical(snapshot([task("queued", "queued", 1, 2)])),
        canonical(snapshot([task("done", "done", 1, 2)])),
    ]
    malformed = [
        b"{",
        b"[]",
        b"null",
        b'{"version":1,"version":1}',
        b"{}{}",
        b"\xff",
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":"\\ud800"}',
    ]
    sources += malformed
    for i, raw in enumerate(sources):
        work = root / ("source-" + str(i))
        archive = run(app, work, fixture(work, raw, refreshes=1))
        assert archive["events"][0]["status"] == "invalid snapshot"
    for filename in ["tasks-job.json", "archive.json"]:
        for i, raw in enumerate(malformed):
            work = root / (filename + str(i))
            fixture(work)
            if filename == "archive.json":
                save(work / "tasks-job.json", {"version": 1, "mode": "replay", "input": filename, "output": "output"})
            (work / filename).write_bytes(raw)
            reject(app, work)
    archive = run(app, base, config)
    paths = [
        (("version",), True),
        (("version",), 1.0),
        (("signal",), 3),
        (("signal",), True),
        (("settings", "refreshes"), 3),
        (("settings", "columns"), 0),
        (("settings", "interval_ms"), 19),
        (("events",), []),
        (("events", 0, "readable"), 1),
        (("events", 0, "readable"), False),
        (("events", 0, "columns"), 80.0),
        (("events", 0, "rows"), 0),
        (("events", 0, "status"), "unchanged"),
        (("events", 1, "status"), "updated"),
        (("events", 0, "lines", 0), "tampered"),
        (("events", 0, "lines"), []),
        (("events", 0, "source_hex"), archive["events"][0]["source_hex"].upper()),
        (("events", 0, "source_hex"), " " + archive["events"][0]["source_hex"]),
        (("events", 0, "source_hex"), archive["events"][0]["source_hex"][:-1]),
    ]
    altered = []
    for path, value in paths:
        changed = json.loads(canonical(archive))
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        altered.append(changed)
    altered += [{k: v for k, v in archive.items() if k != omitted} for omitted in archive]
    altered.append(dict(archive, extra=1))
    for i, changed in enumerate(altered):
        work = root / ("archive-" + str(i))
        fixture(work)
        save(work / "tasks-job.json", {"version": 1, "mode": "replay", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests": len(requests),
        "invalid_snapshots": len(sources),
        "malformed_json_per_fatal_input": len(malformed),
        "inconsistent_archives": len(altered),
        "invalid_snapshots_retained_as_observations": True,
    }


def limits(app: Application, root: Path) -> dict:
    source = snapshot(
        [task("x" * 29 + str(i), "running", 999999999, 1000000000, "L" * 120) for i in range(128)], 2**63 - 1, "T" * 120
    )
    work = root / "maximum"
    config = fixture(work, source, 200, 64)
    for name, size in [("tasks-job.json", 65536), ("tasks.json", 65536)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size, b" "))
        assert path.stat().st_size == size
    archive = run(app, work, config)
    assert all(len(row["lines"]) == 132 for row in archive["events"])
    assert consume(app, work / "output", "replay.json") == archive
    for name in ["tasks-job.json", "tasks.json"]:
        work = root / ("over-" + name)
        config = fixture(work, refreshes=1)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(65537, b" "))
        if name == "tasks-job.json":
            reject(app, work, "input byte limit")
        else:
            assert run(app, work, config)["events"][0]["status"] == "unreadable"
    small = root / "small"
    original = run(app, small, fixture(small, refreshes=1))
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-exact")
        fixture(work)
        config = {"version": 1, "mode": "replay", "input": "archive.json", "output": "output"}
        save(work / "tasks-job.json", config)
        (work / "archive.json").write_bytes(canonical(original).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            assert run(app, work, config) == original
    work = root / "over-hex"
    fixture(work)
    changed = json.loads(canonical(original))
    changed["events"][0]["source_hex"] = "00" * 65537
    save(work / "tasks-job.json", {"version": 1, "mode": "replay", "input": "archive.json", "output": "output"})
    save(work / "archive.json", changed)
    reject(app, work, "snapshot byte limit")
    return {
        "tasks": 128,
        "refreshes": 64,
        "columns": 200,
        "rows": 132,
        "label_characters": 120,
        "id_characters": 32,
        "maximum_sequence": 2**63 - 1,
        "progress_total": 1000000000,
        "request_and_snapshot_bytes": 65536,
        "archive_bytes": 16777216,
        "maximum_replayed": True,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        fixture(work, refreshes=1)
        result = app.run(work, {"TASK_DASHBOARD_FAULT": stage})
        assert result.returncode == 2 and result.stderr and result.stdout
        assert not list(work.glob(".tasks-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work / "output")
    baseline = root / "baseline"
    original = run(app, baseline, fixture(baseline, refreshes=1))
    for mutation in ["request", "archive", "competitor", "source", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, refreshes=1)
        if mutation == "archive":
            save(work / "archive.json", original)
            config = {"version": 1, "mode": "replay", "input": "archive.json", "output": "output"}
            save(work / "tasks-job.json", config)
        stage = "published" if mutation == "kill-published" else "staged"
        release = work / "release"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=app.environment(
                {"TASK_DASHBOARD_PAUSE": stage, "TASK_DASHBOARD_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}
            ),
        )
        try:
            marker = ("PAUSED " + stage + "\n").encode()
            output = bytearray()
            deadline = time.monotonic() + 15
            while not output.endswith(marker):
                assert select.select([process.stdout], [], [], max(0.0, deadline - time.monotonic()))[0]
                chunk = os.read(process.stdout.fileno(), 65536)
                assert chunk
                output.extend(chunk)
            if mutation.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9 and (work / "output").exists() == (stage == "published")
                assert len(list(work.glob(".tasks-*"))) == int(stage == "staged")
                if stage == "published":
                    inspect(work / "output")
                config["output"] = "retry"
                save(work / "retry.json", config)
                run(app, work, config, "retry.json")
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("keep")
                else:
                    filename = {"request": "tasks-job.json", "archive": "archive.json", "source": "tasks.json"}[
                        mutation
                    ]
                    with (work / filename).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert not stdout and not list(work.glob(".tasks-*"))
                if mutation == "source":
                    assert process.returncode == 0 and not stderr
                    assert inspect(work / "output") == original
                else:
                    assert process.returncode == 2 and stderr
                    if mutation == "competitor":
                        assert (work / "output/keep").read_text() == "keep"
                    else:
                        assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()
    return {
        "caught_faults": 2,
        "hard_kills": 2,
        "guarded_request_archive_output_races": 3,
        "watched_source_can_change_after_snapshot": True,
        "retry_after_hard_kill": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["tasks-job.json", "tasks.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work, refreshes=1)
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
            if name == "tasks-job.json":
                reject(app, work)
            else:
                result = app.run(work, {})
                assert result.returncode == 1 and not result.stderr
                assert inspect(work / "output")["events"][0]["status"] == "unreadable"
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work, refreshes=1)
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "tasks-job.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr
            if kind == "file":
                assert output.read_text() == "keep"
            elif kind == "directory":
                assert not list(output.iterdir())
            elif kind == "symlink":
                assert output.is_symlink()
            else:
                assert not output.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, method in [
        ("semantics", semantics),
        ("interactive", interactive),
        ("generated", generated),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = method(app, directory / name)
        print(app.engine + " terminal dashboard " + name + ": passed", flush=True)
    return observations
