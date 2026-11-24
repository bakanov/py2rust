"""Independent content-signature model, native invocation logs and interrupted-cache recovery checks."""

from __future__ import annotations

import copy
import hashlib
import heapq
import json
import os
import queue
import resource
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .build_fixture import build_fixture
from .common import Application
from .process_fixture import gone, ready


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(data: bytes, mode: int = 0o644) -> dict:
    return {"bytes": len(data), "mode": mode, "sha256": digest(data)}


def entry_signature(entry: dict) -> str:
    return digest(canonical({key: entry[key] for key in ["recipe", "inputs", "dependencies"]}))


def order(rows: list[dict]) -> list[str]:
    by_id = {row["id"]: row for row in rows}
    remaining = {name: len(row["dependencies"]) for name, row in by_id.items()}
    successors = {name: [] for name in by_id}
    for name, row in by_id.items():
        for dependency in row["dependencies"]:
            successors[dependency].append(name)
    pending = [name for name, count in remaining.items() if count == 0]
    heapq.heapify(pending)
    result = []
    while pending:
        name = heapq.heappop(pending)
        result.append(name)
        for child in successors[name]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(pending, child)
    assert len(result) == len(rows)
    return result


def target(name: str, inputs: dict[str, str], dependencies: list[str], helper: str) -> dict:
    return {
        "id": name,
        "inputs": inputs,
        "dependencies": dependencies,
        "output": f"artifacts/{name}.bin",
        "argv": [
            helper,
            name,
            "normal",
            "invocations.txt",
            "{output}",
            "v1",
            *["{input:" + key + "}" for key in sorted(inputs)],
            *["{dependency:" + dep + "}" for dep in dependencies],
        ],
        "environment": {"MARK": "red"},
        "timeout_ms": 2000,
        "max_output": 65536,
    }


@dataclass
class Fixture:
    root: Path
    config: dict

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def source(self) -> Path:
        return self.root / "build.json"

    @property
    def settings(self) -> dict[str, str]:
        return {"BUILD_CONFIG": str(self.source)}

    def save(self) -> None:
        self.source.write_bytes(canonical(self.config))
        return  # noqa: PLR1711 - explicit repository returns


def fixture(root: Path, helper: Path) -> Fixture:
    root.mkdir(parents=True)
    (root / "artifacts").mkdir()
    for name in ["a", "b", "c", "f"]:
        (root / (name + ".txt")).write_bytes((name + "0\n").encode())
        (root / (name + ".txt")).chmod(0o644)
    executable = os.path.relpath(helper, root)
    rows = [
        target("A", {"source": "a.txt"}, [], executable),
        target("B", {"source": "b.txt"}, [], executable),
        target("C", {"source": "c.txt"}, ["A"], executable),
        target("D", {}, ["A", "B"], executable),
        target("E", {}, ["C", "D"], executable),
        target("F", {"source": "f.txt"}, [], executable),
    ]
    result = Fixture(root, {"version": 1, "state": "state", "targets": rows})
    result.save()
    return result


def cache(fix: Fixture) -> dict:
    path = fix.state / "cache.json"
    if not path.exists():
        return {}
    envelope = json.loads(path.read_bytes())
    assert set(envelope) == {"version", "entries", "sha256"} and envelope["version"] == 1
    assert envelope["sha256"] == digest(canonical(envelope["entries"]))
    return envelope["entries"]


def oracle(fix: Fixture) -> tuple[dict, dict[str, bytes], dict[str, str]]:
    old = cache(fix)
    entries, outputs, reasons = {}, {}, {}
    rows = {row["id"]: row for row in fix.config["targets"]}
    for name in order(fix.config["targets"]):
        row = rows[name]
        inputs = {}
        replacements = {}
        for key, relative in row["inputs"].items():
            path = fix.root / relative
            data = path.read_bytes()
            inputs[key] = fingerprint(data, path.stat().st_mode & 0o7777)
            replacements["{input:" + key + "}"] = data
        dependencies = {
            dep: {"signature": entries[dep]["signature"], "output": entries[dep]["output"]}
            for dep in row["dependencies"]
        }
        replacements.update({"{dependency:" + dep + "}": outputs[dep] for dep in row["dependencies"]})
        entry = {"recipe": digest(canonical(row)), "inputs": inputs, "dependencies": dependencies}
        entry["signature"] = entry_signature(entry)
        mode = row["argv"][2]
        assert mode in ["normal", "plain"]
        data = b"" if mode == "plain" else f'[{name}|{row["argv"][5]}|{row["environment"].get("MARK", "")}]'.encode()
        data += b"".join(replacements[token] for token in row["argv"][6:])
        entry["output"] = fingerprint(data)
        path = fix.root / row["output"]
        reason = "cached"
        if name not in old:
            reason = "no_cache"
        else:
            for key in ["recipe", "inputs", "dependencies"]:
                if entry[key] != old[name][key]:
                    reason = "changed_" + key
                    break
            if reason == "cached":
                if not path.exists():
                    reason = "missing_output"
                elif fingerprint(path.read_bytes(), path.stat().st_mode & 0o7777) != old[name]["output"]:
                    reason = "changed_output"
        reasons[name], entries[name], outputs[name] = reason, entry, data
    return entries, outputs, reasons


