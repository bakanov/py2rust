"""Independent wire framing, durable receipt, corruption and interruption checks."""

from __future__ import annotations

import copy
import json
import socket
import socketserver
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import Application, Server


def wire(value: object) -> bytes:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return struct.pack("!I", len(body)) + body


def exact(peer: socket.socket, length: int) -> bytes:
    result = bytearray()
    while len(result) < length:
        chunk = peer.recv(length - len(result))
        assert chunk, "peer closed before its entire reply arrived"
        result.extend(chunk)
    return bytes(result)


def response(peer: socket.socket, maximum: int = 2048) -> dict:
    size = struct.unpack("!I", exact(peer, 4))[0]
    assert 1 <= size <= maximum
    return json.loads(exact(peer, size))


def connect(server: Server) -> socket.socket:
    return socket.create_connection(("127.0.0.1", server.port), timeout=3)


def request(server: Server, value: object) -> dict:
    with connect(server) as peer:
        peer.sendall(wire(value))
        return response(peer)


def setup(directory: Path, name: str, **policy: int) -> tuple[Path, dict[str, str], Path]:
    work = directory / name
    work.mkdir()
    config = work / "config.json"
    config.write_text(
        json.dumps(
            {
                "max_jobs": 8,
                "max_payload": 512,
                "max_frame": 2048,
                "frame_timeout_ms": 500,
                "connection_frames": 32,
                **policy,
            }
        )
    )
    state = work / "state.json"
    return (
        work,
        {
            "BROKER_CONFIG": str(config),
            "BROKER_STATE": str(state),
            "BROKER_PORT": "0",
            "BROKER_SHUTDOWN": str(work / "stop"),
            "BROKER_STOP": "",
            "BROKER_MODE": "serve",
        },
        state,
    )


def receipt(identifier: str, sequence: int, state: str = "pending", duplicate: bool = False) -> dict:
    return {"ok": True, "id": identifier, "sequence": sequence, "state": state, "duplicate": duplicate}


