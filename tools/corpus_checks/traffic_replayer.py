"""Independent binary encoder, TCP peer and complete traffic-replayer acceptance."""

# ruff: noqa: PLR1711 - explicit returns
from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import socket
import struct
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .common import Application

LIMITS = {"fixture_bytes": 8388608, "records": 256, "payload_bytes": 1048576, "scheduled_ms": 60000}
TIMEOUTS = {"connect_ms": 2000, "record_ms": 2000, "total_ms": 10000}
Record = tuple[int, int, bytes]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(rows: list[Record]) -> bytes:
    return (
        b"PYTRAF\x01\x00"
        + struct.pack(">I", len(rows))
        + b"".join(
            struct.pack(">IBI", scheduled, direction, len(payload)) + payload for scheduled, direction, payload in rows
        )
    )


def fixture(root: Path, rows: list[Record]) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    (root / "input.traffic").write_bytes(encode(rows))
    return {"version": 1, "mode": "inspect", "fixture": "input.traffic", "limits": dict(LIMITS)}


def run(app: Application, root: Path, job: dict, passed: bool = True) -> dict:
    (root / "traffic-job.json").write_text(json.dumps(job))
    result = app.run(root, {}, timeout=30)
    assert result.returncode == (0 if passed else 2) and not result.stderr, result
    report = json.loads(result.stdout)
    assert report["version"] == 1 and report["status"] == ("passed" if passed else "failed"), report
    assert (report["error"] is None) == passed, report
    return report


def verify_report(report: dict, rows: list[Record], encoded: bytes) -> None:
    assert report["fixture"] == {"size": len(encoded), "sha256": digest(encoded)}
    assert len(report["records"]) == len(rows)
    position = 12
    for index, (scheduled, direction, payload) in enumerate(rows):
        assert report["records"][index] == {
            "index": index,
            "header_offset": position,
            "payload_offset": position + 9,
            "scheduled_ms": scheduled,
            "direction": "send" if direction == 0 else "receive",
            "length": len(payload),
            "sha256": digest(payload),
            "preview_hex": payload[:32].hex(),
        }
        position += 9 + len(payload)
    return


def peer(rows: list[Record], connection: socket.socket) -> None:
    for _scheduled, direction, payload in rows:
        if direction == 0:
            received = bytearray()
            while len(received) < len(payload):
                chunk = connection.recv(min(4093, len(payload) - len(received)))
                assert chunk, (len(received), len(payload))
                received.extend(chunk)
            assert received == payload
        else:
            offset = 0
            sizes = [1, 7, 8191, 31, 65521]
            fragment = 0
            while offset < len(payload):
                part = payload[offset : offset + sizes[fragment % len(sizes)]]
                connection.sendall(part)
                offset += len(part)
                fragment += 1
    assert connection.recv(1) == b"", "client must half-close sending after its last record"
    return


def replay(
    app: Application,
    root: Path,
    rows: list[Record],
    handler: Callable[[socket.socket], None] | None = None,
    passed: bool = True,
    timeouts: dict | None = None,
    host: str = "127.0.0.1",
    prepare: bool = True,
) -> tuple[dict, dict]:
    job = fixture(root, rows) if prepare else json.loads((root / "traffic-job.json").read_text())
    errors = []
    observed = {"accepted": False}
    with socket.socket(socket.AF_INET6 if host == "::1" else socket.AF_INET) as listener:
        listener.bind((host, 0))
        listener.listen()
        listener.settimeout(15)
        job.update(
            mode="replay",
            peer={"host": host, "port": listener.getsockname()[1]},
            timeouts=dict(TIMEOUTS if timeouts is None else timeouts),
        )

        def serve() -> None:
            try:
                with listener.accept()[0] as connection:
                    observed["accepted"] = True
                    connection.settimeout(10)
                    if handler is None:
                        peer(rows, connection)
                    else:
                        handler(connection)
            except BaseException as error:  # noqa: BLE001 - propagate thread assertions to the caller
                errors.append(error)
            return

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        report = run(app, root, job, passed)
        thread.join(timeout=16)
        assert not thread.is_alive() and not errors and observed["accepted"], errors
    if passed:
        verify_report(report, rows, encode(rows))
        events = report["replay"]["events"]
        assert len(events) == len(rows)
        for index, event in enumerate(events):
            assert event["record"] == index and event["status"] == "passed"
            assert event["started_ms"] >= rows[index][0] - 1
            assert 0 <= event["lag_ms"] and 0 <= event["duration_ms"]
    return report, job