def invocations(fix: Fixture) -> list[str]:
    path = fix.root / "invocations.txt"
    return path.read_text().splitlines() if path.exists() else []


def run(app: Application, fix: Fixture, rebuilt: set[str] | None = None, **settings: str) -> dict:
    entries, outputs, reasons = oracle(fix)
    expected_order = order(fix.config["targets"])
    expected_calls = [name for name in expected_order if reasons[name] != "cached"]
    if rebuilt is not None:
        assert set(expected_calls) == rebuilt, (expected_calls, rebuilt, reasons)
    (fix.root / "invocations.txt").write_text("")
    result = app.run(fix.root, dict(fix.settings, **settings), timeout=90)
    assert result.returncode == 0 and not result.stderr, (result.returncode, result.stdout, result.stderr)
    assert invocations(fix) == expected_calls
    report = json.loads((fix.state / "report.json").read_bytes())
    assert set(report) == {"version", "summary", "targets", "cache_sha256"} and report["version"] == 1
    assert [row["id"] for row in report["targets"]] == expected_order
    assert report["cache_sha256"] == digest(canonical(entries)) and cache(fix) == entries
    for row in report["targets"]:
        expected_status = "cached" if reasons[row["id"]] == "cached" else "rebuilt"
        assert row["status"] == expected_status and row["reason"] == reasons[row["id"]]
        assert row["error"] == row["stdout_base64"] == row["stderr_base64"] == "" and row["interrupt_signal"] == 0
        assert row["outcome"] == (
            None if expected_status == "cached" else {"kind": "exited", "returncode": 0, "interrupt_signal": 0}
        )
    assert report["summary"] == {
        "cached": len(entries) - len(expected_calls),
        "rebuilt": len(expected_calls),
        "failed": 0,
        "blocked": 0,
    }
    assert [json.loads(line) for line in result.stdout.splitlines()] == report["targets"] + [report["summary"]]
    for row in fix.config["targets"]:
        path = fix.root / row["output"]
        assert path.read_bytes() == outputs[row["id"]] and path.stat().st_mode & 0o7777 == 0o644
    assert {p.name for p in fix.state.iterdir()} == {"cache.json", "report.json"}
    return report


def edits(app: Application, root: Path, helper: Path) -> dict:
    fix = fixture(root / "edits", helper)
    run(app, fix, set("ABCDEF"))
    run(app, fix, set())
    (fix.root / "a.txt").write_bytes(b"a1\n")
    run(app, fix, set("ACDE"))
    before = (fix.root / "b.txt").stat()
    os.utime(fix.root / "b.txt", ns=(before.st_atime_ns, before.st_mtime_ns + 1000000000))
    run(app, fix, set())
    before = (fix.root / "a.txt").stat()
    (fix.root / "a.txt").write_bytes(b"a2\n")
    os.utime(fix.root / "a.txt", ns=(before.st_atime_ns, before.st_mtime_ns))
    run(app, fix, set("ACDE"))
    fix.config["targets"][2]["argv"][5] = "v2"
    fix.save()
    run(app, fix, set("CE"))
    fix.config["targets"][1]["environment"]["MARK"] = "blue"
    fix.save()
    run(app, fix, set("BDE"))
    (fix.root / "artifacts/C.bin").unlink()
    run(app, fix, set("C"))
    # Rebuilding a missing output with identical bytes/signature does not dirty its consumers.
    (fix.root / "artifacts/B.bin").write_bytes(b"damaged")
    run(app, fix, set("B"))
    (fix.root / "artifacts/A.bin").chmod(0o600)
    run(app, fix, set("A"))
    (fix.root / "b.txt").chmod(0o600)
    run(app, fix, set("BDE"))
    fix.config["targets"].reverse()
    fix.save()
    run(app, fix, set())
    removed = next(row for row in fix.config["targets"] if row["id"] == "F")
    fix.config["targets"] = [row for row in fix.config["targets"] if row["id"] != "F"]
    fix.save()
    run(app, fix, set())
    assert (fix.root / "artifacts/F.bin").exists()
    fix.config["targets"].append(removed)
    fix.save()
    run(app, fix, {"F"})
    return {
        "runs": 14,
        "same_size_restored_mtime_detected": True,
        "touch_only_cached": True,
        "actual_command_log_checked": True,
        "unaffected_targets_cached": True,
        "final_cache_sha256": digest(canonical(cache(fix))),
    }