def check(app: Application, directory: Path) -> dict:
    work, env, state = setup(directory, "wire")
    alpha = {"op": "submit", "id": "alpha", "payload": {"text": "Hello 世界\n\u0000 😀", "data": [None, True, 1]}}
    beta = {"op": "submit", "id": "beta", "payload": None}
    with app.server(work, env) as server:
        assert server.scheme == "tcp"
        with connect(server) as peer:
            # Deliberately split both length and a multibyte UTF-8 code point.
            raw = wire(alpha)
            split = raw.index("世".encode()) + 1
            for chunk in [raw[:1], raw[1:3], raw[3:split], raw[split : split + 1], raw[split + 1 :]]:
                peer.sendall(chunk)
                time.sleep(0.01)
            assert response(peer) == receipt("alpha", 1)
            peer.sendall(wire(beta) + wire({"op": "ack", "id": "alpha"}) + wire({"op": "get", "id": "alpha"}))
            assert response(peer) == receipt("beta", 2)
            assert response(peer) == receipt("alpha", 1, "done")
            stored_alpha = response(peer)["job"]
            assert stored_alpha == {"id": "alpha", "sequence": 1, "state": "done", "payload": alpha["payload"]}
            # A receiving half-close does not discard the final queued command.
            peer.sendall(wire({"op": "pending"}))
            peer.shutdown(socket.SHUT_WR)
            assert response(peer) == {
                "ok": True,
                "jobs": [{"id": "beta", "payload": None, "sequence": 2, "state": "pending"}],
                "next": 2,
                "more": False,
            }
            assert peer.recv(1) == b""
        saved = state.read_bytes()
        assert request(server, alpha) == receipt("alpha", 1, "done", True)
        assert request(server, {"op": "ack", "id": "alpha"}) == receipt("alpha", 1, "done", True)
        assert request(server, dict(alpha, payload=True)) == {"ok": False, "error": "id_conflict"}
        assert request(server, {"op": "get", "id": "missing"}) == {"ok": False, "error": "not_found"}
        assert request(server, {"op": "ack", "id": "missing"}) == {"ok": False, "error": "not_found"}
        assert request(server, {"op": "unknown"}) == {"ok": False, "error": "unknown_operation"}
        bad_requests = [
            [],
            {},
            {"op": 1},
            {"op": "stats", "extra": 1},
            dict(beta, id="bad id"),
            dict(beta, id="big", payload="x" * 512),
            {"op": "ack"},
            {"op": "pending", "after": -1},
            {"op": "pending", "limit": True},
            {"op": "pending", "limit": 101},
        ]
        for value in bad_requests:
            assert request(server, value) == {"ok": False, "error": "request_failed"}
        for body in [b"{", b"\xff", b'{"op":"stats"} trailing', b'{"op":"submit","id":"nan","payload":NaN}']:
            with connect(server) as peer:
                peer.sendall(struct.pack("!I", len(body)) + body + wire({"op": "stats"}))
                assert response(peer) == {"ok": False, "error": "invalid_json"}
                assert response(peer)["accepted"] == 2
        # Fatal framing errors close only this peer and never allocate the claimed oversized body.
        frames = [
            struct.pack("!I", 0),
            struct.pack("!I", 2049),
            struct.pack("!I", 0xFFFFFFFF),
            b"\x00\x00",
            struct.pack("!I", 20) + b"{}",
        ]
        for raw in frames:
            with connect(server) as peer:
                peer.sendall(raw)
                peer.shutdown(socket.SHUT_WR)
                assert response(peer) == {"ok": False, "error": "frame_error"}
                assert peer.recv(1) == b""
        with connect(server) as peer:
            peer.shutdown(socket.SHUT_WR)
            assert peer.recv(1) == b""
        assert state.read_bytes() == saved
        stats = request(server, {"op": "stats"})
        assert stats == {"ok": True, "accepted": 2, "pending": 1, "done": 1, "next_sequence": 3, "capacity": 8}
        # Corruption during service is reported without rewriting or resetting the snapshot.
        corrupt = json.loads(saved)
        corrupt["next_sequence"] = 100
        state.write_text(json.dumps(corrupt))
        before = state.read_bytes()
        assert request(server, beta) == {"ok": False, "error": "request_failed"}
        assert state.read_bytes() == before
        state.write_bytes(saved)
    with app.server(work, env) as server:
        assert request(server, {"op": "stats"}) == stats
        assert request(server, {"op": "get", "id": "alpha"})["job"] == stored_alpha
        assert request(server, beta) == receipt("beta", 2, duplicate=True)
        peer = connect(server)
        peer.sendall(struct.pack("!I", 400) + b'{"op":')
        assert server.process.poll() is None
        # Leave the peer open while the context kills the actual broker.
    peer.close()
    assert state.read_bytes() == saved
    with app.server(work, env) as server:
        assert request(server, {"op": "stats"}) == stats

    work, env, state = setup(directory, "pages", max_jobs=4, max_frame=1024)
    jobs = [{"op": "submit", "id": "job-" + str(i), "payload": "x" * 450} for i in range(4)]
    with app.server(work, env) as server:
        for i, job in enumerate(jobs):
            assert request(server, job) == receipt(job["id"], i + 1)
        cursor = 0
        received = []
        while True:
            page = request(server, {"op": "pending", "after": cursor, "limit": 100})
            assert len(wire(page)) - 4 <= 1024 and len(page["jobs"]) == 1
            received.extend(page["jobs"])
            assert page["next"] > cursor
            cursor = page["next"]
            if not page["more"]:
                break
        assert [row["id"] for row in received] == [row["id"] for row in jobs]
        assert request(server, {"op": "pending", "after": 100}) == {"ok": True, "jobs": [], "next": 100, "more": False}
        assert request(server, {"op": "ack", "id": "job-1"}) == receipt("job-1", 2, "done")
        assert request(server, {"op": "submit", "id": "overflow", "payload": 0}) == {"ok": False, "error": "capacity"}
        assert request(server, jobs[1]) == receipt("job-1", 2, "done", True)
        assert [request(server, {"op": "pending", "after": after, "limit": 1})["next"] for after in [0, 1, 3]] == [
            1,
            3,
            4,
        ]
        before = state.read_bytes()
    with app.server(work, env) as server:
        assert request(server, {"op": "stats"})["accepted"] == 4 and state.read_bytes() == before

    work, env, state = setup(directory, "connection-limit", connection_frames=2)
    with app.server(work, env) as server:
        with connect(server) as peer:
            peer.sendall(wire({"op": "stats"}) * 2)
            assert response(peer)["accepted"] == 0 and response(peer)["accepted"] == 0
            assert peer.recv(1) == b""
        assert request(server, {"op": "stats"})["accepted"] == 0

    work, env, state = setup(directory, "deadline", frame_timeout_ms=160)
    with app.server(work, env) as server:
        with connect(server) as peer:
            stop = threading.Event()

            def drip() -> None:
                try:
                    for byte in wire(dict(alpha, payload="x" * 300)):
                        peer.sendall(bytes([byte]))
                        if stop.wait(0.04):
                            break
                except OSError:
                    pass
                return  # noqa: PLR1711 - explicit return required by repository guidelines

            with ThreadPoolExecutor(max_workers=1) as pool:
                began = time.monotonic()
                future = pool.submit(drip)
                try:
                    assert response(peer) == {"ok": False, "error": "frame_error"}
                    assert time.monotonic() - began < 0.6, "deadline was reset by partial reads"
                finally:
                    stop.set()
                future.result(timeout=1)
        assert not state.exists() and request(server, {"op": "stats"})["accepted"] == 0
        Path(env["BROKER_SHUTDOWN"]).touch()
        assert server.process.wait(timeout=2) == 0
        try:
            peer = connect(server)
        except ConnectionRefusedError:
            pass
        else:
            peer.close()
            raise AssertionError("listener survived graceful shutdown")

    faults = interruptions(app, directory)
    rejected = invalid_inputs(app, directory)
    client = client_checks(app, directory)
    return {
        "wire": ["fragmented length", "split UTF-8", "coalesced commands", "half-close", "fatal frame isolation"],
        "stats_after_restart": stats,
        "pending_pages": 4,
        "capacity_retains_done_ids": True,
        "invalid_requests": len(bad_requests),
        "invalid_json": 4,
        "invalid_frames": len(frames),
        "absolute_frame_deadline": True,
        "graceful_stop": True,
        "connection_limit": 2,
        "interruptions": faults,
        "invalid_startup": rejected,
        "client": client,
    }


