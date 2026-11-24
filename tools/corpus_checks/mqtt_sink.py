"""Paho interoperability and independent MQTT byte/state models for the telemetry sink."""

from __future__ import annotations

import contextlib
import copy
import json
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paho.mqtt.client as mqtt

from .common import Application, Server


def packet(kind: int, body: bytes = b"") -> bytes:
    length = len(body)
    header = bytearray([kind])
    while True:
        digit = length % 128
        length //= 128
        header.append(digit | (128 if length else 0))
        if not length:
            return bytes(header) + body


def field(data: bytes) -> bytes:
    return struct.pack("!H", len(data)) + data


def connect_packet(client: bytes = b"raw", keepalive: int = 0, flags: int = 2, extra: bytes = b"") -> bytes:
    return packet(16, b"\x00\x04MQTT\x04" + bytes([flags]) + struct.pack("!H", keepalive) + field(client) + extra)


def publish_packet(topic: bytes, payload: bytes, retain: bool = False) -> bytes:
    return packet(49 if retain else 48, field(topic) + payload)


class Raw:
    def __init__(self, server: Server) -> None:
        self.socket = socket.create_connection(("127.0.0.1", server.port), timeout=4)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def expect(self, expected: bytes) -> None:
        received = b""
        while len(received) < len(expected):
            chunk = self.socket.recv(len(expected) - len(received))
            assert chunk, (received, expected)
            received += chunk
        assert received == expected, (received, expected)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def connect(self, client: bytes = b"raw", keepalive: int = 0) -> None:
        self.socket.sendall(connect_packet(client, keepalive))
        self.expect(b"\x20\x02\x00\x00")
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def ping(self) -> None:
        self.socket.sendall(b"\xc0\x00")
        self.expect(b"\xd0\x00")
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def publish(self, topic: bytes, payload: bytes, retain: bool = False) -> None:
        # PING on the same connection is an ordered observation barrier after the
        # QoS-0 publication. It isn't a delivery acknowledgement in the protocol.
        self.socket.sendall(publish_packet(topic, payload, retain) + b"\xc0\x00")
        self.expect(b"\xd0\x00")
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def eof(self, reset: bool = False) -> None:
        try:
            assert self.socket.recv(1) == b""
        except ConnectionResetError:
            assert reset
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def close(self) -> None:
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


class Paho:
    def __init__(self, server: Server, name: str) -> None:
        self.connected = threading.Event()
        self.failure = None
        self.peer = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=name,
            clean_session=True,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=False,
        )
        self.peer.on_connect = self.on_connect
        assert self.peer.connect("127.0.0.1", server.port, keepalive=2) == mqtt.MQTT_ERR_SUCCESS
        self.peer.loop_start()
        assert self.connected.wait(4) and not self.failure, self.failure
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def on_connect(
        self, client: mqtt.Client, userdata: object, flags: object, reason: object, properties: object
    ) -> None:
        self.failure = reason.is_failure
        self.connected.set()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def publish(self, topic: str, payload: bytes, retain: bool = False) -> None:
        result = self.peer.publish(topic, payload, qos=0, retain=retain)
        assert result.rc == mqtt.MQTT_ERR_SUCCESS
        result.wait_for_publish(timeout=4)
        assert result.is_published()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def close(self) -> None:
        self.peer.disconnect()
        self.peer.loop_stop()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def setup(directory: Path, name: str, **policy: int) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    config = work / "sink.json"
    config.write_text(json.dumps({"close_ms": 150, **policy}))
    return work, {
        "MQTT_CONFIG": str(config),
        "MQTT_STATE": str(work / "state.json"),
        "MQTT_PORT": "0",
        "MQTT_STOP": str(work / "stop"),
        "MQTT_MODE": "serve",
        "MQTT_FAULT": "",
    }


def state(env: dict[str, str], sequence: int) -> dict:
    deadline = time.monotonic() + 5
    result = {}
    while time.monotonic() < deadline:
        if Path(env["MQTT_STATE"]).exists():
            result = json.loads(Path(env["MQTT_STATE"]).read_text())
            if result["sequence"] == sequence:
                return result
        time.sleep(0.01)
    raise AssertionError((sequence, result))