def failures(app: Application, root: Path, helper: Path) -> dict:
    modes = ["fail", "missing", "directory", "symlink", "hardlink", "oversized", "hold", "flood", "signal"]
    for mode in modes:
        fix = fixture(root / mode, helper)
        run(app, fix, set("ABCDEF"))
        before = {p.name: p.read_bytes() for p in (fix.root / "artifacts").iterdir()}
        fix.config["targets"][0]["argv"][2] = mode
        fix.config["targets"][0]["timeout_ms"] = 500
        fix.save()
        (fix.root / "invocations.txt").write_text("")
        result = app.run(fix.root, fix.settings, timeout=15)
        assert result.returncode == 1 and not result.stderr, (mode, result.stdout, result.stderr)
        report = json.loads((fix.state / "report.json").read_bytes())
        assert report["summary"] == {"cached": 2, "rebuilt": 0, "failed": 1, "blocked": 3}
        assert invocations(fix) == ["A"] and set(cache(fix)) == {"B", "F"}
        assert report["cache_sha256"] == digest(canonical(cache(fix)))
        assert report["targets"][0]["error"] and report["targets"][0]["reason"] == "changed_recipe"
        expected_kind = "timeout" if mode == "hold" else ("output_limit" if mode == "flood" else "exited")
        assert report["targets"][0]["outcome"]["kind"] == expected_kind
        assert before == {p.name: p.read_bytes() for p in (fix.root / "artifacts").iterdir()}
        assert not (fix.state / "artifact.tmp").exists()
        if mode == "hold":
            gone(fix.root / "invocations.txt.pids", minimum=2)
        fix.config["targets"][0]["argv"][2] = "normal"
        fix.config["targets"][0]["timeout_ms"] = 2000
        fix.save()
        run(app, fix, set("ACDE"))
    return {
        "command_and_output_failures": len(modes),
        "old_outputs_preserved": True,
        "failed_and_blocked_cache_entries_removed": True,
        "independent_targets_retained": True,
        "timeout_descendants_terminated": True,
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, BUILD_PAUSE=label, BUILD_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    messages: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
        return  # noqa: PLR1711 - explicit repository returns

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = messages.get(timeout=30)
            assert line is not None, "exited before " + label
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def interruptions(app: Application, root: Path, helper: Path) -> dict:
    points = [
        "staged:initial",
        "committed:initial",
        "staged:invalidate:A",
        "committed:invalidate:A",
        "produced:A",
        "published:A",
        "staged:success:A",
        "committed:success:A",
        "staged:final",
        "committed:final",
        "staged:report",
        "committed:report",
    ]
    hashes = []
    for label in points:
        fix = fixture(root / label.replace(":", "-"), helper)
        run(app, fix, set("ABCDEF"))
        (fix.root / "a.txt").write_bytes(b"changed source\n")
        (fix.root / "invocations.txt").write_text("")
        process = paused(app, fix, label)
        process.kill()
        assert process.wait(timeout=5) < 0
        if label in ["committed:invalidate:A", "produced:A", "published:A", "staged:success:A"]:
            assert "A" not in cache(fix)
        if label in ["staged:initial", "committed:initial", "staged:invalidate:A", "committed:invalidate:A"]:
            assert invocations(fix) == []
        run(app, fix)
        hashes.append(digest(canonical(cache(fix))))
    assert len(set(hashes)) == 1
    fix = fixture(root / "parent-signal", helper)
    run(app, fix, set("ABCDEF"))
    fix.config["targets"][0]["argv"][2] = "hold"
    fix.config["targets"][0]["timeout_ms"] = 10000
    fix.save()
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        ready(fix.root / "invocations.txt.pids", process)
        process.terminate()
        output, error = process.communicate(timeout=10)
        assert process.returncode == 143 and not error, (output, error)
        assert "A" not in cache(fix) and {"B", "F"} <= set(cache(fix))
        gone(fix.root / "invocations.txt.pids", minimum=2)
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
    fix.config["targets"][0]["argv"][2] = "normal"
    fix.config["targets"][0]["timeout_ms"] = 2000
    fix.save()
    # Interrupted consumers retain their valid entries; restoring the recipe only rebuilds A.
    run(app, fix, {"A"})
    return {
        "actual_kill_boundaries": len(points),
        "parent_signal_cleanup": True,
        "portable_final_cache_sha256": hashes[0],
    }


def rejected(app: Application, fix: Fixture) -> None:
    (fix.root / "invocations.txt").write_text("")
    before = {p.name: p.read_bytes() for p in fix.state.iterdir() if p.is_file()} if fix.state.is_dir() else {}
    result = app.run(fix.root, fix.settings, timeout=15)
    assert result.returncode == 2 and result.stderr and not invocations(fix), (
        result.returncode,
        result.stdout,
        result.stderr,
    )
    if before:
        assert before == {p.name: p.read_bytes() for p in fix.state.iterdir() if p.is_file()}
    return  # noqa: PLR1711 - explicit repository returns


def invalid(app: Application, root: Path, helper: Path) -> dict:
    changes = [
        ("id", ""),
        ("id", "1bad"),
        ("id", "x" * 33),
        ("inputs", []),
        ("inputs", {"x": "../escape"}),
        ("inputs", {"bad key": "a.txt"}),
        ("inputs", {"key" + str(i): "a.txt" for i in range(9)}),
        ("output", "a.txt"),
        ("output", "state/cache.json"),
        ("output", "../outside"),
        ("dependencies", ["unknown"]),
        ("dependencies", ["A"]),
        ("dependencies", ["B", "B"]),
        ("environment", {"0BAD": "x"}),
        ("environment", {"A": "\0"}),
        ("environment", {"K" + str(i): "x" for i in range(33)}),
        ("environment", {"A": "x" * 16382}),
        ("environment", {"K" * 129: "x"}),
        ("environment", {"A": 1}),
        ("timeout_ms", 0),
        ("timeout_ms", 60001),
        ("timeout_ms", True),
        ("timeout_ms", 1.0),
        ("max_output", -1),
        ("max_output", 65537),
        ("max_output", True),
        ("argv", []),
        ("argv", ["{output}"] * 65),
        ("argv", ["{output}", "\0"]),
        ("argv", ["{output}", "x" * 1025]),
        ("argv", ["/bin/true"]),
        ("argv", ["{output}", "{input:missing}"]),
        ("argv", ["{output}", "{dependency:B}"]),
    ]
    for index, (key, value) in enumerate(changes):
        fix = fixture(root / f"field-{index}", helper)
        fix.config["targets"][0][key] = value
        fix.save()
        rejected(app, fix)
    for index in range(8):
        fix = fixture(root / f"graph-{index}", helper)
        if index == 0:
            fix.config["targets"].append(copy.deepcopy(fix.config["targets"][0]))
        elif index == 1:
            fix.config["targets"][1]["output"] = fix.config["targets"][0]["output"]
        elif index == 2:
            fix.config["targets"][0]["dependencies"] = ["E"]
        elif index == 3:
            fix.config["targets"] = [
                dict(copy.deepcopy(fix.config["targets"][0]), id=f"j{i}", output=f"artifacts/{i}") for i in range(17)
            ]
        elif index == 4:
            for row in fix.config["targets"]:
                row["timeout_ms"] = 60000
        elif index == 5:
            fix.config["version"] = True
        elif index == 6:
            fix.config["state"] = "a.txt"
        else:
            fix.config["targets"][0]["extra"] = 1
        fix.save()
        rejected(app, fix)
    for index, raw in enumerate([b"", b"{", b"[]", b"\xff", b'{"version":1,"version":1}']):
        fix = fixture(root / f"json-{index}", helper)
        fix.source.write_bytes(raw)
        rejected(app, fix)
    reference = fixture(root / "reference", helper)
    run(app, reference, set("ABCDEF"))
    old = cache(reference)
    changes = []
    for key, value in [
        ("signature", "0" * 64),
        ("recipe", "bad"),
        ("output", {}),
        ("inputs", []),
        ("dependencies", {"B": {}}),
        ("extra", 1),
    ]:
        changed = copy.deepcopy(old)
        changed["A"][key] = value
        changes.append(changed)
    for index, changed in enumerate(changes):
        fix = fixture(root / f"state-{index}", helper)
        fix.state.mkdir()
        (fix.state / "cache.json").write_bytes(
            canonical({"version": 1, "entries": changed, "sha256": digest(canonical(changed))})
        )
        rejected(app, fix)
    for index, raw in enumerate(
        [b"{", b"[]", b'{"version":1,"entries":{},"sha256":"bad"}', b'{"version":1,"version":1}']
    ):
        fix = fixture(root / f"state-json-{index}", helper)
        fix.state.mkdir()
        (fix.state / "cache.json").write_bytes(raw)
        rejected(app, fix)
    return {
        "invalid_target_fields": 33,
        "invalid_graphs_and_suites": 8,
        "malformed_configs": 5,
        "rechecksummed_invalid_caches": 6,
        "malformed_caches": 4,
    }


def transactions(app: Application, root: Path, helper: Path) -> dict:
    for what in ["input", "configuration", "staging"]:
        fix = fixture(root / what, helper)
        run(app, fix, set("ABCDEF"))
        before = (fix.root / "artifacts/A.bin").read_bytes()
        (fix.root / "a.txt").write_bytes(b"changed\n")
        process = paused(app, fix, "produced:A")
        try:
            path = (
                fix.root / "a.txt"
                if what == "input"
                else (fix.source if what == "configuration" else fix.state / "artifact.tmp")
            )
            with path.open("ab") as stream:
                stream.write(b" ")
            (fix.root / "release").touch()
            code = process.wait(timeout=20)
            assert code in [1, 2]
            assert (fix.root / "artifacts/A.bin").read_bytes() == before and "A" not in cache(fix)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
    fix = fixture(root / "contenders", helper)
    process = paused(app, fix, "committed:initial")
    try:
        for _ in range(8):
            rejected(app, fix)
    finally:
        process.kill()
        process.wait(timeout=5)
    run(app, fix, set("ABCDEF"))
    return {"changed_input_config_and_staging_rejected": 3, "competing_workers_rejected": 8}


def filesystem(app: Application, root: Path, helper: Path) -> dict:
    names = [
        "input-symlink",
        "input-hardlink",
        "input-fifo",
        "output-symlink",
        "output-hardlink",
        "state-symlink",
        "lock-symlink",
        "lock-hardlink",
        "cache-symlink",
        "cache-hardlink",
        "unknown-state",
    ]
    for name in names:
        fix = fixture(root / name, helper)
        outside = fix.root / "untouched"
        outside.write_bytes(b"preserve")
        if name.startswith("input-"):
            path = fix.root / "a.txt"
            path.unlink()
        elif name.startswith("output-"):
            path = fix.root / "artifacts/A.bin"
        elif name.startswith("state-"):
            path = fix.state
        elif name.startswith("lock-"):
            path = fix.root / "state.lock"
        else:
            fix.state.mkdir()
            path = fix.state / ("cache.json" if name.startswith("cache-") else "unrelated.txt")
        if name.endswith("symlink"):
            path.symlink_to(outside)
        elif name.endswith("hardlink"):
            os.link(outside, path)
        elif name.endswith("fifo"):
            os.mkfifo(path)
        else:
            path.write_bytes(b"keep")
        rejected(app, fix)
        assert outside.read_bytes() == b"preserve"
    fix = fixture(root / "permission", helper)
    run(app, fix, set("ABCDEF"))
    (fix.root / "a.txt").write_bytes(b"changed\n")
    old = (fix.root / "artifacts/A.bin").read_bytes()
    (fix.root / "artifacts").chmod(0o500)
    try:
        result = app.run(fix.root, fix.settings, timeout=20)
        assert result.returncode == 1 and "A" not in cache(fix)
        assert (fix.root / "artifacts/A.bin").read_bytes() == old
    finally:
        (fix.root / "artifacts").chmod(0o700)
    run(app, fix, set("ACDE"))
    return {"alias_and_ownership_cases": len(names), "permission_failure_recovered": True}


def limits(app: Application, root: Path, helper: Path) -> dict:
    fix = fixture(root / "graph-maximum", helper)
    executable = os.path.relpath(helper, fix.root)
    rows = [target("j" + str(i).zfill(2), {"source": "a.txt"}, [], executable) for i in range(15)]
    rows.append(target("z", {}, [row["id"] for row in rows], executable))
    fix.config["targets"] = rows
    fix.save()
    fix.source.write_bytes(fix.source.read_bytes().ljust(262144, b" "))
    run(app, fix, {row["id"] for row in rows})
    arguments = fixture(root / "command-maximum", helper)
    row = arguments.config["targets"][0]
    row["id"] = "A" * 32
    row["inputs"] = {"input" + str(i): "a.txt" for i in range(7)} | {"I" * 32: "b.txt"}
    row["argv"][1] = row["id"]
    row["argv"][5] = "v" * 1024
    tokens = ["{input:" + key + "}" for key in row["inputs"]]
    row["argv"] = row["argv"][:6] + [tokens[i % 8] for i in range(58)]
    row["environment"] = {"K" + str(i): "x" for i in range(30)} | {"K" * 128: "x", "MARK": ""}
    size = sum(len(key) + len(value) + 2 for key, value in row["environment"].items())
    row["environment"]["MARK"] = "e" * (16384 - size)
    other = arguments.config["targets"][1]
    row["timeout_ms"] = other["timeout_ms"] = 60000
    arguments.config["targets"] = [row, other]
    arguments.save()
    run(app, arguments, {row["id"], "B"})
    run(app, arguments, set())
    full = fixture(root / "file-maximum", helper)
    data = bytes(range(256)) * 16384
    (full.root / "a.txt").write_bytes(data)
    row = full.config["targets"][0]
    row["argv"][2] = "plain"
    row["timeout_ms"] = 60000
    row["max_output"] = 0
    full.config["targets"] = [row]
    full.save()

    def memory_limit() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return  # noqa: PLR1711 - explicit repository returns

    result = subprocess.run(
        app.command,
        cwd=full.root,
        env=app.environment(full.settings),
        capture_output=True,
        text=True,
        timeout=90,
        preexec_fn=memory_limit,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (full.root / "artifacts/A.bin").read_bytes() == data
    run(app, full, set())
    path = full.state / "cache.json"
    path.write_bytes(path.read_bytes().ljust(2097152, b" "))
    run(app, full, set())
    path.write_bytes(path.read_bytes().ljust(2097153, b" "))
    rejected(app, full)
    oversized = fixture(root / "input-over", helper)
    (oversized.root / "a.txt").write_bytes(data + b"x")
    oversized.config["targets"] = [oversized.config["targets"][0]]
    oversized.save()
    result = app.run(oversized.root, oversized.settings, timeout=15)
    assert result.returncode == 1 and not invocations(oversized) and cache(oversized) == {}
    empty = fixture(root / "empty", helper)
    empty.config["targets"] = []
    empty.save()
    run(app, empty, set())
    over = fixture(root / "config-over", helper)
    over.source.write_bytes(over.source.read_bytes().ljust(262145, b" "))
    rejected(app, over)
    return {
        "targets": 16,
        "dependencies": 15,
        "direct_inputs": 8,
        "arguments": 64,
        "argument_bytes": 1024,
        "environment_variables": 32,
        "environment_bytes": 16384,
        "total_timeout_ms": 120000,
        "input_and_artifact_bytes": 4194304,
        "configuration_bytes": 262144,
        "cache_bytes": 2097152,
        "memory_limit": 268435456,
        "maximum_artifact_sha256": digest(data),
    }


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    helper = build_fixture(directory)
    return {
        "edits": edits(app, directory / "edits", helper),
        "failures": failures(app, directory / "failures", helper),
        "interruptions": interruptions(app, directory / "interruptions", helper),
        "invalid": invalid(app, directory / "invalid", helper),
        "transactions": transactions(app, directory / "transactions", helper),
        "filesystem": filesystem(app, directory / "filesystem", helper),
        "limits": limits(app, directory / "limits", helper),
        "independent_dependency_content_cache_and_invocation_oracle": True,
    }
