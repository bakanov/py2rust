"""Independent sockets, report calculations, worker supervision and atomic bundle acceptance."""

from __future__ import annotations

import copy
import json
import os
import select
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path

from .common import Application
from .process_fixture import build_fixture, gone, ready
from .transfer_fixture import (
    aggregates,
    build_reporter,
    canonical,
    case,
    comparison,
    digest,
    payload,
    recorded,
    worker,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def command(app: Application, root: Path) -> dict:
    environment = (
        {} if app.engine == "python" else {name: "/nonexistent" for name in ["PATH", "PYTHONHOME", "PYTHONPATH"]}
    )
    executable = Path(app.command[0])
    argv = [str(executable.parent.resolve() / executable.name), *app.command[1:]]
    return {"argv": argv, "environment": environment, "cwd": str(root)}


def fixture(
    root: Path, sender: Application, receiver: Application, cases: list[dict] | None = None, repetitions: int = 1
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "mode": "benchmark",
        "output": "output",
        "cases": [case()] if cases is None else cases,
        "repetitions": repetitions,
        "sender": command(sender, root),
        "receiver": command(receiver, root),
    }
    save(root / "transfer-job.json", config)
    return config


def compare_fixture(root: Path, before: dict | None = None, after: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    save(root / "before.json", recorded() if before is None else before)
    save(root / "after.json", recorded(times=[100, 101, 300]) if after is None else after)
    config = {"version": 1, "mode": "compare", "output": "output", "baseline": "before.json", "candidate": "after.json"}
    save(root / "transfer-job.json", config)
    return config


def inspect(root: Path, config: dict) -> dict:
    output = root / config["output"]
    report = json.loads((output / "report.json").read_bytes())
    replay = copy.deepcopy(config)
    replay["output"] = "replayed"
    names = {"report.json", "report.txt", "replay.json"}
    if config["mode"] == "benchmark":
        assert set(report) == {"version", "kind", "cases", "repetitions", "workers", "runs", "statistics"}
        assert report["version"] == 1 and report["kind"] == "benchmark"
        assert report["cases"] == config["cases"] and report["repetitions"] == config["repetitions"]
        assert report["workers"] == {role: config[role]["argv"] for role in ["sender", "receiver"]}
        known = {row["id"]: row for row in config["cases"]}
        keys = set()
        for index, row in enumerate(report["runs"]):
            assert set(row) == {"case", "trial", "status", "phase", "error", "sender", "receiver", "wall_us"}
            assert type(row["wall_us"]) is int and 1 <= row["wall_us"] <= 120_000_000
            key = (row["case"], row["trial"])
            assert key not in keys and key[0] in known and 1 <= key[1] <= config["repetitions"]
            keys.add(key)
            if row["status"] == "ok":
                assert row["phase"] == "reports" and row["error"] == ""
                for role in ["sender", "receiver"]:
                    elapsed = row[role]["elapsed_us"]
                    assert type(elapsed) is int and 1 <= elapsed <= row["wall_us"]
                    assert row[role] == worker(known[row["case"]], role, elapsed)
            else:
                assert row["status"] in ["failed", "interrupted"] and row["error"]
                if row["status"] == "interrupted":
                    assert index == len(report["runs"]) - 1
        if report["runs"][-1]["status"] != "interrupted":
            assert keys == {
                (row["id"], trial) for row in config["cases"] for trial in range(1, config["repetitions"] + 1)
            }
        assert report["statistics"] == aggregates(config["cases"], report["runs"], config["repetitions"])
        lines = ["Transfer benchmark"] + [
            row["id"] + ": " + canonical(report["statistics"][row["id"]]).decode().strip() for row in config["cases"]
        ]
        lines += [
            row["case"] + ": " + row["phase"] + ": " + row["error"] for row in report["runs"] if row["status"] != "ok"
        ]
    else:
        before = (root / config["baseline"]).read_bytes()
        after = (root / config["candidate"]).read_bytes()
        expected = {
            "version": 1,
            "kind": "comparison",
            "baseline_sha256": digest(before),
            "candidate_sha256": digest(after),
            "rows": comparison(json.loads(before), json.loads(after)),
        }
        assert report == expected
        for name, data in [("baseline.json", before), ("candidate.json", after)]:
            assert (output / name).read_bytes() == data
            names.add(name)
        replay.update(baseline="baseline.json", candidate="candidate.json")
        lines = ["Transfer compare"] + [canonical(row).decode().strip() for row in report["rows"]]
    assert json.loads((output / "replay.json").read_bytes()) == replay
    assert (output / "report.json").read_bytes() == canonical(report)
    assert (output / "report.txt").read_text() == "\n".join(lines) + "\n"
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert set(manifest) == names and {p.name for p in output.iterdir()} == names | {"manifest.json"}
    for name, row in manifest.items():
        data = (output / name).read_bytes()
        assert row == {"bytes": len(data), "sha256": digest(data)}
    return report


def run(app: Application, root: Path, config: dict, expected_code: int = 0, timeout: int = 30) -> dict:
    save(root / "transfer-job.json", config)
    result = app.run(root, {}, timeout=timeout)
    assert result.returncode == expected_code and not result.stderr, (root, result)
    assert result.stdout == "completed " + config["mode"] + "\n", (root, result)
    return inspect(root, config)


def reject(app: Application, root: Path, config: dict | None = None) -> None:
    if config is not None:
        save(root / "transfer-job.json", config)
    result = app.run(root, {}, timeout=10)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert not (root / "output").exists()
    return  # noqa: PLR1711


def benchmarks(app: Application, root: Path) -> dict:
    cases = [
        case("empty", 0, 0, send_chunk=1, receive_chunk=1),
        case("one", 1, 255),
        case("fragmented", 257),
        case("page", 4096, send_chunk=257, receive_chunk=1024),
        case("block", 65536, send_chunk=4096, receive_chunk=8192),
        case("capacity", 1048576, 255, send_chunk=65536, receive_chunk=65536, timeout_ms=5000),
    ]
    work = root / "repeated"
    report = run(app, work, fixture(work, app, app, cases, 3), timeout=45)
    assert all(row["status"] == "ok" for row in report["runs"])
    work = root / "case-and-repetition-capacity"
    cases2 = [case("c" + str(i), 0, i, timeout_ms=1500) for i in range(16)]
    other = run(app, work, fixture(work, app, app, cases2, 4), timeout=45)
    assert len(other["runs"]) == 64 and all(row["status"] == "ok" for row in other["runs"])
    replay = json.loads((root / "repeated/output/replay.json").read_bytes())
    replayed = run(app, root / "repeated/output", replay, timeout=45)
    assert all(row["status"] == "ok" for row in replayed["runs"])
    return {
        "real_transfers": 100,
        "max_payload_bytes": 1048576,
        "max_cases": 16,
        "max_repetitions": 4,
        "payload_digests": {row["id"]: digest(payload(row)) for row in cases},
        "benchmark_replay": True,
    }


def exact_read(stream: socket.socket, count: int) -> bytes:
    parts = bytearray()
    while len(parts) < count:
        data = stream.recv(count - len(parts))
        if not data:
            break
        parts.extend(data)
    return bytes(parts)


def receiver_peer(app: Application, root: Path, mode: str) -> None:
    row = case(size=257, timeout_ms=300 if mode == "stall" else 2000)
    data = payload(row)
    header = b"P2RB1" + len(data).to_bytes(8, "big") + digest(data).encode()
    mutations = {
        "good": header + data,
        "magic": b"WRONG" + header[5:] + data,
        "length": header[:5] + (258).to_bytes(8, "big") + header[13:] + data,
        "digest": header[:13] + b"0" * 64 + data,
        "short-header": header[:36],
        "short-body": header + data[:-1],
        "corrupt": header + b"x" + data[1:],
        "trailing": header + data + b"!",
        "stall": header,
    }
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"TRANSFER_ROLE": "receiver", "TRANSFER_CASE": json.dumps(row), "PYTHONUNBUFFERED": "1"}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert select.select([process.stdout], [], [], 5)[0], "no readiness"
        line = process.stdout.readline()
        assert line.startswith(b"READY "), (line, process.communicate())
        with socket.create_connection(("127.0.0.1", int(line[6:])), timeout=3) as stream:
            try:
                raw = mutations[mode]
                for offset in range(0, len(raw), 3):
                    stream.sendall(raw[offset : offset + 3])
                if mode != "stall":
                    stream.shutdown(socket.SHUT_WR)
                answer = exact_read(stream, 67)
                assert answer == (b"OK" + digest(data).encode() if mode == "good" else b""), (mode, answer)
            except (BrokenPipeError, ConnectionResetError):
                assert mode != "good"
        stdout, stderr = process.communicate(timeout=4)
        if mode == "good":
            value = json.loads(stdout)
            assert process.returncode == 0 and not stderr and value == worker(row, "receiver", value["elapsed_us"])
            assert 1 <= value["elapsed_us"] <= 2_000_000
        else:
            assert process.returncode == 2 and stderr and not stdout, (mode, process.returncode, stdout, stderr)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    return  # noqa: PLR1711


def sender_peer(app: Application, root: Path, mode: str) -> None:
    row = case(size=257, timeout_ms=300 if mode == "stall" else 2000)
    data = payload(row)
    wire = b"P2RB1" + len(data).to_bytes(8, "big") + digest(data).encode() + data
    ack = b"OK" + digest(data).encode()
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(5)

        def peer() -> None:
            try:
                with listener.accept()[0] as stream:
                    stream.settimeout(4)
                    received = bytearray()
                    while True:
                        part = stream.recv(13)
                        if not part:
                            break
                        received.extend(part)
                    assert bytes(received) == wire
                    if mode == "stall":
                        assert stream.recv(1) == b""
                        time.sleep(0.6)
                    else:
                        answer = {"good": ack, "wrong": b"NO" + ack[2:], "short": ack[:31], "trailing": ack + b"!"}[
                            mode
                        ]
                        for offset in range(0, len(answer), 2):
                            stream.sendall(answer[offset : offset + 2])
                        stream.shutdown(socket.SHUT_WR)
            except (BrokenPipeError, ConnectionResetError):
                if mode == "good":
                    errors.append("good peer connection reset")
            except Exception as error:  # noqa: BLE001 - propagate thread failures
                errors.append(repr(error))
            return  # noqa: PLR1711

        thread = threading.Thread(target=peer)
        thread.start()
        result = app.run(
            root,
            {
                "TRANSFER_ROLE": "sender",
                "TRANSFER_CASE": json.dumps(row),
                "TRANSFER_PORT": str(listener.getsockname()[1]),
            },
            timeout=6,
        )
        thread.join(timeout=6)
        assert not thread.is_alive() and not errors, errors
    if mode == "good":
        value = json.loads(result.stdout)
        assert result.returncode == 0 and not result.stderr and value == worker(row, "sender", value["elapsed_us"])
        assert 1 <= value["elapsed_us"] <= 2_000_000
    else:
        assert result.returncode == 2 and result.stderr and not result.stdout, (mode, result)
    return  # noqa: PLR1711


def sockets(app: Application, root: Path) -> dict:
    root.mkdir(parents=True)
    receiver_cases = ["good", "magic", "length", "digest", "short-header", "short-body", "corrupt", "trailing", "stall"]
    sender_cases = ["good", "wrong", "short", "trailing", "stall"]
    for mode in receiver_cases:
        receiver_peer(app, root, mode)
    for mode in sender_cases:
        sender_peer(app, root, mode)
    return {
        "receiver_independent_peers": len(receiver_cases),
        "sender_independent_peers": len(sender_cases),
        "fragmented_bytes_and_eof_verified": True,
    }


def comparisons(app: Application, root: Path) -> dict:
    before = recorded([case("steady"), case("changed"), case("gone"), case("empty", 0), case("failed")])
    after = recorded(
        [case("steady"), case("changed", seed=18), case("added"), case("empty", 0), case("failed")],
        times=[100, 101, 300],
    )
    after["runs"][-1].update(status="failed", phase="transfer", error="independent failure", sender=None, receiver=None)
    after["statistics"] = aggregates(after["cases"], after["runs"], after["repetitions"])
    work = root / "all-statuses"
    report = run(app, work, compare_fixture(work, before, after))
    assert {row["status"] for row in report["rows"]} == {
        "comparable",
        "incompatible",
        "missing_candidate",
        "missing_baseline",
        "unavailable",
    }
    assert next(row for row in report["rows"] if row["case"] == "steady")["wall_change_ppm"] == -663334
    replay = json.loads((work / "output/replay.json").read_bytes())
    assert run(app, work / "output", replay) == report
    for index, field in enumerate(["size", "seed", "send_chunk", "receive_chunk", "timeout_ms"]):
        changed = case()
        changed[field] += 1
        work = root / f"incompatible-{index}"
        assert (
            run(app, work, compare_fixture(work, recorded(), recorded([changed])))["rows"][0]["status"]
            == "incompatible"
        )
    partial = recorded([case("one"), case("two")])
    partial["runs"] = partial["runs"][:2]
    partial["runs"][-1].update(status="interrupted", phase="readiness", error="signal", sender=None, receiver=None)
    partial["statistics"] = aggregates(partial["cases"], partial["runs"], partial["repetitions"])
    work = root / "interrupted"
    result = run(app, work, compare_fixture(work, partial, partial))
    assert all(row["status"] == "unavailable" for row in result["rows"])
    return {
        "independent_median_and_floor_ppm_oracles": True,
        "comparison_statuses": 5,
        "incompatible_fields": 5,
        "partial_interrupted_report": True,
        "byte_exact_replay": True,
    }


def invalid(app: Application, root: Path) -> dict:
    changes = [
        ("version", True),
        ("version", 2),
        ("mode", "unknown"),
        ("output", ""),
        ("output", "\0"),
        ("cases", []),
        ("cases", {}),
        ("cases", [case(), case()]),
        ("repetitions", 0),
        ("repetitions", 5),
        ("repetitions", True),
        ("extra", 1),
        ("cases", [case("c" + str(i)) for i in range(17)]),
        ("cases", [case("c" + str(i), timeout_ms=15000) for i in range(9)]),
    ]
    for field, values in {
        "id": ["", "1bad", "é", "a" * 33],
        "size": [-1, 1048577, True],
        "seed": [-1, 256, True],
        "send_chunk": [0, 65537, True],
        "receive_chunk": [0, 65537, True],
        "timeout_ms": [0, 15001, True],
    }.items():
        changes.extend(("cases", [dict(case(), **{field: value})]) for value in values)
    count = 0
    for field, value in changes:
        work = root / str(count)
        config = fixture(work, app, app)
        config[field] = value
        reject(app, work, config)
        count += 1
    commands = [
        ("argv", []),
        ("argv", ["a"] * 33),
        ("argv", [""]),
        ("argv", ["\0"]),
        ("argv", [app.command[0], "é" * 4096]),
        ("cwd", "missing"),
        ("cwd", "transfer-job.json"),
        ("environment", {"TRANSFER_CASE": "x"}),
        ("environment", {"PYTHONUNBUFFERED": "x"}),
        ("environment", {"BAD=NAME": "x"}),
        ("environment", {"A": "\0"}),
        ("environment", {"A": "é" * 4096}),
        ("environment", {"E" + str(i): "v" for i in range(33)}),
        ("environment", {"a" * 65: "x"}),
        ("environment", []),
        ("environment", {"A": True}),
        ("extra", 1),
    ]
    for role in ["sender", "receiver"]:
        for field, value in commands:
            work = root / str(count)
            config = fixture(work, app, app)
            config[role][field] = value
            reject(app, work, config)
            count += 1
    edits = [
        ("version", 2),
        ("version", True),
        ("kind", "other"),
        ("statistics", {}),
        ("extra", 1),
        ("runs", []),
        ("repetitions", 5),
        ("workers", {"sender": [], "receiver": ["x"]}),
    ]
    for field, value in edits:
        work = root / str(count)
        before = recorded()
        before[field] = value
        compare_fixture(work, before)
        reject(app, work)
        count += 1
    run_edits = [
        ("case", "unknown"),
        ("trial", 0),
        ("trial", True),
        ("status", "unknown"),
        ("phase", "unknown"),
        ("phase", "transfer"),
        ("wall_us", 0),
        ("wall_us", True),
        ("wall_us", 120000001),
        ("error", "nonempty"),
        ("extra", 1),
    ]
    for field, value in run_edits:
        before = recorded()
        before["runs"][0][field] = value
        work = root / str(count)
        compare_fixture(work, before)
        reject(app, work)
        count += 1
    for role in ["sender", "receiver"]:
        for field, value in [
            ("version", True),
            ("role", "other"),
            ("bytes", True),
            ("bytes", 99),
            ("sha256", "0" * 64),
            ("elapsed_us", 0),
            ("elapsed_us", True),
            ("elapsed_us", 999999),
        ]:
            before = recorded()
            before["runs"][0][role][field] = value
            work = root / str(count)
            compare_fixture(work, before)
            reject(app, work)
            count += 1
    for mode in ["duplicate-trial", "incomplete", "after-interrupted", "forged-statistics", "duplicate-json"]:
        before = recorded()
        if mode == "duplicate-trial":
            before["runs"][1] = copy.deepcopy(before["runs"][0])
        elif mode == "incomplete":
            before["runs"].pop()
        elif mode == "after-interrupted":
            before["runs"][0].update(status="interrupted", error="stop")
        elif mode == "forged-statistics":
            before["statistics"]["sample"]["wall_us"] += 1
        work = root / str(count)
        compare_fixture(work, before)
        if mode == "duplicate-json":
            (work / "before.json").write_bytes(canonical(before).replace(b'"version":1', b'"version":1,"version":1', 1))
        reject(app, work)
        count += 1
    return {"invalid_requests_and_reports": count}


def supervision(app: Application, root: Path) -> dict:
    reporter = build_reporter(root / "fixture")
    helper = build_fixture(root / "fixture")
    row = case()

    def fake(role: str, text: str | None = None, errors: str = "", delay: int = 250, code: int = 0) -> dict:
        output = canonical(worker(row, role)).decode() if text is None else text
        if role == "receiver":
            output = "READY 12345\n" + output
        return {"argv": [str(reporter), output, errors, str(delay), str(code)], "environment": {}, "cwd": str(root)}

    modes = [
        "receiver-missing",
        "sender-missing",
        "bad-ready",
        "bad-port",
        "exit",
        "nonzero",
        "stderr",
        "bad-json",
        "duplicate-json",
        "wrong-role",
        "wrong-size",
        "wrong-digest",
        "zero-time",
        "long-time",
        "flood",
    ]
    for mode in modes:
        work = root / mode
        config = fixture(work, app, app)
        config["sender"], config["receiver"] = fake("sender"), fake("receiver")
        if mode.endswith("missing"):
            config[mode.split("-")[0]]["argv"] = [str(work / "absent")]
        elif mode == "bad-ready":
            config["receiver"]["argv"][1] = "NOT READY\n"
        elif mode == "bad-port":
            config["receiver"]["argv"][1] = "READY 0\n"
        elif mode == "exit":
            config["receiver"] = {"argv": [str(helper), "exit", "0"], "environment": {}, "cwd": str(root)}
        elif mode == "nonzero":
            config["sender"] = fake("sender", code=7)
        elif mode == "stderr":
            config["sender"] = fake("sender", errors="unexpected diagnostic")
        elif mode in ["bad-json", "duplicate-json"]:
            config["sender"] = fake("sender", text="{" if mode == "bad-json" else '{"version":1,"version":1}')
        elif mode == "flood":
            config["sender"] = {
                "argv": [str(helper), "emit", "20000", "20000", "0"],
                "environment": {},
                "cwd": str(root),
            }
        else:
            bad = worker(row, "sender")
            field, value = {
                "wrong-role": ("role", "receiver"),
                "wrong-size": ("bytes", 258),
                "wrong-digest": ("sha256", "0" * 64),
                "zero-time": ("elapsed_us", 0),
                "long-time": ("elapsed_us", 120000001),
            }[mode]
            bad[field] = value
            config["sender"] = fake("sender", text=canonical(bad).decode())
        report = run(app, work, config, 1)
        assert report["runs"][0]["status"] == "failed"
    for role in ["sender", "receiver"]:
        for mode in ["deadline", "interrupt"]:
            work = root / f"{role}-{mode}"
            config = fixture(work, app, app, [case(timeout_ms=350 if mode == "deadline" else 5000)], 3)
            pidfile = work / "pids"
            config[role] = {"argv": [str(helper), "hold", str(pidfile)], "environment": {}, "cwd": str(root)}
            save(work / "transfer-job.json", config)
            if mode == "deadline":
                report = run(app, work, config, 1)
                assert len(report["runs"]) == 3 and all(r["status"] == "failed" for r in report["runs"])
                gone(pidfile, minimum=6)
            else:
                process = subprocess.Popen(
                    app.command,
                    cwd=work,
                    env=app.environment({}),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                try:
                    ready(pidfile, process)
                    process.send_signal(signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=5)
                    assert process.returncode == 130 and stdout == "completed benchmark\n" and not stderr
                    report = inspect(work, config)
                    assert len(report["runs"]) == 1 and report["runs"][0]["status"] == "interrupted"
                    gone(pidfile, minimum=2)
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
    return {
        "worker_failure_modes": len(modes),
        "deadline_cases": 2,
        "signal_cases": 2,
        "owned_parent_and_grandchild_groups_reaped": True,
        "remaining_trials_stop_on_signal": True,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / (stage + "-fault")
        config = compare_fixture(work)
        result = app.run(work, {"TRANSFER_FAULT": stage}, timeout=10)
        assert result.returncode == 2 and result.stderr
        assert not list(work.glob(".transfer-*"))
        assert (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for change in ["config", "baseline", "candidate", "competitor", "kill-staged", "kill-published"]:
        work = root / change
        config = compare_fixture(work)
        release = work / "release"
        stage = "published" if change == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"TRANSFER_PAUSE": stage, "TRANSFER_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 5)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            if change.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert (work / "output").exists() == (stage == "published")
                if stage == "published":
                    inspect(work, config)
                else:
                    assert len(list(work.glob(".transfer-*"))) == 1
            else:
                if change == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("untouched")
                else:
                    name = {"config": "transfer-job.json", "baseline": "before.json", "candidate": "after.json"}[change]
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=5)
                assert process.returncode == 2 and stderr and not stdout
                assert not list(work.glob(".transfer-*"))
                if change == "competitor":
                    assert (work / "output/keep").read_text() == "untouched"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return {
        "caught_faults": 2,
        "input_and_destination_races": 4,
        "hard_kills": 2,
        "complete_or_absent_final_directory": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name in ["transfer-job.json", "before.json", "after.json"]:
        for kind in ["symlink", "hardlink", "fifo", "directory", "unreadable", "oversize"]:
            work = root / str(count)
            compare_fixture(work)
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
            elif kind == "unreadable":
                path.write_bytes(raw)
                path.chmod(0)
            else:
                path.write_bytes(b" " * (65537 if name == "transfer-job.json" else 1048577))
            try:
                reject(app, work)
                assert target.read_bytes() == raw
            finally:
                if kind == "unreadable":
                    path.chmod(0o600)
            count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        compare_fixture(work)
        target = work / "output"
        if kind == "file":
            target.write_text("keep")
        elif kind == "directory":
            target.mkdir()
        elif kind == "symlink":
            target.symlink_to(work / "before.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {}, timeout=10)
            assert result.returncode == 2 and result.stderr and not result.stdout
            if kind == "file":
                assert target.read_text() == "keep"
            elif kind == "directory":
                assert not list(target.iterdir())
            elif kind == "symlink":
                assert target.is_symlink()
            else:
                assert not target.exists()
        finally:
            work.chmod(0o700)
        count += 1
    work = root / "exact-byte-boundaries"
    config = compare_fixture(work)
    for name, limit in [("transfer-job.json", 65536), ("before.json", 1048576), ("after.json", 1048576)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(limit, b" "))
    result = app.run(work, {}, timeout=10)
    assert result.returncode == 0 and not result.stderr
    inspect(work, config)
    return {"guarded_filesystem_cases": count, "exact_input_byte_boundaries": 3}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("benchmarks", benchmarks),
        ("sockets", sockets),
        ("comparisons", comparisons),
        ("invalid", invalid),
        ("supervision", supervision),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " transfer " + name + ": passed", flush=True)
    return observations