def client_checks(app: Application, directory: Path) -> dict:
    calls = []
    connections = []

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            connections.append(1)
            for _ in range(2):
                first = self.request.recv(4)
                if not first:
                    return
                size = struct.unpack("!I", first + exact(self.request, 4 - len(first)))[0]
                assert 1 <= size <= 2048
                command = json.loads(exact(self.request, size))
                calls.append(command)
                if command["op"] == "truncate":
                    self.request.sendall(struct.pack("!I", 100) + b"{")
                    return
                self.request.sendall(wire({"ok": command["op"] != "fail", "seen": command}))
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            work, env, state = setup(directory, "client", connection_frames=2)
            batch = work / "requests.json"
            output = work / "responses.json"
            commands = [
                {"op": "first", "text": "Hello 世界"},
                {"op": "fail"},
                {"op": "third"},
                {"op": "fourth"},
                {"op": "last"},
            ]
            batch.write_text(json.dumps(commands))
            settings = dict(
                env,
                BROKER_MODE="client",
                BROKER_HOST="127.0.0.1",
                BROKER_PORT=str(server.server_address[1]),
                BROKER_REQUESTS=str(batch),
                BROKER_REPORT=str(output),
            )
            process = app.run(work, settings)
            assert process.returncode == 1, process.stderr
            assert json.loads(process.stdout) == {"responses": 5, "errors": 1}
            assert json.loads(output.read_text()) == {
                "phase": "finished",
                "errors": 1,
                "requested": 5,
                "responses": [{"ok": command["op"] != "fail", "seen": command} for command in commands],
            }
            assert calls == commands and len(connections) == 3 and not state.exists()
            batch.write_text(json.dumps([{"op": "first"}, {"op": "truncate"}, {"op": "unsent"}]))
            assert app.run(work, settings).returncode != 0
            assert json.loads(output.read_text()) == {
                "phase": "running",
                "requested": 3,
                "responses": [{"ok": True, "seen": {"op": "first"}}],
            }
            assert calls[-2:] == [{"op": "first"}, {"op": "truncate"}]
            before = output.read_bytes()
            for invalid in [[], [{"op": "stats"}] * 101, [{"op": "first", "text": "x" * 2048}]]:
                batch.write_text(json.dumps(invalid))
                assert app.run(work, settings).returncode != 0 and output.read_bytes() == before
            batch.write_text(json.dumps([{"op": "first"}]))
            preserved = batch.read_bytes()
            assert app.run(work, dict(settings, BROKER_REPORT=str(batch))).returncode != 0
            assert batch.read_bytes() == preserved
            assert len(calls) == 7
        finally:
            server.shutdown()
            thread.join(timeout=3)
    return {"responses": 5, "errors": 1, "connections": 3, "partial_receipts_retained": 1, "invalid_batches": 4}


