"""redis-py interoperability, an independent byte codec and state/persistence oracles."""

from __future__ import annotations

import concurrent.futures
import json
import random
import socket
import threading
import time
from pathlib import Path

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from .common import Application, Server


def packet(*args: bytes) -> bytes:
    return b"*%d\r\n" % len(args) + b"".join(b"$%d\r\n" % len(part) + part + b"\r\n" for part in args)


class Peer:
    def __init__(self, port: int) -> None:
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=4)
        self.reader = self.socket.makefile("rb")

    def close(self) -> None:
        self.reader.close()
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def read(self) -> tuple[str, object]:
        header = self.reader.readline(128)
        assert len(header) >= 3 and header.endswith(b"\r\n"), header
        tag, payload = header[:1], header[1:-2]
        if tag in {b"+", b"-"}:
            return tag.decode(), payload
        if tag == b":":
            return ":", int(payload)
        assert tag == b"$", header
        size = int(payload)
        if size == -1:
            return "$", None
        assert 0 <= size <= 65536
        value = self.reader.read(size)
        assert len(value) == size and self.reader.read(2) == b"\r\n"
        return "$", value

    def command(self, *args: bytes) -> tuple[str, object]:
        self.socket.sendall(packet(*args))
        return self.read()


def client(port: int) -> redis.Redis:
    return redis.Redis(
        host="127.0.0.1",
        port=port,
        protocol=2,
        lib_name=None,
        lib_version=None,
        socket_connect_timeout=3,
        socket_timeout=4,
        retry=Retry(NoBackoff(), 0),
    )


def fixture(work: Path, **changes: int) -> dict[str, str]:
    work.mkdir(parents=True, exist_ok=True)
    settings = {
        "max_keys": 100,
        "max_key": 256,
        "max_value": 65536,
        "max_total": 262144,
        "max_peers": 16,
        "frame_ms": 600,
        "idle_ms": 5000,
    }
    settings.update(changes)
    config = work / "kv.json"
    config.write_text(json.dumps(settings))
    (work / "clock.json").write_text("1000000")
    return {
        "KV_CONFIG": str(config),
        "KV_STATE": str(work / "state.json"),
        "KV_PORT": "0",
        "KV_CLOCK": str(work / "clock.json"),
        "KV_STOP": str(work / "stop"),
        "KV_FAULT": "",
    }


def clock(work: Path, value: int) -> None:
    (work / "clock.json").write_text(str(value))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def values(work: Path) -> dict[bytes, bytes]:
    path = work / "state.json"
    if not path.exists():
        return {}
    state = json.loads(path.read_text())
    assert state["version"] == 1
    return {bytes.fromhex(key): bytes.fromhex(value["value"]) for key, value in state["entries"].items()}


