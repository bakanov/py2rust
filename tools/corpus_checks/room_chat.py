"""Independent room protocol clients, real slow-reader backpressure and cleanup checks."""

from __future__ import annotations

import contextlib
import json
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import Application, Server


class Peer:
    def __init__(self, server: Server, small_buffer: bool = False) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if small_buffer:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        self.socket.settimeout(3)
        self.socket.connect(("127.0.0.1", server.port))
        self.buffer = b""
        self.expect("HELLO NICK JOIN SAY WHO ROOMS PING QUIT STATS")
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def send(self, line: str) -> None:
        self.socket.sendall(line.encode() + b"\n")
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def line(self) -> str:
        while b"\n" not in self.buffer:
            chunk = self.socket.recv(65536)
            assert chunk, "connection closed before a complete line"
            self.buffer += chunk
            assert len(self.buffer) <= 1048576, "unexpected unbounded reply"
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode()

    def expect(self, expected: str) -> None:
        actual = self.line()
        assert actual == expected, (actual, expected)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def through(self, expected: str) -> list[str]:
        extras = []
        for _ in range(100):
            actual = self.line()
            if actual == expected:
                return extras
            extras.append(actual)
        raise AssertionError((expected, extras))

    def register(self, nick: str, room: str) -> None:
        self.send("NICK " + nick)
        self.expect("OK NICK " + nick)
        self.send("JOIN " + room)
        self.expect("OK JOIN " + room.lower())
        self.expect("JOIN " + room.lower() + " " + nick)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def eof(self, allow_reset: bool = False) -> None:
        assert self.buffer == b"", self.buffer
        try:
            assert self.socket.recv(1) == b""
        except ConnectionResetError:
            assert allow_reset, "unexpected reset after a fully consumed command"
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def close(self) -> None:
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def setup(directory: Path, name: str, **policy: int) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    config = work / "rooms.json"
    config.write_text(
        json.dumps({"max_peers": 8, "max_rooms": 2, "line_bytes": 256, "partial_ms": 1000, "idle_ms": 30000, **policy})
    )
    return work, {"ROOM_CONFIG": str(config), "ROOM_PORT": "0", "ROOM_STOP": str(work / "stop")}


def stats(peer: Peer) -> dict:
    peer.send("STATS")
    line = peer.line()
    assert line.startswith("STATS "), line
    return json.loads(line[6:])


def check(app: Application, directory: Path) -> dict:
    work, env = setup(directory, "rooms", commands_per_tick=2)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        alice = stack.enter_context(contextlib.closing(Peer(server)))
        alice.send("SAY before joining")
        alice.expect("ERR NEED_ROOM")
        alice.send("JOIN main")
        alice.expect("ERR NEED_NICK")
        alice.register("Alice", "MAIN")
        bob = stack.enter_context(contextlib.closing(Peer(server)))
        bob.register("Bob", "main")
        alice.expect("JOIN main Bob")
        carol = stack.enter_context(contextlib.closing(Peer(server)))
        carol.register("Carol", "other")
        dave = stack.enter_context(contextlib.closing(Peer(server)))
        dave.send("NICK alice")
        dave.expect("ERR IN_USE")
        dave.send("NICK bad nick")
        dave.expect("ERR NICK")
        dave.send("NICK Dave")
        dave.expect("OK NICK Dave")
        dave.send("JOIN third")
        dave.expect("ERR ROOM_LIMIT")
        alice.send("WHO")
        alice.expect("USERS main Alice,Bob")
        dave.send("ROOMS")
        dave.expect("ROOMS main,other")
        payload = "Hello 世界 😀  "
        encoded = ("SAY " + payload + "\r\n").encode()
        boundary = encoded.index("世".encode()) + 1
        alice.socket.sendall(encoded[:boundary])
        time.sleep(0.02)
        alice.socket.sendall(encoded[boundary:])
        alice.expect("MSG 1 main Alice " + payload)
        bob.expect("MSG 1 main Alice " + payload)
        carol.send("PING isolated")
        carol.expect("PONG isolated")
        carol.send("SAY private")
        carol.expect("MSG 2 other Carol private")
        alice.send("PING still isolated")
        alice.expect("PONG still isolated")
        bob.send("NICK Bobby")
        bob.expect("OK NICK Bobby")
        bob.expect("RENAME main Bob Bobby")
        alice.expect("RENAME main Bob Bobby")
        bob.send("JOIN Other")
        bob.expect("OK JOIN other")
        bob.expect("JOIN other Bobby")
        alice.expect("LEAVE main Bobby move")
        carol.expect("JOIN other Bobby")
        # The only member can move, freeing its former room at the configured room limit.
        alice.send("JOIN third")
        alice.expect("OK JOIN third")
        alice.expect("JOIN third Alice")
        dave.send("ROOMS")
        dave.expect("ROOMS other,third")
        bob.send("QUIT")
        bob.expect("BYE")
        bob.eof()
        carol.expect("LEAVE other Bobby quit")
        dave.send("NICK bObBy")
        dave.expect("OK NICK bObBy")
        # More complete commands than the per-tick budget retain order without waiting for more I/O.
        alice.socket.sendall(b"".join(f"PING {i}\n".encode() for i in range(200)))
        for i in range(200):
            alice.expect("PONG " + str(i))
        for command, expected in [
            ("NOPE", "ERR COMMAND"),
            ("WHO extra", "ERR ARGUMENT"),
            ("SAY   ", "ERR EMPTY"),
            ("JOIN bad/name", "ERR ROOM"),
        ]:
            alice.send(command)
            alice.expect(expected)
        # Abrupt reset removes membership and the nickname; OS error category is not prescribed.
        carol.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        carol.close()
        for _ in range(100):
            current = stats(alice)
            if current["peers"] == 2:
                break
            time.sleep(0.01)
        assert current["peers"] == 2 and current["messages"] == 2
        dave.send("NICK Carol")
        dave.expect("OK NICK Carol")
        Path(env["ROOM_STOP"]).touch()
        assert server.process.wait(timeout=2) == 0
        alice.eof()
        dave.eof()
    protocol_failures = bad_lines(app, directory)
    slow = slow_reader(app, directory)
    limits = lifecycle_limits(app, directory)
    invalid = invalid_config(app, directory)
    return {
        "room_isolation": True,
        "split_unicode_and_crlf": payload,
        "messages": 2,
        "coalesced_commands_in_order": 200,
        "nickname_cleanup": True,
        "room_limit_releases_empty_rooms": True,
        "protocol_failures": protocol_failures,
        "slow_reader": slow,
        "limits": limits,
        "invalid_config": invalid,
    }


