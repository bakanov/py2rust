"""Independent RFC 6455 clients, malformed frames, deadlines and real backpressure."""

from __future__ import annotations

import contextlib
import json
import socket
import struct
import threading
import time
from pathlib import Path

from websockets.sync.client import connect

from .common import Application, Server

ASSET = Path(__file__).resolve().parents[2] / "examples/corpus/027_websocket_rooms/client.html"


def frame(payload: bytes = b"", opcode: int = 1, finished: bool = True) -> bytes:
    """Independent masked client encoder; never import the application codec."""
    size = len(payload)
    prefix = bytes([(128 if finished else 0) | opcode])
    if size < 126:
        prefix += bytes([128 | size])
    elif size <= 65535:
        prefix += b"\xfe" + struct.pack("!H", size)
    else:
        prefix += b"\xff" + struct.pack("!Q", size)
    mask = b"\x37\xfa\x21\x3d"
    return prefix + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))


class Raw:
    def __init__(self, server: Server, small_buffer: bool = False) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if small_buffer:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        self.socket.settimeout(3)
        self.socket.connect(("127.0.0.1", server.port))
        self.server = server
        self.buffer = b""
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def take(self, count: int) -> bytes:
        while len(self.buffer) < count:
            part = self.socket.recv(65536)
            assert part, "EOF before complete reply"
            self.buffer += part
        result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result

    def headers(self) -> tuple[int, dict[str, str]]:
        while b"\r\n\r\n" not in self.buffer:
            part = self.socket.recv(65536)
            assert part, "EOF before HTTP response"
            self.buffer += part
            assert len(self.buffer) < 1048576
        head, self.buffer = self.buffer.split(b"\r\n\r\n", 1)
        lines = head.decode().split("\r\n")
        assert lines[0].startswith("HTTP/1.1 "), lines[0]
        headers = {}
        for line in lines[1:]:
            name, value = line.split(": ", 1)
            assert name.lower() not in headers, "duplicate response header"
            headers[name.lower()] = value
        return int(lines[0].split()[1]), headers

    def request(self, path: str = "/room/main/raw", extra: bytes = b"") -> bytes:
        return (
            (
                f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n"
                "Upgrade: websocket\r\nConnection: keep-alive, Upgrade\r\n"
                "Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            ).encode()
            + extra
            + b"\r\n"
        )

    def upgraded(self) -> dict:
        status, headers = self.headers()
        assert status == 101, (status, headers)
        assert headers["sec-websocket-accept"] == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        assert headers["upgrade"].lower() == "websocket" and headers["connection"].lower() == "upgrade"
        assert "sec-websocket-extensions" not in headers and "sec-websocket-protocol" not in headers
        return self.message()

    def upgrade(self, path: str = "/room/main/raw") -> dict:
        self.socket.sendall(self.request(path))
        return self.upgraded()

    def packet(self) -> tuple[int, bytes]:
        first, second = self.take(2)
        assert first & 240 == 128 and second & 128 == 0, (first, second)
        size = second & 127
        if size == 126:
            size = struct.unpack("!H", self.take(2))[0]
            assert size >= 126
        elif size == 127:
            size = struct.unpack("!Q", self.take(8))[0]
            assert size >= 65536
        assert size <= 1048576
        return first & 15, self.take(size)

    def message(self) -> dict:
        opcode, payload = self.packet()
        assert opcode == 1, (opcode, payload)
        return json.loads(payload)

    def eof(self) -> None:
        assert self.buffer == b"", self.buffer[:100]
        assert self.socket.recv(1) == b""
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def closed(self, code: int, acknowledge: bool = True, allow_reset: bool = False) -> None:
        opcode, payload = self.packet()
        assert opcode == 8 and len(payload) >= 2, (opcode, payload)
        assert struct.unpack("!H", payload[:2])[0] == code, payload
        if acknowledge:
            self.socket.sendall(frame(payload, 8))
        try:
            self.eof()
        except ConnectionResetError:
            # Only hostile deadline fixtures keep writing after the close frame.
            # TCP can reset with unread input (RFC 6455 section 1.4). The frame
            # and close code above must still have been delivered and validated.
            assert allow_reset and not acknowledge, "unexpected TCP reset during graceful close"
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def close(self) -> None:
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def setup(directory: Path, name: str, **policy: int) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    config = work / "rooms.json"
    config.write_text(json.dumps({"idle_ms": 30000, "close_ms": 150, **policy}))
    return work, {"WS_CONFIG": str(config), "WS_HOME": str(ASSET), "WS_PORT": "0", "WS_STOP": str(work / "stop")}


def client(server: Server, room: str, name: str):
    peer = connect(
        f"ws://127.0.0.1:{server.port}/room/{room}/{name}",
        origin=f"http://127.0.0.1:{server.port}",
        compression=None,
        proxy=None,
        open_timeout=3,
        close_timeout=1,
        ping_interval=None,
        max_size=1048576,
    )
    welcome = json.loads(peer.recv(timeout=3))
    assert welcome["type"] == "welcome" and welcome["room"] == room and welcome["name"] == name
    return peer


def shutdown(server: Server, env: dict[str, str]) -> None:
    Path(env["WS_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def drip(peer: Raw, data: bytes, stopped: threading.Event) -> None:
    for _ in range(60):
        if stopped.wait(0.02):
            break
        try:
            peer.socket.sendall(data)
        except OSError:
            break
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    work, env = setup(directory, "independent", message_bytes=65536, queue_bytes=524288, frames_per_tick=2)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        response = server.request("GET", "/")
        assert response.status == 200 and response.body == ASSET.read_bytes()
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        alice = stack.enter_context(client(server, "main", "Alice"))
        bob = stack.enter_context(client(server, "main", "Bob"))
        other = stack.enter_context(client(server, "other", "Alice"))
        messages = ["Hello 世界 😀", "", 'line\n\t\x00quote"slash\\', "a" * 125, "b" * 126, "c" * 65535, "d" * 65536]
        for sequence, text in enumerate(messages, 1):
            alice.send(text)
            expected = {"type": "message", "room": "main", "name": "Alice", "sequence": sequence, "text": text}
            assert json.loads(alice.recv(timeout=3)) == expected
            assert json.loads(bob.recv(timeout=3)) == expected
        assert alice.ping(b"independent ping").wait(2)
        alice.send(["fragment ", "世界", " 😀"])
        assert json.loads(alice.recv(timeout=3))["text"] == "fragment 世界 😀"
        assert json.loads(bob.recv(timeout=3))["sequence"] == 8
        other.send("isolated")
        assert json.loads(other.recv(timeout=3))["sequence"] == 9
        bob.send("still healthy")
        assert json.loads(alice.recv(timeout=3))["text"] == "still healthy"
        assert json.loads(bob.recv(timeout=3))["sequence"] == 10
        # A room/name pair is unique only while connected.
        with contextlib.closing(Raw(server)) as duplicate:
            duplicate.socket.sendall(duplicate.request("/room/main/Alice"))
            assert duplicate.headers()[0] == 409
        bob.close()
        with client(server, "main", "Bob") as returned:
            assert returned.ping(b"rejoined").wait(2)
        shutdown(server, env)
    work, env = setup(directory, "handshakes")
    rejected = 0
    with app.server(work, env) as server:
        with contextlib.closing(Raw(server)) as probe:
            request = probe.request()
        cases = [
            (request.replace(b"GET ", b"POST ", 1), 400),
            (request.replace(b"HTTP/1.1", b"HTTP/1.0"), 400),
            (request.replace(b"/room/main/raw", b"/missing"), 404),
            (request.replace(b"/room/main/raw", b"/room/main/bad%20name"), 404),
            (request.replace(f"127.0.0.1:{server.port}".encode(), b"example.com"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nOrigin: https://example.com\r\n\r\n"), 403),
            (request.replace(b"Version: 13", b"Version: 12"), 426),
            (request.replace(b"websocket\r\n", b"other\r\n"), 400),
            (request.replace(b"keep-alive, Upgrade", b"keep-alive, xUpgrade"), 400),
            (request.replace(b"dGhlIHNhbXBsZSBub25jZQ==", b"Zg=="), 400),
            (request.replace(b"dGhlIHNhbXBsZSBub25jZQ==", b"dGhlIHNhbXBsZSBub25jZR=="), 400),
            (request.replace(b"\r\n\r\n", b"\r\nTransfer-Encoding: chunked\r\n\r\n"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nContent-Length: 1\r\n\r\nx"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nUpgrade: websocket\r\n\r\n"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nBad Header: value\r\n\r\n"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nBad: x\x00y\r\n\r\n"), 400),
            (request.replace(b"\r\n\r\n", b"\r\nBad: \xff\r\n\r\n"), 400),
            (
                request.replace(b"\r\n\r\n", b"\r\n" + b"".join(f"X-{i}: a\r\n".encode() for i in range(66)) + b"\r\n"),
                400,
            ),
            (b"GET / HTTP/1.1\r\nX-Large: " + b"a" * 8193, 431),
            (request.replace(b"\r\n\r\n", b"\r\nLarge: " + b"x" * 8192 + b"\r\n\r\n"), 431),
        ]
        for data, expected_status in cases:
            with contextlib.closing(Raw(server)) as peer:
                peer.socket.sendall(data)
                status, headers = peer.headers()
                assert status == expected_status, (status, expected_status, data[:80])
                if status == 426:
                    assert headers["sec-websocket-version"] == "13"
                peer.take(int(headers["content-length"]))
                peer.eof()
                rejected += 1
        with contextlib.closing(Raw(server)) as peer:
            request = peer.request(extra=b"Sec-WebSocket-Extensions: permessage-deflate\r\n")
            peer.socket.sendall(request[:7])
            time.sleep(0.01)
            peer.socket.sendall(request[7:] + frame("pipelined 世界".encode()))
            assert peer.upgraded()["type"] == "welcome"
            assert peer.message()["text"] == "pipelined 世界"
        shutdown(server, env)
    work, env = setup(directory, "frames", message_bytes=256, frames_per_tick=2, write_bytes=7)
    malformed = [
        (b"\x81\x01x", 1002),
        (bytes([frame()[0] | 64]) + frame()[1:], 1002),
        (frame(b"", 3), 1002),
        (b"\x81\xfe\x00\x01", 1002),
        (b"\x81\xff" + struct.pack("!Q", 65535), 1002),
        (b"\x81\xff\x80" + b"\x00" * 7, 1002),
        (frame(b"", 9, False), 1002),
        (frame(b"a" * 126, 9), 1002),
        (frame(b"binary", 2), 1003),
        (frame(b"\xff"), 1007),
        (frame(b"\xed\xa0\x80"), 1007),
        (b"\x81\xfe\x01\x01", 1009),
        (frame(b"a" * 200, finished=False) + frame(b"b" * 57, 0), 1009),
        (frame(b"orphan", 0), 1002),
        (frame(b"first", finished=False) + frame(b"second"), 1002),
        (frame(b"a", 8), 1002),
        (frame(struct.pack("!H", 1005), 8), 1002),
        (frame(struct.pack("!H", 999), 8), 1002),
        (frame(struct.pack("!H", 1015), 8), 1002),
        (frame(struct.pack("!H", 5000), 8), 1002),
        (frame(struct.pack("!H", 1000) + b"\xff", 8), 1007),
    ]
    with app.server(work, env) as server:
        for index, (data, code) in enumerate(malformed):
            with contextlib.closing(Raw(server)) as peer:
                peer.upgrade(f"/room/errors/p{index}")
                peer.socket.sendall(data)
                peer.closed(code)
        with contextlib.closing(Raw(server)) as peer:
            peer.upgrade()
            text = "before 世界 after"
            encoded = text.encode()
            split = encoded.index("世".encode()) + 1
            peer.socket.sendall(
                frame(encoded[:split], finished=False) + frame(b"middle", 9) + frame(encoded[split:], 0)
            )
            assert peer.packet() == (10, b"middle")
            assert peer.message()["text"] == text
            peer.socket.sendall(frame(b"ignored pong", 10) + b"".join(frame(str(i).encode()) for i in range(25)))
            for i in range(25):
                assert peer.message()["text"] == str(i)
            # A TCP split inside the mask isn't a frame boundary.
            packet = frame(b"split mask")
            peer.socket.sendall(packet[:4])
            time.sleep(0.01)
            peer.socket.sendall(packet[4:])
            assert peer.message()["text"] == "split mask"
        for payload in [b"", struct.pack("!H", 1000) + "done 世界".encode(), struct.pack("!H", 3000)]:
            with contextlib.closing(Raw(server)) as peer:
                peer.upgrade()
                peer.socket.sendall(frame(payload, 8))
                assert peer.packet() == (8, payload)
                peer.eof()
        shutdown(server, env)
    # Control payloads remain legal at 125 bytes even when the text limit is one byte.
    work, env = setup(directory, "small_text", message_bytes=1, write_bytes=1)
    with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
        peer.upgrade()
        peer.socket.sendall(frame(b"p" * 125, 9) + frame(b"a"))
        assert peer.packet() == (10, b"p" * 125)
        assert peer.message()["text"] == "a"
        shutdown(server, env)
        peer.closed(1001, acknowledge=False)
    deadlines = []
    for mode in ["handshake", "partial", "fragment", "idle"]:
        work, env = setup(directory, mode, handshake_ms=150, partial_ms=150, idle_ms=300 if mode == "idle" else 30000)
        with app.server(work, env) as server, contextlib.closing(Raw(server)) as peer:
            if mode != "handshake":
                peer.upgrade()
            started = time.monotonic()
            stopped = threading.Event()
            data = frame(b"", 0, False) if mode == "fragment" else b"a"
            writer = threading.Thread(target=drip, args=(peer, data, stopped))
            try:
                if mode == "handshake":
                    peer.socket.sendall(b"GET /")
                elif mode == "partial":
                    peer.socket.sendall(frame(b"x" * 1000)[:4])
                elif mode == "fragment":
                    peer.socket.sendall(frame(b"first", finished=False))
                if mode != "idle":
                    writer.start()
                if mode == "handshake":
                    assert peer.headers()[0] == 408
                else:
                    peer.closed(
                        1001 if mode == "idle" else 1008,
                        acknowledge=False,
                        allow_reset=mode in ["partial", "fragment"],
                    )
                # The drip continues for 1.2 seconds if not interrupted. Resetting
                # a deadline after every read or continuation would exceed this bound.
                elapsed = time.monotonic() - started
                assert elapsed < 0.8, (mode, elapsed)
            finally:
                stopped.set()
                if writer.ident is not None:
                    writer.join(timeout=2)
            deadlines.append(mode)
            shutdown(server, env)
    work, env = setup(directory, "capacity", max_peers=2, handshake_ms=150)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        first = stack.enter_context(contextlib.closing(Raw(server)))
        first.upgrade("/room/main/one")
        second = stack.enter_context(contextlib.closing(Raw(server)))
        second.upgrade("/room/main/two")
        with contextlib.closing(Raw(server)) as excess:
            excess.eof()
        second.close()
        time.sleep(0.05)
        with client(server, "main", "two") as replacement:
            assert replacement.ping(b"available").wait(2)
        Path(env["WS_STOP"]).touch()
        first.closed(1001)
        assert server.process.wait(timeout=2) == 0
    work, env = setup(directory, "backpressure", message_bytes=1024, queue_bytes=8192, send_buffer=1024)
    with app.server(work, env) as server, contextlib.ExitStack() as stack:
        slow = stack.enter_context(contextlib.closing(Raw(server, small_buffer=True)))
        slow.upgrade("/room/main/slow")
        sender = stack.enter_context(client(server, "main", "sender"))
        healthy = stack.enter_context(client(server, "main", "healthy"))
        for index in range(180):
            text = str(index) + ":" + "x" * 900
            sender.send(text)
            assert json.loads(sender.recv(timeout=3))["text"] == text
            assert json.loads(healthy.recv(timeout=3))["text"] == text
        assert healthy.ping(b"after slow reader").wait(2)
        # Real socket buffers fill before the application output queue. Drain to
        # EOF after healthy peers have proved they can keep sending/receiving.
        slow.buffer = b""
        drained = 0
        try:
            while chunk := slow.socket.recv(65536):
                drained += len(chunk)
                assert drained < 1048576
        except ConnectionResetError:
            pass
        shutdown(server, env)
    assert "slow queue_limit" in (work / "process.log").read_text()
    invalid = [
        {"unknown": 1},
        {"max_peers": True},
        {"max_peers": 0},
        {"max_peers": 65},
        {"message_bytes": 0},
        {"message_bytes": 65537},
        {"queue_bytes": 8191},
        {"queue_bytes": 1048577},
        {"message_bytes": 65536, "queue_bytes": 8192},
        {"frames_per_tick": 0},
        {"frames_per_tick": 33},
        {"handshake_ms": 49},
        {"partial_ms": 30001},
        {"idle_ms": 99},
        {"close_ms": 5001},
        {"send_buffer": 1023},
        {"write_bytes": 0},
        {"write_bytes": 65537},
    ]
    for index, policy in enumerate(invalid):
        work, env = setup(directory, "invalid_" + str(index), **policy)
        result = app.run(work, env)
        assert result.returncode != 0 and "LISTENING" not in result.stdout
    for index, port in enumerate(["-1", "65536", "true", '"8791"']):
        work, env = setup(directory, "port_" + str(index))
        env["WS_PORT"] = port
        result = app.run(work, env)
        assert result.returncode != 0 and "LISTENING" not in result.stdout
    work, env = setup(directory, "large_asset")
    asset = work / "large.html"
    asset.write_bytes(b"x" * 4097)
    env["WS_HOME"] = str(asset)
    assert app.run(work, env).returncode != 0
    return {
        "independent_client": "websockets 17.1: Unicode, empty text, 125/126/65535/65536 bytes, fragments, ping, rooms, rejoin",
        "http_rejections": rejected,
        "invalid_frames": len(malformed),
        "raw_frames": "split/coalesced TCP, UTF-8 fragments, ping interleaving, ignored pong, bounded frame batches, close echo",
        "deadlines": deadlines,
        "capacity": "excess rejected, disconnect frees slot, graceful shutdown",
        "backpressure": "real nonreading socket evicted while two independent clients exchange 180 messages",
        "configuration_rejections": len(invalid) + 5,
        "browser_client": "exact served HTML asset",
    }