def stop(server: Server, settings: dict[str, str]) -> None:
    Path(settings["KV_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    Path(settings["KV_STOP"]).unlink()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def interoperability(app: Application, work: Path) -> dict:
    settings = fixture(work)
    binary = bytes(range(256)) * 8
    with app.server(work, settings) as server, client(server.port) as connection:
        assert connection.ping()
        assert connection.get(b"missing") is None
        assert connection.set(b"\x00\xffkey", binary)
        assert connection.get(b"\x00\xffkey") == binary
        assert connection.set(b"", b"") and connection.get(b"") == b""
        assert connection.execute_command("INCR", b"number") == 1
        assert connection.execute_command("INCR", b"number") == 2
        assert connection.get(b"number") == b"2"
        assert connection.delete(b"number", b"number", b"missing") == 1
        with connection.pipeline(transaction=False) as pipeline:
            pipeline.set(b"pipe", b"1")
            pipeline.execute_command("INCR", b"pipe")
            pipeline.get(b"pipe")
            assert pipeline.execute() == [True, 2, b"2"]
        before = (work / "state.json").read_bytes()
        connection.close()
        stop(server, settings)
    with app.server(work, settings) as server, client(server.port) as connection:
        assert (work / "state.json").read_bytes() == before
        assert connection.get(b"\x00\xffkey") == binary
        assert connection.get(b"pipe") == b"2"
        connection.close()
        stop(server, settings)
    return {"redis_py": redis.__version__, "binary_round_trip": True, "null_and_empty": True, "pipeline": True}


def model_trace(app: Application, work: Path) -> dict:
    settings = fixture(work)
    model: dict[bytes, bytes] = {}
    rng = random.Random(4024)
    with app.server(work, settings) as server, client(server.port) as connection:
        for step in range(180):
            key = bytes([rng.randrange(12)]) + b"\xff"
            operation = rng.choice(["SET", "GET", "DEL", "INCR"])
            if operation == "SET":
                value = str(rng.randrange(-100, 100)).encode() if step % 2 else rng.randbytes(rng.randrange(20))
                assert connection.set(key, value)
                model[key] = value
            elif operation == "GET":
                assert connection.get(key) == model.get(key)
            elif operation == "DEL":
                expected = int(key in model)
                assert connection.delete(key, key) == expected
                model.pop(key, None)
            else:
                current = model.get(key, b"0")
                try:
                    number = int(current)
                    valid = str(number).encode() == current and -(2**63) <= number < 2**63 - 1
                except ValueError:
                    valid = False
                if valid:
                    assert connection.execute_command("INCR", key) == number + 1
                    model[key] = str(number + 1).encode()
                else:
                    try:
                        connection.execute_command("INCR", key)
                    except redis.ResponseError:
                        pass
                    else:
                        raise AssertionError("non-integer value incremented")
            assert values(work) == model
        connection.close()
        stop(server, settings)
    return {"independent_model_steps": 180, "remaining_keys": len(model)}


def integer_errors(app: Application, work: Path) -> dict:
    settings = fixture(work)
    invalid = [
        b"",
        b"00",
        b"01",
        b"+1",
        b"-0",
        b" 1",
        b"1 ",
        b"1_0",
        b"1.0",
        b"\xff",
        b"1\x00",
        b"9223372036854775807",
        b"9223372036854775808",
        b"-9223372036854775809",
    ]
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        for value in invalid:
            assert peer.command(b"SET", b"n", value) == ("+", b"OK")
            assert peer.command(b"INCR", b"n")[0] == "-"
            assert peer.command(b"GET", b"n") == ("$", value)
        for number in [-9223372036854775808, 9223372036854775806, -1, 0]:
            assert peer.command(b"SET", b"n", str(number).encode()) == ("+", b"OK")
            assert peer.command(b"INCR", b"n") == (":", number + 1)
        errors = [
            (b"UNKNOWN",),
            (b"GET",),
            (b"GET", b"n", b"x"),
            (b"SET", b"n"),
            (b"SET", b"n", b"x", b"NX"),
            (b"DEL",),
            (b"INCR", b"n", b"1"),
            (b"SET", b"n", b"x", b"PX", b"0"),
            (b"SET", b"n", b"x", b"EX", b"2592001"),
            (b"SET", b"n", b"x", b"PX", b"-1"),
            (b"\xff",),
        ]
        before = values(work)
        for args in errors:
            assert peer.command(*args)[0] == "-"
            assert values(work) == before
        assert peer.command(b"pInG", b"\xff\x00\r\n") == ("$", b"\xff\x00\r\n")
        peer.close()
        stop(server, settings)
    return {"integer_rejections": len(invalid), "integer_edges": 4, "command_errors": len(errors)}


def expirations(app: Application, work: Path) -> dict:
    settings = fixture(work)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        assert peer.command(b"SET", b"short", b"5", b"PX", b"100") == ("+", b"OK")
        assert peer.command(b"SET", b"long", b"L", b"EX", b"1") == ("+", b"OK")
        clock(work, 1000099)
        assert peer.command(b"INCR", b"short") == (":", 6)
        assert json.loads((work / "state.json").read_text())["entries"][b"short".hex()]["expires"] == 1000100
        clock(work, 1000100)
        assert peer.command(b"GET", b"short") == ("$", None)
        assert peer.command(b"GET", b"long") == ("$", b"L")
        clock(work, 1000000)
        assert peer.command(b"GET", b"short") == ("$", None)
        assert peer.command(b"SET", b"long", b"persistent") == ("+", b"OK")
        clock(work, 1001000)
        assert peer.command(b"GET", b"long") == ("$", b"persistent")
        assert peer.command(b"SET", b"restart", b"R", b"PX", b"1") == ("+", b"OK")
        peer.close()
        stop(server, settings)
    clock(work, 1001001)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        assert peer.command(b"GET", b"restart") == ("$", None)
        assert peer.command(b"INCR", b"restart") == (":", 1)
        assert peer.command(b"DEL", b"restart", b"restart") == (":", 1)
        clock(work, 0)
        assert peer.command(b"GET", b"long") == ("$", b"persistent")
        assert peer.command(b"GET", b"restart") == ("$", None)
        peer.close()
        stop(server, settings)
    real = work / "real"
    settings = fixture(real)
    settings["KV_CLOCK"] = ""
    with app.server(real, settings) as server, client(server.port) as connection:
        assert connection.set(b"real", b"time", px=120)
        assert connection.get(b"real") == b"time"
        time.sleep(0.18)
        assert connection.get(b"real") is None
        connection.close()
        stop(server, settings)
    return {
        "exact_deadline": True,
        "incr_keeps_ttl": True,
        "set_clears_ttl": True,
        "rollback_and_restart": True,
        "real_clock": True,
    }


def framing(app: Application, work: Path) -> dict:
    settings = fixture(work)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        encoded = packet(b"SET", b"binary", b"\xff\x00\r\n*2\r\n$-1\r\n")
        for byte in encoded:
            peer.socket.sendall(bytes([byte]))
        assert peer.read() == ("+", b"OK")
        assert peer.command(b"GET", b"binary") == ("$", b"\xff\x00\r\n*2\r\n$-1\r\n")
        for malformed_command in [
            b"*0\r\n",
            b"*-1\r\n",
            b"$-1\r\n",
            b"+PING\r\n",
            b":7\r\n",
            b"*1\r\n*1\r\n$4\r\nPING\r\n",
            b"*1\r\n$-1\r\n",
        ]:
            peer.socket.sendall(malformed_command)
            assert peer.read()[0] == "-"
            assert peer.command(b"PING") == ("+", b"PONG")
        peer.socket.sendall(packet(b"PING") * 80)
        peer.socket.shutdown(socket.SHUT_WR)
        assert [peer.read() for _ in range(80)] == [("+", b"PONG")] * 80
        assert peer.reader.read(1) == b""
        peer.close()
        bad_frames = [
            b"!bad\r\n",
            b"*-2\r\n",
            b"*65\r\n",
            b"$65537\r\n",
            b"$1\r\nx!!",
            b"*1\r\n$3\r\nX",
            b"*x\r\n",
            b":9223372036854775808\r\n",
            b"*1\r\n" * 9 + b"$0\r\n\r\n",
            b"*1\n",
            b"*" + b"9" * 65,
            b"*2\r\n" + (b"*64\r\n" + b"$0\r\n\r\n" * 64) * 2,
            b"*3\r\n" + (b"$65536\r\n" + b"x" * 65536 + b"\r\n") * 2 + b"$65536\r\n",
        ]
        before = values(work)
        for data in bad_frames:
            peer = Peer(server.port)
            peer.socket.sendall(data)
            peer.socket.shutdown(socket.SHUT_WR)
            assert peer.read()[0] == "-"
            peer.close()
            assert values(work) == before
        healthy = Peer(server.port)
        assert healthy.command(b"PING") == ("+", b"PONG")
        healthy.close()
        peer = Peer(server.port)
        peer.socket.sendall(packet(b"PING") + b"!bad\r\n")
        assert peer.read() == ("+", b"PONG")
        assert peer.read()[0] == "-"
        assert peer.reader.read(1) == b""
        peer.close()
        stop(server, settings)
    return {
        "fragmented_binary": True,
        "noncommand_frames": 7,
        "malformed_frames": len(bad_frames),
        "half_closed_pipeline": 80,
    }


def concurrency(app: Application, work: Path) -> dict:
    settings = fixture(work, frame_ms=3000)
    with app.server(work, settings) as server:

        def worker() -> list[int]:
            with client(server.port) as connection:
                return [connection.execute_command("INCR", b"counter") for _ in range(30)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(worker) for _ in range(4)]
            results = [number for future in futures for number in future.result(timeout=15)]
        assert sorted(results) == list(range(1, 121))
        stop(server, settings)
    folder = work / "nonreader"
    settings = fixture(folder, max_peers=2, frame_ms=3000)
    with app.server(folder, settings) as server:
        slow = Peer(server.port)
        assert slow.command(b"PING") == ("+", b"PONG")
        slow.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        flood = packet(b"PING", b"z" * 65536) * 40
        sent = threading.Event()

        def nonreader() -> None:
            try:
                slow.socket.sendall(flood)
            except OSError:
                pass
            sent.set()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        writer = threading.Thread(target=nonreader, daemon=True)
        writer.start()
        healthy = Peer(server.port)
        began = time.monotonic()
        for index in range(12):
            assert healthy.command(b"INCR", b"counter") == (":", 1 + index)
        assert time.monotonic() - began < 3.0
        admitted = False
        while time.monotonic() - began < 2.5 and not admitted:
            probe = Peer(server.port)
            try:
                admitted = probe.command(b"PING") == ("+", b"PONG")
            except (OSError, AssertionError):
                pass
            finally:
                probe.close()
            assert healthy.command(b"PING") == ("+", b"PONG")
            if not admitted:
                time.sleep(0.02)
        assert admitted, "nonreader must release its slot before the frame or idle deadline"
        healthy.close()
        try:
            slow.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        slow.close()
        writer.join(timeout=5)
        assert sent.is_set() and values(folder)[b"counter"] == b"12"
        stop(server, settings)
    return {
        "concurrent_increments": 120,
        "unique_results": True,
        "healthy_during_nonreader": 12,
        "nonreader_evicted": True,
    }


def limits(app: Application, work: Path) -> dict:
    settings = fixture(work, max_keys=2, max_key=4, max_value=32, max_total=64, max_peers=2, frame_ms=100, idle_ms=400)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        assert peer.command(b"SET", b"a", b"x" * 32) == ("+", b"OK")
        assert peer.command(b"SET", b"b", b"y" * 31)[0] == "-"
        assert peer.command(b"SET", b"b", b"y" * 30) == ("+", b"OK")
        assert peer.command(b"SET", b"c", b"z")[0] == "-"
        assert peer.command(b"SET", b"a", b"smaller") == ("+", b"OK")
        assert peer.command(b"SET", b"large", b"x")[0] == "-"
        assert peer.command(b"SET", b"a", b"x" * 33)[0] == "-"
        assert peer.command(b"DEL", b"b") == (":", 1)
        assert peer.command(b"INCR", b"c") == (":", 1)
        slow = Peer(server.port)
        excess = Peer(server.port)
        assert excess.socket.recv(1) == b""
        excess.close()
        began = time.monotonic()
        for index in range(8):
            try:
                slow.socket.sendall(b"*")
            except OSError:
                break
            assert peer.command(b"PING") == ("+", b"PONG")
            time.sleep(0.03)
        try:
            assert slow.reader.read(1) == b""
        except ConnectionResetError:
            pass
        assert time.monotonic() - began < 0.8
        slow.close()
        peer.close()
        idle = Peer(server.port)
        assert idle.reader.read(1) == b""
        idle.close()
        stop(server, settings)
    return {
        "byte_capacity": True,
        "key_capacity": True,
        "key_value_limits": True,
        "partial_deadline": True,
        "idle_deadline": True,
    }


def recovery(app: Application, work: Path) -> dict:
    for boundary in ["before_checkpoint", "after_checkpoint", "after_reply"]:
        folder = work / boundary
        settings = fixture(folder)
        with app.server(folder, dict(settings, KV_FAULT=boundary)) as server:
            peer = Peer(server.port)
            peer.socket.sendall(packet(b"SET", b"durable", b"\xff\x00"))
            if boundary == "after_reply":
                assert peer.read() == ("+", b"OK")
            else:
                assert peer.reader.read(1) == b""
            assert server.process.wait(timeout=3) == 75
            peer.close()
        expected = {} if boundary == "before_checkpoint" else {b"durable": b"\xff\x00"}
        assert values(folder) == expected
        with app.server(folder, settings) as server:
            peer = Peer(server.port)
            assert peer.command(b"GET", b"durable") == ("$", expected.get(b"durable"))
            assert peer.command(b"INCR", b"continued") == (":", 1)
            peer.close()
            stop(server, settings)
    folder = work / "kill"
    settings = fixture(folder)
    with app.server(folder, settings) as server:
        peer = Peer(server.port)
        assert peer.command(b"SET", b"before", b"B") == ("+", b"OK")
        peer.socket.sendall(packet(b"SET", b"partial", b"incomplete")[:-3])
        server.process.kill()
        assert server.process.wait(timeout=3) != 0
        peer.close()
    with app.server(folder, settings) as server:
        assert values(folder) == {b"before": b"B"}
        stop(server, settings)
    return {"checkpoint_boundaries": 3, "real_process_kill": True}


def corruption(app: Application, work: Path) -> dict:
    settings = fixture(work)
    with app.server(work, settings) as server:
        peer = Peer(server.port)
        assert peer.command(b"SET", b"key", b"value") == ("+", b"OK")
        peer.close()
        stop(server, settings)
    path = work / "state.json"
    original = path.read_bytes()
    key = b"key".hex()
    variants = [b"{", json.dumps({"version": 2, "clock_ms": 0, "entries": {}}).encode()]
    for field, value in [("expires", True), ("expires", 1), ("value", "0"), ("value", "FF")]:
        state = json.loads(original)
        state["entries"][key][field] = value
        variants.append(json.dumps(state).encode())
    for content in variants:
        path.write_bytes(content)
        assert app.run(work, settings).returncode != 0 and path.read_bytes() == content
    path.unlink()
    external = work / "external.json"
    external.write_bytes(original)
    path.symlink_to(external)
    assert app.run(work, settings).returncode != 0 and external.read_bytes() == original
    path.unlink()
    assert app.run(work, dict(settings, KV_STATE=settings["KV_CONFIG"])).returncode != 0
    return {"malformed_snapshots": len(variants), "protected_paths": 2}


def invalid_configuration(app: Application, work: Path) -> int:
    variants = [
        {"max_keys": 0},
        {"max_key": 257},
        {"max_value": 31},
        {"max_total": 63},
        {"max_peers": 33},
        {"frame_ms": 49},
        {"idle_ms": 300001},
        {"max_keys": True},
        {"max_keys": 1.5},
        {"unknown": 1},
    ]
    for index, variant in enumerate(variants):
        folder = work / str(index)
        settings = fixture(folder, **variant)
        assert app.run(folder, settings).returncode != 0
    folder = work / "clock"
    settings = fixture(folder)
    for bad in ["-1", "true", "253402214400001", "1.5", "{broken"]:
        (folder / "clock.json").write_text(bad)
        assert app.run(folder, settings).returncode != 0
    return len(variants) + 5


def check(app: Application, work: Path) -> dict:
    assert redis.__version__ == "6.4.0", "install the pinned corpus-checks extra"
    return {
        "interoperability": interoperability(app, work / "interop"),
        "model": model_trace(app, work / "model"),
        "integers": integer_errors(app, work / "integers"),
        "expirations": expirations(app, work / "expirations"),
        "framing": framing(app, work / "framing"),
        "concurrency": concurrency(app, work / "concurrency"),
        "limits": limits(app, work / "limits"),
        "recovery": recovery(app, work / "recovery"),
        "corruption": corruption(app, work / "corruption"),
        "invalid_configuration": invalid_configuration(app, work / "invalid"),
    }