def bad_lines(app: Application, directory: Path) -> list[str]:
    work, env = setup(directory, "bad-lines", partial_ms=120, write_bytes=1, close_ms=1000)
    cases = [
        (b"x" * 257, "LINE_TOO_LONG"),
        (b"x" * 257 + b"\n", "LINE_TOO_LONG"),
        (b"PING \xff\n", "UTF8"),
        (b"PING a\x00b\n", "CONTROL"),
        (b"PING a\tb\n", "CONTROL"),
    ]
    with app.server(work, env) as server, contextlib.closing(Peer(server)) as watcher:
        watcher.register("Watcher", "main")
        for index, (raw, code) in enumerate(cases):
            with contextlib.closing(Peer(server)) as peer:
                peer.register("Invalid" + str(index), "main")
                watcher.expect("JOIN main Invalid" + str(index))
                peer.socket.sendall(raw)
                peer.expect("ERR " + code)
                peer.eof()
                watcher.expect("LEAVE main Invalid" + str(index) + " protocol")
        # One-byte output writes can split a multibyte code point; the client still sees exact UTF-8.
        watcher.send("SAY 世界 😀")
        watcher.expect("MSG 1 main Watcher 世界 😀")
        with contextlib.closing(Peer(server)) as slow:
            slow.register("Drip", "main")
            watcher.expect("JOIN main Drip")
            stop = threading.Event()

            def drip() -> None:
                try:
                    for byte in b"PING never completes":
                        slow.socket.sendall(bytes([byte]))
                        if stop.wait(0.03):
                            break
                except OSError:
                    pass
                return  # noqa: PLR1711 - explicit return required by repository guidelines

            with ThreadPoolExecutor(max_workers=1) as pool:
                began = time.monotonic()
                future = pool.submit(drip)
                try:
                    slow.expect("ERR LINE_TIMEOUT")
                    assert time.monotonic() - began < 0.6
                finally:
                    stop.set()
                future.result(timeout=1)
            slow.eof()
            watcher.expect("LEAVE main Drip timeout")
        current = stats(watcher)
        assert current["closed"]["protocol"] == 5 and current["closed"]["timeout"] == 1
        assert current["peers"] == 1
    return [code for _, code in cases] + ["LINE_TIMEOUT"]