def record(model: dict, topic: str, payload: bytes, client: str, retain: bool = False, history: int = 3) -> dict:
    model = copy.deepcopy(model)
    model["sequence"] += 1
    entry = model["topics"].setdefault(topic, {"history": [], "retained": ""})
    entry["history"].append(
        {"sequence": model["sequence"], "client": client, "payload": payload.hex(), "retain": retain}
    )
    entry["history"] = entry["history"][-history:]
    if retain:
        entry["retained"] = payload.hex()
    return model


def stop(server: Server, env: dict[str, str]) -> None:
    Path(env["MQTT_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def report(app: Application, work: Path, env: dict[str, str]) -> dict:
    result = app.run(work, dict(env, MQTT_MODE="report"))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def drip(peer: Raw, data: bytes, stopped: threading.Event) -> None:
    for _ in range(75):
        if stopped.wait(0.02):
            break
        try:
            peer.socket.sendall(data)
        except OSError:
            break
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    empty = {"version": 1, "sequence": 0, "topics": {}}
    work, env = setup(directory, "paho", history=3, payload_bytes=65536)
    model = empty
    assert report(app, work, env) == empty
    with app.server(work, env) as server, contextlib.closing(Paho(server, "sensor-one")) as publisher:
        cases = [
            ("sensors/温度", b"21.5", False),
            ("raw/binary", bytes(range(256)), True),
            ("/empty//level/", b"", False),
            ("\ufeffkept", b"BOM topic", False),
            ("$SYS/local", b"local status", False),
            ("sensors/温度", "23° 😀".encode(), True),
            ("sensors/温度", b"latest", False),
            ("sensors/温度", b"newest", False),
            ("sensors/温度", b"", True),
            ("raw/binary", b"x" * 65536, False),
        ]
        for topic, data, retain in cases:
            publisher.publish(topic, data, retain)
            model = record(model, topic, data, "sensor-one", retain)
            assert state(env, model["sequence"]) == model
        # Paho's own keep-alive PING/PINGRESP loop preserves this connection.
        time.sleep(3.4)
        publisher.publish("sensors/温度", b"after automatic ping")
        model = record(model, "sensors/温度", b"after automatic ping", "sensor-one")
        assert state(env, model["sequence"]) == model
        stop(server, env)
    assert report(app, work, env) == model
    Path(env["MQTT_STOP"]).unlink()
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        peer.connect(b"restart")
        peer.publish(b"restart", b"persisted")
        model = record(model, "restart", b"persisted", "restart")
        assert state(env, model["sequence"]) == model
        # Actual process termination with a partly received next PUBLISH never
        # commits that incomplete packet and never damages previous checkpoints.
        partial = publish_packet(b"interrupted", b"not committed" * 100)
        peer.socket.sendall(partial[:-20])
        time.sleep(0.04)
        server.process.kill()
        server.process.wait(timeout=3)
    assert report(app, work, env) == model
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        peer.connect(b"after-kill")
        peer.publish(b"restart", b"after kill")
        model = record(model, "restart", b"after kill", "after-kill")
        assert state(env, model["sequence"]) == model
        stop(server, env)
    work, env = setup(directory, "framing", history=3, packets_per_tick=2, write_bytes=1)
    model = empty
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        hello = connect_packet("клиент".encode())
        boundary = hello.index("к".encode()) + 1
        peer.socket.sendall(hello[:boundary])
        time.sleep(0.02)
        peer.socket.sendall(hello[boundary:] + publish_packet(b"coalesced", b"first") + b"\xc0\x00")
        peer.expect(b"\x20\x02\x00\x00\xd0\x00")
        model = record(model, "coalesced", b"first", "клиент")
        # Remaining lengths at both one/two- and two/three-byte boundaries.
        for size in [123, 124, 16379, 16380]:
            data = bytes([size % 251]) * size
            encoded = publish_packet(b"ab", data)
            peer.socket.sendall(encoded[:2])
            time.sleep(0.005)
            peer.socket.sendall(encoded[2:] + b"\xc0\x00")
            peer.expect(b"\xd0\x00")
            model = record(model, "ab", data, "клиент")
        assert state(env, model["sequence"]) == model
        peer.socket.sendall(b"\xc0\x00" * 30)
        peer.expect(b"\xd0\x00" * 30)
        peer.socket.sendall(b"\xe0\x00")
        peer.eof()
        stop(server, env)
    # Unsupported CONNECT options get a refusal; malformed fields get no reply.
    work, env = setup(directory, "rejections")
    refused = [
        (connect_packet().replace(b"MQTT\x04", b"MQTT\x05"), 1),
        (connect_packet(b""), 2),
        (connect_packet(b"x" * 65), 2),
        (connect_packet(flags=0), 5),
        (connect_packet(flags=6, extra=field(b"last/will") + field(b"bye")), 5),
        (connect_packet(flags=130, extra=field(b"user")), 5),
        (connect_packet(flags=194, extra=field(b"user") + field(b"password\x00")), 5),
    ]
    invalid_connect = [
        b"\x11\x00",
        packet(16, b"short"),
        connect_packet().replace(b"MQTT", b"NOPE"),
        connect_packet(flags=3),
        connect_packet(flags=66),
        connect_packet(flags=10),
        connect_packet(flags=34),
        connect_packet(flags=30),
        connect_packet(flags=6),
        connect_packet(b"bad\x00id"),
        connect_packet(b"\xff"),
        connect_packet(b"\xed\xa0\x80"),
        connect_packet(extra=b"trailing"),
        connect_packet(flags=130, extra=field(b"bad\x00user")),
        packet(16, b"\x00\x04MQTT\x04\x02\x00\x00\x00\x05abc"),
    ]
    malformed = [
        b"\x32\x00",
        b"\x34\x00",
        b"\x36\x00",
        b"\x38\x00",
        b"\x82\x00",
        b"\xc1\x00",
        b"\xe1\x00",
        b"\x00\x00",
        b"\xf0\x00",
        b"\x20\x00",
        b"\xc0\x01x",
        b"\xe0\x01x",
        b"\xc0\x80\x00",
        b"\xc0\x80\x80\x00",
        b"\xc0\x80\x80\x80\x00",
        b"\xc0\x80\x80\x80\x80",
        b"\x30\xff\xff\xff\x7f",
        b"\x30\x83\x88\x04",
        connect_packet(),
        publish_packet(b"", b"x"),
        publish_packet(b"a/+", b"x"),
        publish_packet(b"a/#", b"x"),
        publish_packet(b"a\x00b", b"x"),
        publish_packet(b"\xff", b"x"),
        publish_packet(b"\xc0\x80", b"x"),
        publish_packet(b"\xed\xa0\x80", b"x"),
        packet(48, b"\x00"),
        packet(48, b"\x00\x05abc"),
        publish_packet(b"a" * 257, b"x"),
        publish_packet(b"a", b"x" * 16385),
    ]
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as healthy:
        healthy.connect(b"healthy")
        healthy.publish(b"good", b"untouched")
        saved = Path(env["MQTT_STATE"]).read_bytes()
        for data, code in refused:
            with contextlib.closing(Raw(server)) as peer:
                peer.socket.sendall(data)
                peer.expect(b"\x20\x02\x00" + bytes([code]))
                peer.eof()
        for data in invalid_connect + [b"\xc0\x00", b"\xe0\x00", publish_packet(b"early", b"x")]:
            with contextlib.closing(Raw(server)) as peer:
                peer.socket.sendall(data)
                peer.eof(reset=True)
        for data in malformed:
            with contextlib.closing(Raw(server)) as peer:
                peer.connect()
                peer.socket.sendall(data)
                peer.eof(reset=True)
        healthy.ping()
        assert Path(env["MQTT_STATE"]).read_bytes() == saved
        stop(server, env)
    work, env = setup(directory, "takeover", max_peers=3, partial_ms=150, handshake_ms=150)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        old = stack.enter_context(contextlib.closing(Raw(server)))
        old.connect(b"shared")
        new = stack.enter_context(contextlib.closing(Raw(server)))
        new.connect(b"shared")
        old.eof()
        new.publish(b"takeover", b"new owner")
        waiting = stack.enter_context(contextlib.closing(Raw(server)))
        waiting.connect(b"second")
        third = stack.enter_context(contextlib.closing(Raw(server)))
        third.connect(b"third")
        with contextlib.closing(Raw(server)) as excess:
            excess.eof()
        waiting.socket.sendall(b"\xe0\x00")
        waiting.eof()
        with contextlib.closing(Raw(server)) as replacement:
            replacement.connect(b"second")
            replacement.ping()
        stop(server, env)
        new.eof()
        third.eof()
    for mode in ["handshake", "partial"]:
        work, env = setup(directory, "deadline_" + mode, handshake_ms=150, partial_ms=150)
        with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
            if mode == "partial":
                peer.connect()
                data = publish_packet(b"topic", b"x" * 1000)
            else:
                data = connect_packet(b"a" * 60)
            peer.socket.sendall(data[:3] if mode == "partial" else data[:2])
            stopped = threading.Event()
            writer = threading.Thread(target=drip, args=(peer, b"x", stopped))
            started = time.monotonic()
            writer.start()
            try:
                peer.eof(reset=True)
                assert time.monotonic() - started < 0.8
            finally:
                stopped.set()
                writer.join(timeout=2)
            assert not Path(env["MQTT_STATE"]).exists()
            stop(server, env)
    work, env = setup(directory, "keepalive", partial_ms=5000)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        timed = stack.enter_context(contextlib.closing(Raw(server)))
        timed.connect(b"timed", keepalive=1)
        disabled = stack.enter_context(contextlib.closing(Raw(server)))
        disabled.connect(b"disabled", keepalive=0)
        started = time.monotonic()
        # A partly received packet must not refresh the negotiated keep-alive.
        timed.socket.sendall(publish_packet(b"partial", b"x" * 100)[:-20])
        timed.eof()
        elapsed = time.monotonic() - started
        assert 1.2 <= elapsed < 2.5, elapsed
        disabled.publish(b"still/open", b"keepalive zero")
        disabled.socket.sendall(b"\xe0\x00")
        disabled.eof()
        stop(server, env)
    work, env = setup(directory, "limits", max_topics=2, history=2, topic_bytes=6, payload_bytes=20, total_bytes=64)
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        peer.connect(b"a")
        peer.publish("世界".encode(), b"x" * 20)
        peer.publish(b"other", b"y" * 20)
        saved = Path(env["MQTT_STATE"]).read_bytes()
        # All failures are transactional, even if an intermediate candidate
        # evicted history or changed the retained payload before validation.
        for topic, data in [(b"third", b""), ("世界a".encode(), b""), (b"other", b"z" * 21), (b"other", b"z" * 20)]:
            with contextlib.closing(Raw(server)) as rejected:
                rejected.connect(b"b")
                rejected.socket.sendall(publish_packet(topic, data, retain=True))
                rejected.eof()
            assert Path(env["MQTT_STATE"]).read_bytes() == saved
        peer.ping()
        stop(server, env)
    work, env = setup(directory, "concurrent", history=32)
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as incomplete:
        incomplete.connect(b"incomplete")
        incomplete.socket.sendall(publish_packet(b"waiting", b"x" * 1000)[:20])

        def produce(index: int) -> None:
            with contextlib.closing(Raw(server)) as peer:
                peer.connect(f"client{index}".encode())
                for number in range(12):
                    peer.publish(f"topic{index}".encode(), f"{index}:{number}".encode())
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(produce, range(4)))
        result = state(env, 48)
        sequences = []
        for index in range(4):
            history = result["topics"][f"topic{index}"]["history"]
            assert [bytes.fromhex(row["payload"]) for row in history] == [f"{index}:{n}".encode() for n in range(12)]
            sequences.extend(row["sequence"] for row in history)
        assert sorted(sequences) == list(range(1, 49))
        stop(server, env)
    work, env = setup(directory, "eof", history=128, packets_per_tick=2)
    model = empty
    with app.server(work, env) as server:
        with contextlib.closing(Raw(server)) as peer:
            peer.connect()
            peer.socket.sendall(b"".join(publish_packet(b"batch", bytes([index])) for index in range(64)))
            peer.socket.shutdown(socket.SHUT_WR)
            peer.eof()
            for index in range(64):
                model = record(model, "batch", bytes([index]), "raw", history=128)
            assert state(env, 64) == model
        with contextlib.closing(Raw(server)) as peer:
            peer.connect()
            peer.socket.sendall(publish_packet(b"batch", b"complete") + publish_packet(b"batch", b"truncated")[:-1])
            peer.socket.shutdown(socket.SHUT_WR)
            peer.eof()
            model = record(model, "batch", b"complete", "raw", history=128)
            assert state(env, 65) == model
        stop(server, env)
    work, env = setup(directory, "queue", queue_bytes=64, packets_per_tick=32, write_bytes=1)
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as flood:
        flood.connect()
        flood.socket.sendall(b"\xc0\x00" * 256)
        received = b""
        try:
            while data := flood.socket.recv(1024):
                received += data
                assert len(received) < 512
        except ConnectionResetError:
            pass
        with contextlib.closing(Raw(server)) as healthy:
            healthy.connect(b"healthy")
            healthy.publish(b"after/flood", b"works")
        stop(server, env)
    assert "reply queue exhausted" in (work / "process.log").read_text()
    work, env = setup(directory, "sequence_overflow")
    exhausted = record(empty, "topic", b"original", "setup")
    exhausted["sequence"] = 9223372036854775807
    exhausted["topics"]["topic"]["history"][0]["sequence"] = 9223372036854775807
    Path(env["MQTT_STATE"]).write_text(json.dumps(exhausted))
    saved = Path(env["MQTT_STATE"]).read_bytes()
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        peer.connect()
        peer.socket.sendall(publish_packet(b"overflow", b"rejected"))
        peer.eof()
        assert Path(env["MQTT_STATE"]).read_bytes() == saved
        stop(server, env)
    for boundary in ["before_checkpoint", "after_checkpoint"]:
        work, env = setup(directory, boundary)
        original = record(empty, "baseline", b"durable", "setup", history=16)
        Path(env["MQTT_STATE"]).write_text(json.dumps(original))
        with app.server(work, dict(env, MQTT_FAULT=boundary)) as server, contextlib.closing(Raw(server)) as peer:
            peer.connect(b"fault")
            peer.socket.sendall(publish_packet(b"fault", b"candidate"))
            assert server.process.wait(timeout=3) == 75
        expected = (
            original
            if boundary == "before_checkpoint"
            else record(original, "fault", b"candidate", "fault", history=16)
        )
        assert report(app, work, env) == expected
        with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
            peer.connect(b"resumed")
            peer.publish(b"resumed", b"safe")
            assert state(env, expected["sequence"] + 1) == record(expected, "resumed", b"safe", "resumed", history=16)
            stop(server, env)
    work, env = setup(directory, "recovery")
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as healthy:
        healthy.connect(b"healthy")
        healthy.publish(b"state", b"before")
        saved = Path(env["MQTT_STATE"]).read_bytes()
        Path(env["MQTT_STATE"]).write_text("corrupt")
        with contextlib.closing(Raw(server)) as peer:
            peer.connect(b"write-fails")
            peer.socket.sendall(publish_packet(b"bad", b"must not replace corrupt state"))
            peer.eof()
        assert Path(env["MQTT_STATE"]).read_text() == "corrupt"
        healthy.ping()
        Path(env["MQTT_STATE"]).write_bytes(saved)
        healthy.publish(b"state", b"after")
        assert state(env, 2)["topics"]["state"]["history"][-1]["payload"] == b"after".hex()
        stop(server, env)
    invalid_count = check_invalid(app, directory, empty)
    return {
        "independent_client": "Paho MQTT 2.1.0: Unicode topics, binary/empty payloads, automatic keep-alive, retained update/clear",
        "framing": "split/coalesced packets, one/two/three-byte lengths, one-byte writes, queued PING order",
        "connect_refusals": len(refused),
        "malformed_packets": len(invalid_connect) + 3 + len(malformed),
        "persistence": "per-topic trimming, exact hex, JSON report, restart, actual kill during partial publish, two checkpoint faults",
        "ownership": "duplicate client takeover, peer limits, freed slots and shutdown cleanup",
        "deadlines": "absolute handshake/partial, negotiated 1.5x keep-alive, zero disables keep-alive",
        "concurrent": "four peers publish 48 ordered/unique records while another packet remains incomplete",
        "eof": "64 buffered publications drain across tick budgets; a truncated tail never commits",
        "output_queue": "PING flood disconnects at the queue limit; a subsequent publisher succeeds",
        "sequence_overflow": "signed-i64 exhaustion preserves the prior checkpoint",
        "limits": "topic/UTF-8-byte/payload/total bounds leave snapshot unchanged",
        "invalid_startups": invalid_count,
    }


def check_invalid(app: Application, directory: Path, empty: dict) -> int:
    baseline = record(empty, "topic", b"value", "client", True)
    bad = []
    for key, value in [
        ("version", 2),
        ("version", True),
        ("sequence", -1),
        ("sequence", True),
        ("sequence", 2),
        ("topics", []),
    ]:
        bad.append(dict(baseline, **{key: value}))
    bad.append(dict(baseline, extra=1))
    for key, value in [("retained", "FF"), ("retained", "ff"), ("history", []), ("history", [1]), ("extra", 1)]:
        example = copy.deepcopy(baseline)
        example["topics"]["topic"][key] = value
        bad.append(example)
    for key, value in [
        ("sequence", 0),
        ("sequence", 2),
        ("sequence", True),
        ("client", ""),
        ("client", "bad\x00id"),
        ("client", "a" * 65),
        ("payload", "zz"),
        ("payload", "AA"),
        ("retain", 1),
        ("extra", 1),
    ]:
        example = copy.deepcopy(baseline)
        example["topics"]["topic"]["history"][0][key] = value
        bad.append(example)
    duplicated = copy.deepcopy(baseline)
    duplicated["topics"]["second"] = copy.deepcopy(duplicated["topics"]["topic"])
    bad.append(duplicated)
    for topic in ["", "a/+", "a/#", "a\x00b", "a" * 257]:
        bad.append(dict(baseline, topics={topic: baseline["topics"]["topic"]}))
    for index, invalid in enumerate(bad):
        work, env = setup(directory, f"corrupt_{index}")
        path = Path(env["MQTT_STATE"])
        path.write_text(json.dumps(invalid))
        before = path.read_bytes()
        result = app.run(work, env)
        assert result.returncode != 0 and "LISTENING" not in result.stdout, (index, invalid)
        assert path.read_bytes() == before
    invalid_policies = [
        {"unknown": 1},
        {"max_peers": True},
        {"max_peers": 0},
        {"max_peers": 65},
        {"max_topics": 0},
        {"history": 0},
        {"history": 129},
        {"topic_bytes": 1025},
        {"payload_bytes": -1},
        {"payload_bytes": 65537},
        {"total_bytes": 63},
        {"total_bytes": 1048577},
        {"packet_bytes": 131073},
        {"packet_bytes": 12},
        {"queue_bytes": 63},
        {"packets_per_tick": 0},
        {"write_bytes": 0},
        {"handshake_ms": 49},
        {"partial_ms": 30001},
        {"close_ms": 5001},
    ]
    for index, policy in enumerate(invalid_policies):
        work, env = setup(directory, f"policy_{index}", **policy)
        result = app.run(work, env)
        assert result.returncode != 0 and "LISTENING" not in result.stdout
    for index, port in enumerate(["true", "-1", "65536", '"8792"']):
        work, env = setup(directory, f"port_{index}")
        result = app.run(work, dict(env, MQTT_PORT=port))
        assert result.returncode != 0 and "LISTENING" not in result.stdout
    for alias in ["same", "hardlink", "symlink"]:
        work, env = setup(directory, "alias_" + alias)
        config = Path(env["MQTT_CONFIG"])
        saved = config.read_bytes()
        if alias == "same":
            env["MQTT_STATE"] = str(config)
        elif alias == "hardlink":
            Path(env["MQTT_STATE"]).hardlink_to(config)
        else:
            Path(env["MQTT_STATE"]).symlink_to(config)
        assert app.run(work, env).returncode != 0
        assert config.read_bytes() == saved
    work, env = setup(directory, "large_snapshot")
    with Path(env["MQTT_STATE"]).open("wb") as stream:
        stream.truncate(8388609)
    assert app.run(work, env).returncode != 0
    return len(bad) + len(invalid_policies) + 8
