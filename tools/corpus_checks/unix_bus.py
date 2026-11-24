"""Independent Unix peers test framing, correlation, lifecycle and a complete native client."""

from __future__ import annotations

import concurrent.futures
import contextlib
import json
import socket
import struct
import tempfile
import threading
import time
from pathlib import Path

from .common import Application, Server


def packet(value: object) -> bytes:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    return struct.pack("!I", len(data)) + data


def request(identifier: str, op: str, args: object = None) -> dict:
    return {"id": identifier, "op": op, "args": args}


def success(identifier: str, value: object) -> dict:
    return {"id": identifier, "ok": True, "result": value}


def exact(stream: socket.socket, size: int) -> bytes:
    result = b""
    while len(result) < size:
        part = stream.recv(size - len(result))
        if not part:
            raise EOFError("truncated bus frame")
        result += part
    return result


def receive(stream: socket.socket) -> dict:
    size = struct.unpack("!I", exact(stream, 4))[0]
    assert 0 < size <= 65536
    return json.loads(exact(stream, size))


def connect(server: Server) -> socket.socket:
    stream = socket.socket(socket.AF_UNIX)
    stream.settimeout(5)
    stream.connect(server.unix_path)
    return stream


def call(stream: socket.socket, value: object) -> dict:
    stream.sendall(packet(value))
    return receive(stream)


def failure(reply: dict, identifier: str, code: str) -> None:
    assert set(reply) == {"id", "ok", "error"} and reply["id"] == identifier and reply["ok"] is False, reply
    assert set(reply["error"]) == {"code", "message"} and reply["error"]["code"] == code, reply
    assert isinstance(reply["error"]["message"], str) and reply["error"]["message"]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def setup(directory: Path, sockets: Path, name: str, **policy: int) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    config = work / "bus.json"
    config.write_text(json.dumps({"session_ms": 10000, "partial_ms": 500, **policy}))
    return work, {
        "BUS_MODE": "serve",
        "BUS_SOCKET": str(sockets / (name + ".sock")),
        "BUS_CONFIG": str(config),
        "BUS_STOP": str(work / "stop"),
        "BUS_REQUESTS": str(work / "requests.json"),
        "BUS_REPORT": str(work / "report.json"),
    }