def slow_reader(app: Application, directory: Path) -> dict:
    work, env = setup(
        directory,
        "slow-reader",
        line_bytes=1024,
        queue_bytes=4096,
        send_buffer=1024,
        queue_lines=128,
        write_bytes=65536,
    )
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        sender = stack.enter_context(contextlib.closing(Peer(server)))
        sender.register("Sender", "main")
        reader = stack.enter_context(contextlib.closing(Peer(server)))
        reader.register("Reader", "main")
        sender.expect("JOIN main Reader")
        slow = stack.enter_context(contextlib.closing(Peer(server, small_buffer=True)))
        slow.register("Slow", "main")
        sender.expect("JOIN main Slow")
        reader.expect("JOIN main Slow")
        departed = False
        extras = []
        for index in range(200):
            text = str(index) + ":" + "世界" * 140
            sender.send("SAY " + text)
            expected = f"MSG {index + 1} main Sender " + text
            extras.extend(sender.through(expected))
            extras.extend(reader.through(expected))
            sender.send("PING barrier")
            extras.extend(sender.through("PONG barrier"))
            assert all(line == "LEAVE main Slow slow" for line in extras), extras
            if extras:
                departed = True
                break
        assert departed, "a nonreading client was not evicted at the queue limit"
        reader.send("PING reader barrier")
        extras.extend(reader.through("PONG reader barrier"))
        assert extras == ["LEAVE main Slow slow"] * 2, extras
        current = stats(sender)
        assert current["peers"] == 2 and current["closed"]["slow"] == 1
        sender.send("SAY still responsive")
        expected = f"MSG {index + 2} main Sender still responsive"
        sender.expect(expected)
        reader.expect(expected)
    return {"actual_nonreader_evicted": True, "healthy_clients_lossless": True, "maximum_probe_messages": 200}


def lifecycle_limits(app: Application, directory: Path) -> dict:
    work, env = setup(directory, "peer-limit", max_peers=2)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        first = stack.enter_context(contextlib.closing(Peer(server)))
        first.register("First", "main")
        second = stack.enter_context(contextlib.closing(Peer(server)))
        second.register("Second", "main")
        first.expect("JOIN main Second")
        with socket.create_connection(("127.0.0.1", server.port), timeout=3) as rejected:
            assert rejected.recv(1) == b""
        first.send("QUIT")
        first.expect("BYE")
        first.eof()
        second.expect("LEAVE main First quit")
        replacement = stack.enter_context(contextlib.closing(Peer(server)))
        replacement.register("First", "main")
        second.expect("JOIN main First")
        # Graceful server stop also closes peers with incomplete lines.
        replacement.socket.sendall(b"PING partial")
        Path(env["ROOM_STOP"]).touch()
        assert server.process.wait(timeout=2) == 0
        second.eof()
        replacement.eof(allow_reset=True)
    work, env = setup(directory, "line-queue", queue_lines=4, commands_per_tick=8)
    with (
        app.server(work, env) as server,
        contextlib.closing(Peer(server)) as observer,
        contextlib.closing(Peer(server)) as flood,
    ):
        observer.register("Observer", "main")
        flood.register("Flood", "main")
        observer.expect("JOIN main Flood")
        flood.socket.sendall(b"PING flood\n" * 8)
        # Five replies cannot enter a queue with four line slots, independent of byte capacity.
        observer.expect("LEAVE main Flood slow")
        observer.send("SAY unaffected")
        observer.expect("MSG 1 main Observer unaffected")
        assert stats(observer)["closed"]["slow"] == 1
    work, env = setup(directory, "idle", idle_ms=150)
    with app.server(work, env) as server:
        with contextlib.closing(Peer(server)) as idle:
            idle.expect("ERR IDLE")
            idle.eof()
        with contextlib.closing(Peer(server)) as peer:
            assert stats(peer)["closed"]["timeout"] == 1
    return {"peer_slots_reused": True, "line_queue_bound": 4, "idle_cleanup": True, "active_stop": True}


def invalid_config(app: Application, directory: Path) -> int:
    invalid = [
        ("max_peers", 0),
        ("max_peers", 65),
        ("max_rooms", True),
        ("line_bytes", 63),
        ("queue_bytes", 4095),
        ("queue_lines", 3),
        ("commands_per_tick", 0),
        ("write_bytes", 0),
        ("send_buffer", 65537),
        ("partial_ms", 49),
        ("idle_ms", 99),
        ("close_ms", 49),
        ("unknown", 1),
    ]
    for index, (key, value) in enumerate(invalid):
        work, env = setup(directory, "invalid-" + str(index))
        path = Path(env["ROOM_CONFIG"])
        config = json.loads(path.read_text())
        config[key] = value
        path.write_text(json.dumps(config))
        process = app.run(work, env, timeout=3)
        assert process.returncode != 0 and "LISTENING" not in process.stdout
    work, env = setup(directory, "invalid-port")
    process = app.run(work, dict(env, ROOM_PORT="65536"), timeout=3)
    assert process.returncode != 0 and "LISTENING" not in process.stdout
    work, env = setup(directory, "queue-too-small", line_bytes=4096, queue_bytes=4096)
    assert app.run(work, env, timeout=3).returncode != 0
    return len(invalid) + 2