def semantics(app: Application, root: Path) -> dict:
    rows = [(0, 1, b"hello\0\xff"), (20, 0, b""), (20, 0, "Saved notes 世界".encode()), (40, 1, b"OK")]
    job = fixture(root / "inspect", rows)
    report = run(app, root / "inspect", job)
    verify_report(report, rows, encode(rows))
    assert report["replay"] is None
    replay(app, root / "ipv4", rows)
    replay(app, root / "ipv6", rows, host="::1")
    # The source may rotate after preflight. All network bytes and report hashes
    # must still refer to the immutable, fully validated in-memory snapshot.
    changed = root / "snapshot"

    def replace_source(connection: socket.socket) -> None:
        (changed / "input.traffic").write_bytes(b"changed after connection")
        peer(rows, connection)
        return

    replay(app, changed, rows, replace_source)
    scheduled = [(120, 0, b"scheduled"), (200, 0, b"later")]

    def check_schedule(connection: socket.socket) -> None:
        origin = time.monotonic()
        for due, _direction, payload in scheduled:
            received = bytearray()
            while len(received) < len(payload):
                chunk = connection.recv(len(payload) - len(received))
                assert chunk
                received.extend(chunk)
            assert received == payload
            assert (time.monotonic() - origin) * 1000 >= due - 35
        assert connection.recv(1) == b""
        return

    replay(app, root / "scheduled", scheduled, check_schedule)
    return {
        "ipv4_ipv6": True,
        "receive_first": True,
        "empty_payload": True,
        "immutable_snapshot": True,
        "scheduled_sends_observed_by_peer": True,
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(120)
    hashes = []
    count = 0
    for case in range(12):
        rows = [(0, rng.randrange(2), rng.randbytes(rng.randrange(15000))) for _ in range(rng.randrange(1, 10))]
        replay(app, root / str(case), rows)
        hashes.append(digest(encode(rows)))
        count += len(rows)
    return {"seed": 120, "fixtures": 12, "records": count, "fixture_hashes": hashes}


def malformed(app: Application, root: Path) -> dict:
    rows = [(0, 0, b"abc"), (5, 1, b"de")]
    raw = encode(rows)
    cases = []
    for length in range(len(raw)):
        if length < 12:
            expected = ("truncated_header", -1, length)
        elif length < 21:
            expected = ("truncated_record_header", 0, length)
        elif length < 24:
            expected = ("truncated_payload", 0, length)
        elif length < 33:
            expected = ("truncated_record_header", 1, length)
        else:
            expected = ("truncated_payload", 1, length)
        cases.append((raw[:length], expected))
    changes = [
        (0, b"X", ("bad_magic", -1, 0)),
        (6, b"\x02", ("bad_magic", -1, 0)),
        (7, b"\x01", ("bad_magic", -1, 0)),
        (8, struct.pack(">I", 0), ("record_limit", -1, 8)),
        (8, struct.pack(">I", 257), ("record_limit", -1, 8)),
        (8, struct.pack(">I", 0xFFFFFFFF), ("record_limit", -1, 8)),
        (8, struct.pack(">I", 1), ("trailing_fixture_bytes", 1, 24)),
        (8, struct.pack(">I", 3), ("truncated_record_header", 2, len(raw))),
        (12, struct.pack(">I", 60001), ("invalid_schedule", 0, 12)),
        (12, struct.pack(">I", 0xFFFFFFFF), ("invalid_schedule", 0, 12)),
        (16, b"\x02", ("invalid_direction", 0, 16)),
        (28, b"\xff", ("invalid_direction", 1, 28)),
        (17, struct.pack(">I", 1048577), ("payload_limit", 0, 17)),
        (29, struct.pack(">I", 0xFFFFFFFF), ("payload_limit", 1, 29)),
        (29, struct.pack(">I", 3), ("truncated_payload", 1, len(raw))),
    ]
    cases += [
        (raw[:offset] + replacement + raw[offset + len(replacement) :], expected)
        for offset, replacement, expected in changes
    ]
    cases += [(raw + b"\0", ("trailing_fixture_bytes", 2, len(raw)))]
    cases += [(encode([(5, 0, b""), (4, 1, b"")]), ("invalid_schedule", 1, 21))]
    # Keep a listening peer present: malformed input must never connect to it.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(256)
        for index, (data, expected) in enumerate(cases):
            home = root / str(index)
            job = fixture(home, rows)
            (home / "input.traffic").write_bytes(data)
            job.update(mode="replay", peer={"host": "127.0.0.1", "port": listener.getsockname()[1]}, timeouts=TIMEOUTS)
            report = run(app, home, job, False)
            error = report["error"]
            assert (error["code"], error["record"], error["offset"]) == expected, (index, report, expected)
            assert error["phase"] == "parse" and error["offset_kind"] == "file" and report["replay"] is None
            assert (home / "input.traffic").read_bytes() == data
        listener.setblocking(False)
        try:
            connection, _address = listener.accept()
        except BlockingIOError:
            pass
        else:
            connection.close()
            raise AssertionError("malformed fixture connected to peer")
    return {"all_prefixes": len(raw), "malformed_cases": len(cases), "no_network_before_full_validation": True}


def failures(app: Application, root: Path) -> dict:
    payload = bytes(range(256)) * 300

    def mismatch(connection: socket.socket) -> None:
        connection.sendall(payload[:65537] + b"\xff" + payload[65538:])
        return

    report, _job = replay(app, root / "mismatch", [(0, 1, payload)], mismatch, False)
    assert report["error"] == {
        "code": "mismatch",
        "phase": "receive",
        "record": 0,
        "offset": 65537,
        "offset_kind": "payload",
        "expected": 1,
        "actual": 255,
    }, report

    def later_mismatch(connection: socket.socket) -> None:
        connection.sendall(b"hello" + b"oX")
        return

    report, _job = replay(
        app, root / "later-mismatch", [(0, 1, b"hello"), (0, 0, b""), (0, 1, b"ok")], later_mismatch, False
    )
    assert report["error"]["record"] == 2 and report["error"]["offset"] == 1
    assert [event["status"] for event in report["replay"]["events"]] == ["passed", "passed", "failed"]

    def early(connection: socket.socket) -> None:
        connection.sendall(b"abc")
        return

    report, _job = replay(app, root / "early", [(0, 1, b"abcdef")], early, False)
    assert report["error"]["code"] == "early_eof" and report["error"]["offset"] == 3

    def extra(connection: socket.socket) -> None:
        connection.sendall(b"ok!")
        assert connection.recv(1) == b""
        return

    report, _job = replay(app, root / "extra", [(0, 1, b"ok")], extra, False)
    assert report["error"]["code"] == "extra_reply" and report["error"]["record"] == 1

    def close(connection: socket.socket) -> None:
        assert connection.recv(1) == b""
        return

    report, _job = replay(app, root / "schedule", [(200, 0, b"late")], close, False, dict(TIMEOUTS, total_ms=100))
    assert report["error"]["code"] == "deadline" and report["error"]["phase"] == "schedule"
    assert report["replay"]["events"] == []

    def slow(connection: socket.socket) -> None:
        for _ in range(12):
            try:
                connection.sendall(b"x")
            except (BrokenPipeError, ConnectionResetError):
                break
            time.sleep(0.05)
        return

    for name, timeouts in [
        ("record", dict(TIMEOUTS, record_ms=170)),
        ("overall", dict(TIMEOUTS, total_ms=170)),
    ]:
        report, _job = replay(app, root / name, [(0, 1, b"x" * 12)], slow, False, timeouts)
        assert report["error"]["phase"] == "receive" and report["error"]["code"] in {"io_error", "deadline"}
        assert 70 <= report["replay"]["elapsed_ms"] < 500, report
        assert report["error"]["offset"] < 12

    def never_eof(connection: socket.socket) -> None:
        assert connection.recv(1) == b""
        time.sleep(0.35)
        return

    report, _job = replay(app, root / "eof", [(0, 0, b"")], never_eof, False, dict(TIMEOUTS, record_ms=120))
    assert report["error"]["phase"] == "eof" and report["error"]["code"] == "io_error"
    # A bound but non-listening port reliably refuses connection without guessing an unused port.
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        home = root / "connect"
        job = fixture(home, [(0, 0, b"")])
        job.update(mode="replay", peer={"host": "127.0.0.1", "port": closed.getsockname()[1]}, timeouts=TIMEOUTS)
        report = run(app, home, job, False)
        assert report["error"]["phase"] == "connect" and report["error"]["record"] == -1
    return {"network_failure_cases": 9, "first_mismatch_byte": 65537, "fragmentation_does_not_extend_deadline": True}


def limits(app: Application, root: Path) -> dict:
    rows = [(0, 0, b"")] * 256
    replay(app, root / "record-maximum", rows)
    payload = bytes(range(256)) * 4096
    replay(app, root / "payload-maximum", [(0, 0, payload), (0, 1, payload)])
    rows = [(60000, 0, b"")]
    job = fixture(root / "schedule-maximum", rows)
    run(app, root / "schedule-maximum", job)
    # Largest snapshot is parsed, hashed and reported without any socket activity.
    rows = [(0, 0, payload)] * 7 + [(0, 0, payload[: len(payload) - 84])]
    job = fixture(root / "fixture-maximum", rows)
    assert len(encode(rows)) == LIMITS["fixture_bytes"]
    report = run(app, root / "fixture-maximum", job)
    verify_report(report, rows, encode(rows))
    home = root / "exact"
    rows = [(0, 0, b"abc")]
    job = fixture(home, rows)
    job["limits"].update(fixture_bytes=len(encode(rows)), records=1, payload_bytes=3, scheduled_ms=0)
    run(app, home, job)
    rejected = 0
    for key, value in [("fixture_bytes", len(encode(rows)) - 1), ("payload_bytes", 2)]:
        changed = copy.deepcopy(job)
        changed["limits"][key] = value
        run(app, home, changed, False)
        rejected += 1
    return {"maximum_records": 256, "maximum_payload": 1048576, "maximum_fixture": 8388608, "one_over_cases": rejected}


def invalid(app: Application, root: Path) -> dict:
    home = root / "requests"
    base = fixture(home, [(0, 0, b"")])
    jobs = []
    for key in base:
        changed = copy.deepcopy(base)
        del changed[key]
        jobs.append(changed)
    jobs += [dict(base, version=True), dict(base, version=2), dict(base, extra=1), dict(base, mode="unknown")]
    for value in ["", "\0", 12, None, "x" * 4097]:
        jobs.append(dict(base, fixture=value))
    for key, low, high in [
        ("fixture_bytes", 12, 8388608),
        ("records", 1, 256),
        ("payload_bytes", 0, 1048576),
        ("scheduled_ms", 0, 60000),
    ]:
        for value in [low - 1, high + 1, True, "1"]:
            changed = copy.deepcopy(base)
            changed["limits"][key] = value
            jobs.append(changed)
    replay_job = dict(base, mode="replay", peer={"host": "127.0.0.1", "port": 1234}, timeouts=dict(TIMEOUTS))
    for host in ["localhost", "192.0.2.1", "0.0.0.0", "127.0.0.2", "", 1]:
        changed = copy.deepcopy(replay_job)
        changed["peer"]["host"] = host
        jobs.append(changed)
    for port in [0, 65536, True, "1234"]:
        changed = copy.deepcopy(replay_job)
        changed["peer"]["port"] = port
        jobs.append(changed)
    for key in TIMEOUTS:
        for value in [0, 120001, True]:
            changed = copy.deepcopy(replay_job)
            changed["timeouts"][key] = value
            jobs.append(changed)
    for job in jobs:
        report = run(app, home, job, False)
        assert report["error"]["code"] == "invalid_input"
    for raw in [b"{", b"[]", b"null", b'{"version":1,"version":1}', b"\xff", b" " * 65537]:
        (home / "traffic-job.json").write_bytes(raw)
        result = app.run(home, {})
        assert (
            result.returncode == 2
            and json.loads(result.stdout)["error"]["code"] == "invalid_input"
            and not result.stderr
        )
    return {"invalid_requests": len(jobs), "malformed_json": 6}


def filesystem(app: Application, root: Path) -> dict:
    for kind in ["missing", "directory", "symlink", "fifo"]:
        home = root / kind
        job = fixture(home, [(0, 0, b"")])
        path = home / "input.traffic"
        path.unlink()
        if kind == "directory":
            path.mkdir()
        elif kind == "symlink":
            (home / "real").write_bytes(encode([(0, 0, b"")]))
            path.symlink_to("real")
        elif kind == "fifo":
            os.mkfifo(path)
        report = run(app, home, job, False)
        assert report["error"]["code"] == "invalid_input"
    home = root / "relative"
    job = fixture(home / "nested", [(0, 0, b"path independent of cwd")])
    (home / "nested/traffic-job.json").write_text(json.dumps(job))
    result = app.run(home, {"TRAFFIC_CONFIG": "nested/traffic-job.json"})
    assert result.returncode == 0 and not result.stderr
    verify_report(
        json.loads(result.stdout), [(0, 0, b"path independent of cwd")], (home / "nested/input.traffic").read_bytes()
    )
    return {"guarded_file_cases": 4, "config_relative_fixture_path": True}


def check(app: Application, root: Path) -> dict:
    observations = {}
    for function in [semantics, generated, malformed, failures, limits, invalid, filesystem]:
        observations[function.__name__] = function(app, root / function.__name__)
        print(app.engine + " traffic " + function.__name__ + ": passed", flush=True)
    return observations