def stop(server: Server, env: dict[str, str]) -> None:
    Path(env["BUS_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    assert not Path(env["BUS_SOCKET"]).exists()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def exercise_pair(server_app: Application, client_app: Application, directory: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="p2r-pair-") as short:
        work, env = setup(directory, Path(short), "pair")
        items = [
            request("save", "set", {"key": "note", "value": "世界\nmessage"}),
            request("load", "get", "note"),
            request("add", "sum", [8, 13, -2]),
            request("echo", "echo", {"bytes": "\u0000\u007f", "empty": []}),
            request("keys", "keys"),
        ]
        expected = [
            success("save", {"key": "note", "stored": True}),
            success("load", "世界\nmessage"),
            success("add", 19),
            success("echo", {"bytes": "\u0000\u007f", "empty": []}),
            success("keys", ["note"]),
        ]
        Path(env["BUS_REQUESTS"]).write_text(json.dumps(items, ensure_ascii=False))
        with server_app.server(work, env) as server:
            for attempt in range(2):
                result = client_app.run(work, dict(env, BUS_MODE="client"))
                assert result.returncode == 0, result.stdout + result.stderr
                assert json.loads(result.stdout) == {"ok": True, "responses": expected}
                assert json.loads(Path(env["BUS_REPORT"]).read_text()) == json.loads(result.stdout)
            stop(server, env)
        return {"commands": len(items), "replay": "identical", "cleanup": True}


def check(app: Application, directory: Path) -> dict:
    pair = exercise_pair(app, app, directory)
    with tempfile.TemporaryDirectory(prefix="p2r-bus-") as short:
        sockets = Path(short)
        work, env = setup(directory, sockets, "basic", write_bytes=1)
        with app.server(work, env) as server:
            with connect(server) as first, connect(server) as second:
                greeting = request("hello", "echo", {"text": "Привет 世界", "empty": None})
                raw = packet(greeting)
                first.sendall(raw[:2])
                time.sleep(0.01)
                first.sendall(raw[2:7])
                time.sleep(0.01)
                first.sendall(raw[7:])
                assert receive(first) == success("hello", greeting["args"])
                saved = request("put", "set", {"key": "note", "value": "hello\n世界"})
                assert call(first, saved) == success("put", {"key": "note", "stored": True})
                assert call(second, request("read", "get", "note")) == success("read", "hello\n世界")
                assert call(second, request("delete", "delete", "note")) == success("delete", "hello\n世界")
                assert call(first, saved) == success("put", {"key": "note", "stored": True})
                failure(call(second, request("absent", "get", "note")), "absent", "command")
                failure(call(first, request("put", "set", {"key": "note", "value": "changed"})), "put", "conflict")
                assert call(first, request("sum", "sum", [-1000000000000, 5, 1000000000000])) == success("sum", 5)
                bad = [
                    request("bad_sum_bool", "sum", [True]),
                    request("bad_sum_float", "sum", [1.5]),
                    request("bad_sum_large", "sum", [1000000000001]),
                    request("bad_sum_count", "sum", [0] * 129),
                    request("bad_key", "set", {"key": "../escape", "value": "x"}),
                    request("bad_value", "set", {"key": "k", "value": "x" * 4097}),
                    request("bad_escaped", "set", {"key": "k", "value": "\x00" * 700}),
                    request("bad_stop", "stop"),
                    request("bad_op", "unknown"),
                    request("bad_keys", "keys", []),
                    request("bad_stats", "stats", {}),
                    request("bad_echo", "echo", "x" * 4097),
                ]
                for value in bad:
                    failure(call(first, value), value["id"], "command")
                for value in [None, [], {}, request("", "echo"), request("世界", "echo"), request("x" * 65, "echo")]:
                    failure(call(first, value), "", "request")
                failure(call(first, {"id": "fields", "op": "echo"}), "fields", "request")
                failure(call(first, request("optype", 3)), "optype", "request")
                for payload in [b"not JSON", b"\xff"]:
                    first.sendall(struct.pack("!I", len(payload)) + payload)
                    failure(receive(first), "", "json")
                assert call(first, request("alive", "keys")) == success("alive", [])
            # Complete frames continue across the per-tick budget after EOF.
            with connect(server) as stream:
                items = [request(f"pipe{index}", "sum", [index, -2]) for index in range(25)]
                stream.sendall(b"".join(packet(row) for row in items) + b"\x00\x00")
                stream.shutdown(socket.SHUT_WR)
                for index, row in enumerate(items):
                    assert receive(stream) == success(row["id"], index - 2)
                failure(receive(stream), "", "frame")
                assert stream.recv(1) == b""

            def worker(index: int) -> list[int]:
                results = []
                with connect(server) as stream:
                    for item in range(5):
                        identifier = f"worker{index}-{item}"
                        reply = call(stream, request(identifier, "sum", [index, item]))
                        assert reply == success(identifier, index + item)
                        results.append(reply["result"])
                return results

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as workers:
                concurrent_results = list(workers.map(worker, range(8)))
            assert concurrent_results == [[index + item for item in range(5)] for index in range(8)]
            for length in [0, 16385, 0xFFFFFFFF]:
                with connect(server) as stream:
                    stream.sendall(struct.pack("!I", length))
                    failure(receive(stream), "", "frame")
                    assert stream.recv(1) == b""
            # A second server must not remove or replace the active socket.
            before = Path(env["BUS_SOCKET"]).stat().st_ino
            duplicate = app.run(work, env, timeout=5)
            assert duplicate.returncode != 0 and "LISTENING" not in duplicate.stdout
            assert Path(env["BUS_SOCKET"]).stat().st_ino == before
            with connect(server) as stream:
                assert call(stream, request("still-live", "echo", 9)) == success("still-live", 9)
            stop(server, env)
        lifecycle(app, directory, sockets)
        flow = flow_control(app, directory, sockets)
        startup = invalid_startup(app, directory, sockets)
        clients = client_checks(app, directory, sockets)
    return {
        "same_engine_pair": pair,
        "concurrent_clients": 8,
        "concurrent_replies": 40,
        "eof_pipeline": 25,
        "invalid_requests": 25,
        "flow": flow,
        "startup_rejections": startup,
        "client_checks": clients,
        "lifecycle": "graceful stop, crash recovery, active socket and replacement protection",
    }


def lifecycle(app: Application, directory: Path, sockets: Path) -> None:
    work, env = setup(directory, sockets, "lifecycle", allow_stop=1)
    with app.server(work, env) as server:
        with connect(server) as stream:
            assert call(stream, request("saved", "set", {"key": "a", "value": "b"}))["ok"]
        server.process.kill()
        server.process.wait(timeout=3)
    assert Path(env["BUS_SOCKET"]).is_socket()
    with app.server(work, env) as server, connect(server) as stream:
        assert call(stream, request("empty", "keys")) == success("empty", [])
        stream.sendall(
            packet(request("one", "echo", 1)) + packet(request("two", "echo", 2)) + packet(request("end", "stop"))
        )
        assert [receive(stream) for _ in range(3)] == [success("one", 1), success("two", 2), success("end", "stopping")]
        assert stream.recv(1) == b""
        assert server.process.wait(timeout=3) == 0 and not Path(env["BUS_SOCKET"]).exists()
    with app.server(work, env) as server:
        path = Path(env["BUS_SOCKET"])
        path.unlink()
        path.write_text("replacement")
        Path(env["BUS_STOP"]).touch()
        assert server.process.wait(timeout=3) == 0
        assert path.read_text() == "replacement"
    failed = app.run(work, env)
    assert failed.returncode != 0 and path.read_text() == "replacement"
    work, env = setup(directory, sockets, "eviction", receipts=2, keys=1)
    with app.server(work, env) as server, connect(server) as stream:
        first = request("set", "set", {"key": "a", "value": "first"})
        assert call(stream, first)["ok"]
        assert call(stream, request("update", "set", {"key": "a", "value": "second"}))["ok"]
        failure(call(stream, request("full", "set", {"key": "b", "value": "other"})), "full", "command")
        assert call(stream, first)["ok"]  # Its evicted ID executes again.
        assert call(stream, request("get", "get", "a")) == success("get", "first")
        assert call(stream, request("stats", "stats")) == success("stats", {"keys": 1, "receipts": 2})
        stop(server, env)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def flow_control(app: Application, directory: Path, sockets: Path) -> dict:
    for mode in ["partial", "session"]:
        work, env = setup(
            directory,
            sockets,
            mode,
            partial_ms=100 if mode == "partial" else 1000,
            session_ms=200 if mode == "session" else 10000,
        )
        with app.server(work, env) as server, connect(server) as stream:
            started = time.monotonic()
            if mode == "partial":
                stream.sendall(struct.pack("!I", 100))
                for _ in range(4):
                    time.sleep(0.015)
                    stream.sendall(b" ")
            else:
                for index in range(3):
                    assert call(stream, request(str(index), "echo", index)) == success(str(index), index)
                    time.sleep(0.03)
            assert stream.recv(1) == b"" and time.monotonic() - started < 0.8
            stop(server, env)
    work, env = setup(
        directory, sockets, "slow", frame_bytes=1024, value_bytes=128, queue_bytes=1028, session_ms=500, max_peers=3
    )
    with app.server(work, env) as server, connect(server) as slow:
        slow.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
        slow.setblocking(False)
        payload = b"".join(packet(request(f"slow{index}", "echo", "x" * 100)) for index in range(10000))
        offset = 0
        while offset < len(payload):
            try:
                offset += slow.send(payload[offset:])
            except BlockingIOError:
                break
        assert offset < len(payload), "fixture did not reach real backpressure"
        with connect(server) as fast:
            assert call(fast, request("fast", "sum", [2, 3])) == success("fast", 5)
        stop(server, env)
    return {"partial_deadline": True, "session_deadline": True, "real_backpressure": True, "fast_peer": 5}


def invalid_startup(app: Application, directory: Path, sockets: Path) -> int:
    bounds = {
        "max_peers": (1, 128),
        "frame_bytes": (1024, 65536),
        "queue_bytes": (1028, 262144),
        "keys": (1, 1024),
        "receipts": (1, 1024),
        "value_bytes": (1, 8192),
        "session_ms": (100, 300000),
        "partial_ms": (50, 30000),
        "drain_ms": (50, 10000),
        "write_bytes": (1, 65536),
        "allow_stop": (0, 1),
    }
    invalid = [{"unknown": 1}, [], {"keys": "1"}, {"keys": 1.5}, {"queue_bytes": 1028}, {"frame_bytes": 1024}]
    for key, (low, high) in bounds.items():
        invalid.extend([{key: low - 1}, {key: high + 1}, {key: True}])
    for index, value in enumerate(invalid):
        work, env = setup(directory, sockets, "config" + str(index))
        Path(env["BUS_CONFIG"]).write_text(json.dumps(value))
        result = app.run(work, env, timeout=5)
        assert result.returncode != 0 and "LISTENING" not in result.stdout, value
        assert not Path(env["BUS_SOCKET"]).exists()
    for name in ["BUS_SOCKET", "BUS_REPORT", "BUS_REQUESTS", "BUS_STOP"]:
        work, env = setup(directory, sockets, name)
        before = Path(env["BUS_CONFIG"]).read_bytes()
        env[name] = env["BUS_CONFIG"]
        result = app.run(work, env, timeout=5)
        assert result.returncode != 0 and "LISTENING" not in result.stdout
        assert Path(env["BUS_CONFIG"]).read_bytes() == before
    return len(invalid) + 4


def client_checks(app: Application, directory: Path, sockets: Path) -> list[str]:
    cases = ["id", "fields", "ok_type", "error_code", "oversize", "truncated", "slow", "error", "normal"]
    for mode in cases:
        work, env = setup(directory, sockets, "client_" + mode, partial_ms=100 if mode == "slow" else 500)
        Path(env["BUS_REQUESTS"]).write_text(json.dumps([request("client", "echo", "hello")]))
        report = Path(env["BUS_REPORT"])
        report.write_text("previous report")
        errors = []
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(env["BUS_SOCKET"])
            listener.listen(1)
            listener.settimeout(5)

            def respond(mode: str = mode, listener: socket.socket = listener, errors: list = errors) -> None:
                try:
                    with listener.accept()[0] as stream:
                        stream.settimeout(5)
                        assert receive(stream) == request("client", "echo", "hello")
                        answer = success("client", "hello")
                        if mode == "id":
                            answer["id"] = "other"
                        if mode == "fields":
                            answer["extra"] = True
                        if mode == "ok_type":
                            answer["ok"] = 1
                        if mode in ["error", "error_code"]:
                            answer = {
                                "id": "client",
                                "ok": False,
                                "error": {"code": "bad" if mode == "error" else "", "message": "rejected"},
                            }
                        raw = packet(answer)
                        if mode == "oversize":
                            raw = struct.pack("!I", 16385)
                        if mode == "truncated":
                            raw = raw[:-1]
                        if mode == "slow":
                            stream.sendall(raw[:4])
                            for part in raw[4:10]:
                                time.sleep(0.025)
                                with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                                    stream.sendall(bytes([part]))
                        else:
                            stream.sendall(raw[:2])
                            stream.sendall(raw[2:])
                except Exception as error:  # noqa: BLE001 - propagate fixture-thread failures
                    errors.append(repr(error))
                return  # noqa: PLR1711 - explicit return required by repository guidelines

            thread = threading.Thread(target=respond)
            thread.start()
            result = app.run(work, dict(env, BUS_MODE="client"), timeout=5)
            thread.join(timeout=6)
            assert not thread.is_alive() and not errors, errors
        if mode in ["normal", "error"]:
            assert result.returncode == (0 if mode == "normal" else 2), result.stderr
            reply = json.loads(report.read_text())
            assert reply["ok"] == (mode == "normal") and len(reply["responses"]) == 1
        else:
            assert result.returncode != 0 and report.read_text() == "previous report", (mode, result.stdout)
    return cases