def interruptions(app: Application, directory: Path) -> dict:
    results = {}
    for operation in ["submit", "ack"]:
        for point in ["before_checkpoint", "after_checkpoint", "after_reply"]:
            work, env, state = setup(directory, operation + "-" + point)
            initial = {"op": "submit", "id": "first", "payload": {"text": "stored"}}
            with app.server(work, env) as server:
                assert request(server, initial) == receipt("first", 1)
            command = {"op": "ack", "id": "first"} if operation == "ack" else dict(initial, id="second")
            with app.server(work, dict(env, BROKER_STOP=point)) as server:
                with connect(server) as peer:
                    peer.sendall(wire(command))
                    if point == "after_reply":
                        acknowledged = response(peer)
                        expected = receipt("first", 1, "done") if operation == "ack" else receipt("second", 2)
                        assert acknowledged == expected
                    else:
                        assert peer.recv(1) == b""
                assert server.process.wait(timeout=3) == 75
            snapshot = json.loads(state.read_text())
            committed = point != "before_checkpoint"
            assert len(snapshot["jobs"]) == (2 if operation == "submit" and committed else 1)
            assert snapshot["jobs"][0]["state"] == ("done" if operation == "ack" and committed else "pending")
            with app.server(work, env) as server:
                expected = (
                    receipt("first", 1, "done", committed)
                    if operation == "ack"
                    else receipt("second", 2, duplicate=committed)
                )
                assert request(server, command) == expected
                assert request(server, command) == dict(expected, duplicate=True)
            results[operation + ":" + point] = {"committed_before_restart": committed, "duplicate_on_replay": committed}
    return results


def invalid_inputs(app: Application, directory: Path) -> int:
    rejected = 0
    for key, value in [
        ("max_jobs", 0),
        ("max_jobs", 1001),
        ("max_jobs", True),
        ("max_payload", 4097),
        ("max_frame", 1023),
        ("max_frame", 65537),
        ("frame_timeout_ms", 49),
        ("connection_frames", 0),
        ("connection_frames", 101),
        ("unknown", 1),
    ]:
        work, env, state = setup(directory, "bad-config-" + str(rejected))
        path = Path(env["BROKER_CONFIG"])
        config = json.loads(path.read_text())
        config[key] = value
        path.write_text(json.dumps(config))
        assert app.run(work, env, timeout=3).returncode != 0 and not state.exists()
        rejected += 1
    valid = {
        "format": 1,
        "policy": {"max_jobs": 8, "max_payload": 512},
        "next_sequence": 2,
        "jobs": [{"id": "one", "payload": None, "sequence": 1, "state": "pending"}],
    }
    corruptions = []
    for key, value in [("format", True), ("next_sequence", 3), ("jobs", []), ("extra", 1)]:
        corruptions.append(dict(valid, **{key: value}))
    for key, value in [("id", "bad id"), ("sequence", 2), ("state", "lost"), ("payload", "x" * 513)]:
        broken = copy.deepcopy(valid)
        broken["jobs"][0][key] = value
        corruptions.append(broken)
    corruptions.append(dict(valid, jobs=valid["jobs"] * 2, next_sequence=3))
    corruptions.append(dict(valid, policy={"max_jobs": 9, "max_payload": 512}))
    for broken in corruptions:
        work, env, state = setup(directory, "bad-state-" + str(rejected))
        state.write_text(json.dumps(broken))
        before = state.read_bytes()
        assert app.run(work, env, timeout=3).returncode != 0 and state.read_bytes() == before
        rejected += 1
    for mode in ["same", "symlink", "hardlink", "shutdown", "bad-port"]:
        work, env, state = setup(directory, "paths-" + mode)
        config = Path(env["BROKER_CONFIG"])
        before = config.read_bytes()
        if mode == "same":
            env["BROKER_STATE"] = str(config)
        elif mode == "symlink":
            state.symlink_to(config)
        elif mode == "hardlink":
            state.hardlink_to(config)
        elif mode == "shutdown":
            env["BROKER_SHUTDOWN"] = str(state)
        else:
            env["BROKER_PORT"] = "65536"
        assert app.run(work, env, timeout=3).returncode != 0 and config.read_bytes() == before
        rejected += 1
    return rejected
