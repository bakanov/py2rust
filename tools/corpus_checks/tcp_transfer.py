"""Independent transfer peers, interrupted-publication oracles and bounded-memory checks."""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import socket
import struct
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from .common import Application, Server


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(name: str, data: bytes) -> dict:
    return {"version": 1, "name": name, "size": len(data), "sha256": digest(data)}


def frame(data: bytes) -> bytes:
    return struct.pack("!I", len(data)) + data


def control(value: dict) -> bytes:
    return frame(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode())


def exact(stream: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        part = stream.recv(remaining)
        if not part:
            raise EOFError("truncated frame")
        chunks.append(part)
        remaining -= len(part)
    return b"".join(chunks)


def receive(stream: socket.socket, maximum: int = 65536) -> bytes:
    size = struct.unpack("!I", exact(stream, 4))[0]
    assert 0 < size <= maximum, size
    return exact(stream, size)


def read_json(stream: socket.socket) -> dict:
    return json.loads(receive(stream, 1024))


class Peer:
    def __init__(self, server: Server) -> None:
        self.socket = socket.create_connection(("127.0.0.1", server.port), timeout=5)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def open(self, wanted: dict, split: bool = False) -> dict:
        data = control(wanted)
        if split:
            self.socket.sendall(data[:2])
            time.sleep(0.01)
            self.socket.sendall(data[2:9])
            time.sleep(0.01)
            self.socket.sendall(data[9:])
        else:
            self.socket.sendall(data)
        return read_json(self.socket)

    def chunk(self, offset: int, data: bytes, checksum: str | None = None) -> dict:
        self.socket.sendall(
            control({"op": "chunk", "offset": offset, "sha256": checksum or digest(data)}) + frame(data)
        )
        return read_json(self.socket)

    def finish(self) -> dict:
        self.socket.sendall(control({"op": "finish"}))
        return read_json(self.socket)

    def close(self) -> None:
        self.socket.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def receipt(value: dict, data: bytes, offset: int, chunk_size: int, complete: bool = False) -> None:
    assert value == {
        "ok": True,
        "offset": offset,
        "prefix": digest(data[:offset]),
        "chunk_bytes": chunk_size,
        "complete": complete,
    }, value
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def setup(directory: Path, name: str, **policy: int) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    config = work / "transfer.json"
    config.write_text(json.dumps({"chunk_bytes": 1024, "io_ms": 500, "session_ms": 10000, "pause_ms": 10, **policy}))
    return work, {
        "XFER_CONFIG": str(config),
        "XFER_ROOT": str(work / "received"),
        "XFER_STOP": str(work / "stop"),
        "XFER_PORT": "0",
        "XFER_MODE": "receive",
        "XFER_FAULT": "",
    }


def checkpoint(env: dict[str, str], name: str) -> Path:
    return Path(env["XFER_ROOT"]) / ".incoming" / (name + ".json")


def partial(env: dict[str, str], name: str) -> Path:
    return checkpoint(env, name).with_name(name + ".part")


def target(env: dict[str, str], name: str) -> Path:
    return Path(env["XFER_ROOT"]) / name


def stop(server: Server, env: dict[str, str]) -> None:
    Path(env["XFER_STOP"]).touch()
    assert server.process.wait(timeout=3) == 0
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def complete(peer: Peer, wanted: dict, data: bytes, offset: int, chunk_size: int) -> None:
    for start in range(offset, len(data), chunk_size):
        end = min(start + chunk_size, len(data))
        receipt(peer.chunk(start, data[start:end]), data, end, chunk_size)
    receipt(peer.finish(), data, len(data), chunk_size, True)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def rejected(peer: Peer) -> None:
    try:
        answer = read_json(peer.socket)
        assert answer["ok"] is False and isinstance(answer["error"], str), answer
    except (EOFError, ConnectionResetError):
        pass
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@contextlib.contextmanager
def fixture(handler: Callable[[socket.socket], None], connections: int = 1) -> Iterator[tuple[int, list]]:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    listener.settimeout(0.1)
    errors = []
    stopped = threading.Event()
    count = []

    def run() -> None:
        try:
            while len(count) < connections and not stopped.is_set():
                try:
                    stream, _ = listener.accept()
                except TimeoutError:
                    continue
                with stream:
                    stream.settimeout(5)
                    count.append(1)
                    handler(stream)
        except Exception as error:  # noqa: BLE001 - surface fixture-thread failures in the caller
            errors.append(repr(error))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    worker = threading.Thread(target=run)
    worker.start()
    try:
        yield listener.getsockname()[1], count
    finally:
        stopped.set()
        worker.join(timeout=6)
        listener.close()
        assert not worker.is_alive() and not errors, errors
    return


def client_env(env: dict[str, str], source: Path, port: int, name: str) -> dict[str, str]:
    return dict(
        env, XFER_MODE="send", XFER_PORT=str(port), XFER_HOST="127.0.0.1", XFER_SOURCE=str(source), XFER_NAME=name
    )


def exercise_pair(receiver: Application, sender: Application, work: Path) -> dict:
    directory, env = setup(work, "pair", chunk_bytes=8192, attempts=3)
    source = directory / "source.bin"
    data = bytes(range(256)) * 300 + b"tail\x00\xff"
    source.write_bytes(data)
    name = "Résumé 世界.bin"
    with receiver.server(directory, env) as server:
        observed = []

        # Drop the connection after the receiver commits one chunk but before its
        # ACK reaches the sender. On retry relay all frames and inspect the offset.
        def relay(stream: socket.socket) -> None:
            with socket.create_connection(("127.0.0.1", server.port), timeout=5) as upstream:
                wanted = read_json(stream)
                upstream.sendall(control(wanted))
                hello = read_json(upstream)
                observed.append(hello["offset"])
                stream.sendall(control(hello))
                if hello["complete"]:
                    return
                while True:
                    command = read_json(stream)
                    upstream.sendall(control(command))
                    if command["op"] == "chunk":
                        upstream.sendall(frame(receive(stream)))
                    answer = read_json(upstream)
                    if len(observed) == 1:
                        return
                    stream.sendall(control(answer))
                    if answer["complete"]:
                        return
            return

        with fixture(relay, connections=2) as (port, calls):
            result = sender.run(directory, client_env(env, source, port, name), timeout=25)
        assert result.returncode == 0, result.stdout + result.stderr
        summary = json.loads(result.stdout)
        assert summary["attempts"] == 2 and summary["resumed_from"] == 8192 and summary["complete"] is True
        assert observed == [0, 8192] and len(calls) == 2
        assert target(env, name).read_bytes() == data and not partial(env, name).exists()
        again = sender.run(directory, client_env(env, source, server.port, name))
        assert again.returncode == 0 and json.loads(again.stdout)["resumed_from"] == len(data)
        stop(server, env)
    return {"bytes": len(data), "sha256": digest(data), "resume": observed, "idempotent_completion": True}


def check(app: Application, directory: Path) -> dict:
    pair = exercise_pair(app, app, directory)
    data = bytes(range(251)) * 17 + "终点".encode()
    name = "payload.bin"
    wanted = manifest(name, data)
    work, env = setup(directory, "resume")
    with app.server(work, env) as server:
        with contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted, split=True), data, 0, 1024)
            receipt(peer.chunk(0, data[:1024]), data, 1024, 1024)
        saved = json.loads(checkpoint(env, name).read_text())
        assert saved["offset"] == 1024 and not target(env, name).exists()
        # Simulate an interrupted write beyond the last durable checkpoint.
        with partial(env, name).open("ab") as stream:
            stream.write(data[1024:1300])
        with contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted), data, 1024, 1024)
            assert partial(env, name).stat().st_size == 1024
            before = checkpoint(env, name).read_bytes()
            assert peer.chunk(1024, data[1024:2048], "0" * 64)["ok"] is False
            assert checkpoint(env, name).read_bytes() == before and partial(env, name).read_bytes() == data[:1024]
        with contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted), data, 1024, 1024)
            complete(peer, wanted, data, 1024, 1024)
        assert target(env, name).read_bytes() == data and not partial(env, name).exists()
        assert json.loads(checkpoint(env, name).read_text())["phase"] == "published"
        with contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted), data, len(data), 1024, True)
        with contextlib.closing(Peer(server)) as peer:
            empty = manifest("empty.bin", b"")
            receipt(peer.open(empty), b"", 0, 1024)
            receipt(peer.finish(), b"", 0, 1024, True)
        assert target(env, "empty.bin").read_bytes() == b""
        stop(server, env)
    # Restart validates the published file; an unrelated preexisting destination
    # is never overwritten, even if it happens to contain the requested bytes.
    Path(env["XFER_STOP"]).unlink()
    with app.server(work, env) as server:
        with contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted), data, len(data), 1024, True)
        for contents in [b"different", data]:
            target(env, "existing.bin").write_bytes(contents)
            with contextlib.closing(Peer(server)) as peer:
                assert peer.open(manifest("existing.bin", data))["ok"] is False
            assert target(env, "existing.bin").read_bytes() == contents
        stop(server, env)
    faults = []
    for boundary in ["after_write", "after_checkpoint", "before_publish", "after_publish", "after_cleanup"]:
        work, env = setup(directory, boundary)
        with app.server(work, dict(env, XFER_FAULT=boundary)) as server, contextlib.closing(Peer(server)) as peer:
            receipt(peer.open(wanted), data, 0, 1024)
            if boundary in ["after_write", "after_checkpoint"]:
                peer.socket.sendall(
                    control({"op": "chunk", "offset": 0, "sha256": digest(data[:1024])}) + frame(data[:1024])
                )
            else:
                for start in range(0, len(data), 1024):
                    receipt(peer.chunk(start, data[start : start + 1024]), data, min(start + 1024, len(data)), 1024)
                peer.socket.sendall(control({"op": "finish"}))
            assert server.process.wait(timeout=3) == 75
        stored = json.loads(checkpoint(env, name).read_text())
        expected_offset = 0 if boundary == "after_write" else 1024 if boundary == "after_checkpoint" else len(data)
        assert stored["offset"] == expected_offset
        with app.server(work, env) as server, contextlib.closing(Peer(server)) as peer:
            answer = peer.open(wanted)
            receipt(
                answer, data, expected_offset, 1024, boundary in ["before_publish", "after_publish", "after_cleanup"]
            )
            if not answer["complete"]:
                complete(peer, wanted, data, expected_offset, 1024)
            assert target(env, name).read_bytes() == data and not partial(env, name).exists()
            stop(server, env)
        faults.append(boundary)
    work, env = setup(directory, "killed")
    with app.server(work, env) as server, contextlib.closing(Peer(server)) as peer:
        peer.open(wanted)
        peer.chunk(0, data[:1024])
        peer.socket.sendall(
            control({"op": "chunk", "offset": 1024, "sha256": digest(data[1024:2048])}) + frame(data[1024:2048])[:-50]
        )
        time.sleep(0.03)
        server.process.kill()
        server.process.wait(timeout=3)
    with app.server(work, env) as server, contextlib.closing(Peer(server)) as peer:
        receipt(peer.open(wanted), data, 1024, 1024)
        complete(peer, wanted, data, 1024, 1024)
        stop(server, env)
    invalid = check_rejections(app, directory, data)
    startup = check_startup(app, directory)
    sender_cases = check_sender(app, directory)
    # Both ends must stream a file larger than their address-space limit. The
    # fixture writes/compares incrementally as well, to keep verification cheap.
    work, env = setup(directory, "memory", chunk_bytes=65536, max_bytes=201326592, session_ms=300000, io_ms=3000)
    source = work / "large.bin"
    block = bytes(range(256)) * 4096
    with source.open("wb") as stream:
        for _ in range(160):
            stream.write(block)
    limiter = shutil.which("prlimit")
    assert limiter, "Linux prlimit is required"
    limited = Application([limiter, "--as=134217728", "--", *app.command], app.engine)
    with limited.server(work, env) as server:
        result = limited.run(work, client_env(env, source, server.port, "large.bin"), timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        assert target(env, "large.bin").stat().st_size == source.stat().st_size
        with source.open("rb") as original, target(env, "large.bin").open("rb") as copied:
            assert hashlib.file_digest(original, "sha256").digest() == hashlib.file_digest(copied, "sha256").digest()
        stop(server, env)
    return {
        "same_engine_pair": pair,
        "checkpoints": faults,
        "killed_partial_chunk": "resumed at 1024",
        "receiver_rejections": invalid,
        "startup_rejections": startup,
        "sender_checks": sender_cases,
        "memory": {"file_bytes": 160 * 1048576, "address_space_bytes_per_process": 134217728},
        "publication": "exact bytes, empty files, no overwrite, repeat completion, validated restart",
    }


def check_rejections(app: Application, directory: Path, data: bytes) -> int:
    work, env = setup(directory, "invalid", max_files=64)
    rejected_count = 0
    with app.server(work, env) as server:
        for index, name in enumerate(
            ["", ".", "..", "../escape", "/absolute", "a/b", "a\\b", ".incoming", "a\x00b", "a\nb", "x" * 241]
        ):
            with contextlib.closing(Peer(server)) as peer:
                assert peer.open(manifest(name, data))["ok"] is False, index
            rejected_count += 1
        for patch in [
            {"version": 2},
            {"version": True},
            {"size": -1},
            {"size": True},
            {"size": 134217729},
            {"sha256": "A" * 64},
            {"sha256": "bad"},
            {"extra": 1},
        ]:
            with contextlib.closing(Peer(server)) as peer:
                assert peer.open(dict(manifest("invalid.bin", data), **patch))["ok"] is False, patch
            rejected_count += 1
        for raw in [
            b"\x00\x00\x00\x00",
            struct.pack("!I", 1025),
            struct.pack("!I", 0xFFFFFFFF),
            frame(b"not json"),
            frame(b"\xff"),
            frame(b"[]"),
        ]:
            with contextlib.closing(Peer(server)) as peer:
                peer.socket.sendall(raw)
                rejected(peer)
            rejected_count += 1
        for index, command in enumerate(
            [
                {"op": "unknown"},
                {"op": "finish", "extra": 1},
                {"op": "chunk", "offset": -1, "sha256": digest(b"x")},
                {"op": "chunk", "offset": True, "sha256": digest(b"x")},
            ]
        ):
            with contextlib.closing(Peer(server)) as peer:
                peer.open(manifest(f"command{index}", data))
                peer.socket.sendall(control(command))
                rejected(peer)
            rejected_count += 1
        for index, raw in enumerate([struct.pack("!I", 0), struct.pack("!I", 1025), struct.pack("!I", 0xFFFFFFFF)]):
            with contextlib.closing(Peer(server)) as peer:
                peer.open(manifest(f"length{index}", data))
                peer.socket.sendall(control({"op": "chunk", "offset": 0, "sha256": digest(b"x")}) + raw)
                rejected(peer)
            rejected_count += 1
        with contextlib.closing(Peer(server)) as peer:
            peer.open(manifest("short", b"x"))
            assert peer.chunk(0, b"too long")["ok"] is False
        rejected_count += 1
        with contextlib.closing(Peer(server)) as peer:
            peer.open(manifest("unfinished", data))
            assert peer.finish()["ok"] is False
        rejected_count += 1
        with contextlib.closing(Peer(server)) as peer:
            peer.open(dict(manifest("whole_digest", b"abc"), sha256="0" * 64))
            assert peer.chunk(0, b"abc")["ok"] is True
            assert peer.finish()["ok"] is False
            assert not target(env, "whole_digest").exists()
        rejected_count += 1
        # Corrupt prefix, missing prefix, forged metadata and conflicting manifests.
        for mode in ["changed", "missing", "offset", "prefix", "phase", "version", "fields", "manifest"]:
            name = "corrupt_" + mode
            wanted = manifest(name, data)
            with contextlib.closing(Peer(server)) as peer:
                peer.open(wanted)
                peer.chunk(0, data[:1024])
            if mode == "changed":
                partial(env, name).write_bytes(b"x" * 1024)
            elif mode == "missing":
                partial(env, name).unlink()
            elif mode == "manifest":
                wanted["sha256"] = "0" * 64
            else:
                row = json.loads(checkpoint(env, name).read_text())
                if mode == "offset":
                    row["offset"] = len(data) + 1
                elif mode == "prefix":
                    row["prefix"] = "0" * 64
                elif mode == "phase":
                    row["phase"] = "published"
                elif mode == "version":
                    row["version"] = 2
                else:
                    row["unexpected"] = True
                checkpoint(env, name).write_text(json.dumps(row))
            before = checkpoint(env, name).read_bytes()
            with contextlib.closing(Peer(server)) as peer:
                assert peer.open(wanted)["ok"] is False, mode
            assert checkpoint(env, name).read_bytes() == before and not target(env, name).exists()
            rejected_count += 1
        for mode in ["target_symlink", "part_symlink", "meta_symlink", "alias", "orphan"]:
            name = "path_" + mode
            outside = work / (name + ".outside")
            outside.write_bytes(b"untouched")
            if mode == "target_symlink":
                target(env, name).symlink_to(outside)
            elif mode == "part_symlink":
                partial(env, name).symlink_to(outside)
            elif mode == "meta_symlink":
                checkpoint(env, name).symlink_to(outside)
            elif mode == "orphan":
                partial(env, name).write_bytes(b"untouched")
            else:
                checkpoint(env, name).write_text(json.dumps({"not": "a checkpoint"}))
                partial(env, name).hardlink_to(checkpoint(env, name))
            with contextlib.closing(Peer(server)) as peer:
                assert peer.open(manifest(name, data))["ok"] is False, mode
            assert outside.read_bytes() == b"untouched"
            rejected_count += 1
        # A receiving prefix cannot overwrite a destination that appeared later.
        with contextlib.closing(Peer(server)) as peer:
            peer.open(manifest("appeared", data))
            peer.chunk(0, data[:1024])
        target(env, "appeared").write_bytes(b"unrelated")
        with contextlib.closing(Peer(server)) as peer:
            assert peer.open(manifest("appeared", data))["ok"] is False
        assert target(env, "appeared").read_bytes() == b"unrelated"
        rejected_count += 1
        # Publication must revalidate the bytes and refuse a separately created
        # destination, even when that destination has the same checksum.
        for mode in ["same_bytes", "changed_part"]:
            name = "finish_" + mode
            with contextlib.closing(Peer(server)) as peer:
                receipt(peer.open(manifest(name, b"abc")), b"abc", 0, 1024)
                receipt(peer.chunk(0, b"abc"), b"abc", 3, 1024)
                if mode == "same_bytes":
                    target(env, name).write_bytes(b"abc")
                    inode = target(env, name).stat().st_ino
                    assert inode != partial(env, name).stat().st_ino
                else:
                    partial(env, name).write_bytes(b"xyz")
                assert peer.finish()["ok"] is False
                assert partial(env, name).read_bytes() == (b"abc" if mode == "same_bytes" else b"xyz")
                if mode == "same_bytes":
                    assert target(env, name).read_bytes() == b"abc" and target(env, name).stat().st_ino == inode
                else:
                    assert not target(env, name).exists()
            rejected_count += 1
        name = "oversized_checkpoint"
        checkpoint(env, name).write_bytes(b" " * 8193)
        with contextlib.closing(Peer(server)) as peer:
            assert peer.open(manifest(name, b""))["ok"] is False
        assert checkpoint(env, name).stat().st_size == 8193 and not partial(env, name).exists()
        rejected_count += 1
        stop(server, env)
    for mode in ["frame", "session"]:
        work, env = setup(
            directory,
            "deadline_" + mode,
            io_ms=150 if mode == "frame" else 1000,
            session_ms=1000 if mode == "frame" else 200,
        )
        with app.server(work, env) as server, contextlib.closing(Peer(server)) as peer:
            peer.open(manifest("slow", data))
            started = time.monotonic()
            if mode == "frame":
                peer.socket.sendall(struct.pack("!I", 100))
                for _ in range(4):
                    time.sleep(0.03)
                    peer.socket.sendall(b" ")
                rejected(peer)
                assert time.monotonic() - started < 0.8
            else:
                for offset in range(3):
                    receipt(peer.chunk(offset, data[offset : offset + 1]), data, offset + 1, 1024)
                    time.sleep(0.08)
                peer.socket.sendall(
                    control({"op": "chunk", "offset": 3, "sha256": digest(data[3:4])}) + frame(data[3:4])
                )
                rejected(peer)
                assert time.monotonic() - started < 0.9
            assert not target(env, "slow").exists()
            stop(server, env)
        rejected_count += 1
    work, env = setup(directory, "capacity", max_files=1)
    with app.server(work, env) as server:
        with contextlib.closing(Peer(server)) as peer:
            peer.open(manifest("first", b""))
            peer.finish()
        with contextlib.closing(Peer(server)) as peer:
            assert peer.open(manifest("second", b""))["ok"] is False
        stop(server, env)
    return rejected_count + 1


def check_startup(app: Application, directory: Path) -> int:
    bounds = {
        "max_bytes": (0, 1073741824),
        "max_files": (1, 1024),
        "chunk_bytes": (1, 65536),
        "io_ms": (50, 30000),
        "session_ms": (100, 300000),
        "attempts": (1, 10),
        "pause_ms": (0, 5000),
    }
    configurations = [{"unknown": 1}, [], {"attempts": "3"}, {"attempts": 1.5}]
    for key, (low, high) in bounds.items():
        configurations.extend([{key: low - 1}, {key: high + 1}, {key: True}])
    cases = [(json.dumps(value), {}) for value in configurations]
    cases.extend([("not JSON", {}), (" " * 65537, {})])
    cases.extend(("{}", {"XFER_PORT": port}) for port in ["-1", "65536", "true", "1.5", '"3"', "bad"])
    cases.append(("{}", {"XFER_MODE": "other"}))
    for index, (content, settings) in enumerate(cases):
        work, env = setup(directory, "startup_" + str(index))
        Path(env["XFER_CONFIG"]).write_text(content)
        result = app.run(work, dict(env, **settings), timeout=5)
        assert result.returncode != 0 and "LISTENING" not in result.stdout, (index, result.stdout)
    for mode in ["stage_symlink", "config_inside", "stop_inside"]:
        work, env = setup(directory, "startup_" + mode)
        root = Path(env["XFER_ROOT"])
        root.mkdir()
        if mode == "stage_symlink":
            outside = work / "outside"
            outside.mkdir()
            (root / ".incoming").symlink_to(outside, target_is_directory=True)
        elif mode == "config_inside":
            config = root / "policy.json"
            config.write_text("{}")
            env["XFER_CONFIG"] = str(config)
        else:
            env["XFER_STOP"] = str(root / "stop")
        result = app.run(work, env, timeout=5)
        assert result.returncode != 0 and "LISTENING" not in result.stdout, mode
        if mode == "stage_symlink":
            assert list(outside.iterdir()) == []
    return len(cases) + 3


def check_sender(app: Application, directory: Path) -> list[str]:
    cases = [
        "resume_offset",
        "resume_prefix",
        "complete_early",
        "remote_chunk",
        "chunk_offset",
        "chunk_prefix",
        "premature",
        "changed_chunk_limit",
        "final_digest",
        "final_incomplete",
        "source_change",
        "source_size",
        "normal",
        "retry_exhausted",
        "remote_error",
    ]
    for mode in cases:
        attempts = 3 if mode in ["retry_exhausted", "remote_error"] else 1
        work, env = setup(directory, "sender_" + mode, attempts=attempts)
        source = work / "source.bin"
        data = bytes(range(256)) * 12
        source.write_bytes(data)
        observed = []

        def peer(
            stream: socket.socket,
            mode: str = mode,
            data: bytes = data,
            source: Path = source,
            observed: list = observed,
        ) -> None:
            wanted = read_json(stream)
            assert wanted == manifest("sent.bin", data)
            if mode == "retry_exhausted":
                return
            if mode == "remote_error":
                stream.sendall(control({"ok": False, "error": "fixture capacity exhausted"}))
                return
            prefix = {"ok": True, "offset": 0, "prefix": digest(b""), "chunk_bytes": 1024, "complete": False}
            if mode == "resume_offset":
                prefix["offset"] = len(data) + 1
            elif mode == "resume_prefix":
                prefix["prefix"] = "0" * 64
            elif mode == "complete_early":
                prefix["complete"] = True
            elif mode == "remote_chunk":
                prefix["chunk_bytes"] = 65537
            elif mode == "source_size":
                source.write_bytes(b"short")
            stream.sendall(control(prefix))
            received = b""
            try:
                while True:
                    command = read_json(stream)
                    observed.append(command["op"])
                    if command["op"] == "finish":
                        answer = {
                            "ok": True,
                            "offset": len(received),
                            "prefix": digest(received),
                            "chunk_bytes": 1024,
                            "complete": True,
                        }
                        if mode == "final_digest":
                            answer["prefix"] = "0" * 64
                        elif mode == "final_incomplete":
                            answer["complete"] = False
                        stream.sendall(control(answer))
                        return
                    chunk = receive(stream)
                    assert command["offset"] == len(received) and command["sha256"] == digest(chunk)
                    received += chunk
                    answer = {
                        "ok": True,
                        "offset": len(received),
                        "prefix": digest(received),
                        "chunk_bytes": 1024,
                        "complete": False,
                    }
                    if mode == "chunk_offset":
                        answer["offset"] += 1
                    elif mode == "chunk_prefix":
                        answer["prefix"] = "0" * 64
                    elif mode == "premature":
                        answer["complete"] = True
                    elif mode == "changed_chunk_limit":
                        answer["chunk_bytes"] = 512
                    elif mode == "source_change" and len(received) == 1024:
                        with source.open("r+b") as output:
                            output.seek(2048)
                            output.write(b"changed")
                    stream.sendall(control(answer))
            except (EOFError, ConnectionResetError):
                return
            return

        with fixture(peer, connections=attempts) as (port, calls):
            result = app.run(work, client_env(env, source, port, "sent.bin"))
        assert len(calls) == attempts, mode
        if mode == "normal":
            assert result.returncode == 0 and observed == ["chunk"] * 3 + ["finish"], result.stderr
        else:
            assert result.returncode != 0, mode
            if mode in ["resume_offset", "resume_prefix", "complete_early", "remote_chunk", "source_size"]:
                assert observed == [], (mode, observed)
            if mode == "source_change":
                assert "finish" not in observed
            if mode in ["retry_exhausted", "remote_error"]:
                assert observed == [] and result.stderr.count("transfer attempt failed:") == attempts
            if mode == "remote_error":
                assert "fixture capacity exhausted" in result.stderr
    return cases
