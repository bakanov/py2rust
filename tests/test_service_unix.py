"""Unix socket resources, owned-path cleanup and bounded stream operations."""

import socket
import tempfile
from pathlib import Path

import pytest

from .test_services import parity, run


def test_unix_stream_resources_and_readiness(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="p2r-unix-") as directory:
        path = str(Path(directory) / "世界.sock")
        data = Path(directory) / "data"
        data.write_bytes(b"x" * 65536)
        parity(
            tmp_path,
            f"""
from py2rust.stdlib import (
    Json, UnixListener, UnixStream, unix_listen, unix_connect, unix_accept_timeout,
    unix_recv, unix_sendall, unix_set_deadline, unix_shutdown_write,
    unix_close, unix_close_listener, unix_select, unix_accept_ready,
    unix_send_ready, unix_recv_ready, unix_send_buffer, path_exists,
    json_bool, json_int, json_array, sleep, monotonic, read_bytes,
)
def close_on_return(handle: UnixStream) -> None:
    with handle as scoped:
        return
def check() -> None:
    failed: bool = False
    listener: UnixListener = unix_listen({path!r}, False)
    with listener as bound:
        assert path_exists({path!r})
        assert not json_bool(unix_select(bound, [], [], 0)["accept"])
        with unix_connect({path!r}, 1000) as client:
            assert json_bool(unix_select(bound, [], [], 1000)["accept"])
            peers: list[UnixStream] = unix_accept_ready(bound, 2, 1000)
            assert len(peers) == 1
            assert len(unix_accept_ready(bound, 1, 1000)) == 0
            with peers[0] as peer:
                assert unix_recv_ready(peer, 32) == (b"", False)
                unix_send_buffer(client, 1024)
                unix_sendall(client, "世界".encode())
                ready: list[Json] = json_array(unix_select(bound, [peer, peer], [client], 1000)["read"])
                assert len(ready) == 2 and json_int(ready[0]) == 0 and json_int(ready[1]) == 1
                assert unix_recv(peer, 64).decode() == "世界"
                assert unix_send_ready(peer, b"reply") == 5
                assert unix_recv(client, 64) == b"reply"
                block: bytes = read_bytes({str(data)!r})
                blocked: bool = False
                partial: bool = False
                total: int = 0
                for turn in range(100):
                    written: int = unix_send_ready(client, block)
                    total = total + written
                    if written == 0:
                        blocked = True
                        break
                    if written < len(block):
                        partial = True
                assert blocked and partial and total > 0
                drained: int = 0
                while drained < total:
                    chunk: tuple[bytes, bool] = unix_recv_ready(peer, 65536)
                    assert not chunk[1] and len(chunk[0]) > 0
                    drained = drained + len(chunk[0])
                assert unix_send_ready(client, b"z") == 1
                assert unix_recv(peer, 1) == b"z"
                unix_shutdown_write(client)
                assert unix_recv(peer, 64) == b""
                unix_sendall(peer, b"after EOF")
                assert unix_recv(client, 64) == b"after EOF"
                unix_set_deadline(peer, 10)
                sleep(0.02)
                failed = False
                try:
                    unix_recv(peer, 1)
                except Exception:
                    failed = True
                assert failed
        client2: UnixStream = unix_connect({path!r}, 1000)
        with unix_accept_timeout(bound, 1000, 1000) as peer2:
            close_on_return(client2)
            assert unix_recv(peer2, 1) == b""
        failed = False
        try:
            unix_sendall(client2, b"closed")
        except Exception:
            failed = True
        assert failed
        started: float = monotonic()
        failed = False
        try:
            unix_accept_timeout(bound, 30, 1000)
        except Exception:
            failed = True
        assert failed and monotonic() - started < 0.5
    assert not path_exists({path!r})
    unix_close_listener(listener)
    print("Unix resources, deadlines, readiness and half-close passed")
    return
if __name__ == "__main__":
    check()
""",
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("engine", ["python", "rust"])
def test_unix_path_ownership(tmp_path: Path, engine: str) -> None:
    with tempfile.TemporaryDirectory(prefix="p2r-path-") as directory:
        root = Path(directory)
        stale = root / "stale.sock"
        with socket.socket(socket.AF_UNIX) as old:
            old.bind(str(stale))
        ordinary = root / "ordinary"
        ordinary.write_text("untouched")
        link = root / "link"
        link.symlink_to(ordinary)
        folder = root / "folder"
        folder.mkdir()
        result = run(
            tmp_path,
            f"""
from py2rust.stdlib import (
    UnixListener, unix_listen, unix_connect, unix_accept_timeout, unix_close_listener,
    path_exists, remove_file, write_text, read_text,
)
def check() -> None:
    failed: bool = False
    try:
        unix_listen({str(stale)!r}, False)
    except Exception:
        failed = True
    assert failed
    listener: UnixListener = unix_listen({str(stale)!r}, True)
    with listener as bound:
        failed = False
        try:
            unix_listen({str(stale)!r}, True)
        except Exception:
            failed = True
        assert failed
        with unix_connect({str(stale)!r}, 1000) as client:
            with unix_accept_timeout(bound, 1000, 1000) as probe:
                pass
        remove_file({str(stale)!r})
        write_text({str(stale)!r}, "replacement")
    unix_close_listener(listener)
    assert read_text({str(stale)!r}) == "replacement"
    for path in [{str(ordinary)!r}, {str(link)!r}, {str(folder)!r}]:
        failed = False
        try:
            unix_listen(path, True)
        except Exception:
            failed = True
        assert failed
    assert read_text({str(ordinary)!r}) == "untouched"
    print("ownership passed")
    return
if __name__ == "__main__":
    check()
""",
            engine,
        )
        assert result.returncode == 0, result.stderr
        assert stale.read_text() == "replacement" and link.is_symlink() and folder.is_dir()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_unix_invalid_bounds_and_scope_errors(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="p2r-bounds-") as directory:
        path = str(Path(directory) / "bus.sock")
        oversized = Path(directory) / "oversized"
        oversized.write_bytes(b"x" * 1048577)
        parity(
            tmp_path,
            f"""
from py2rust.stdlib import (
    unix_listen, unix_connect, unix_accept_timeout, unix_accept_ready,
    unix_select, unix_recv, unix_sendall, unix_send_buffer, unix_set_deadline,
    unix_recv_ready, path_exists, read_bytes,
)
def check() -> None:
    failures: int = 0
    for path in ["", "\\x00abstract", {directory!r} + "/", {(directory + "/" + "x" * 108)!r}]:
        try:
            unix_listen(path, False)
        except Exception:
            failures = failures + 1
    assert failures == 4
    with unix_listen({path!r}, False) as listener:
        for value in [0, -1, 86400001]:
            try:
                unix_connect({path!r}, value)
            except Exception:
                failures = failures + 1
        with unix_connect({path!r}, 1000) as client:
            with unix_accept_timeout(listener, 1000, 1000) as peer:
                for value in [0, -1, 1048577]:
                    try:
                        unix_recv(peer, value)
                    except Exception:
                        failures = failures + 1
                for value in [1023, 1048577]:
                    try:
                        unix_send_buffer(peer, value)
                    except Exception:
                        failures = failures + 1
                try:
                    unix_set_deadline(peer, 0)
                except Exception:
                    failures = failures + 1
                try:
                    unix_sendall(peer, read_bytes({str(oversized)!r}))
                except Exception:
                    failures = failures + 1
        for value in [0, 65]:
            try:
                unix_accept_ready(listener, value, 1000)
            except Exception:
                failures = failures + 1
        for value in [-1, 60001]:
            try:
                unix_select(listener, [], [], value)
            except Exception:
                failures = failures + 1
    assert failures == 18
    assert not path_exists({path!r})
    try:
        with unix_listen({path!r}, False) as failing:
            assert False, "deliberate"
    except Exception:
        pass
    assert not path_exists({path!r})
    print("bounds and error cleanup passed")
    return
if __name__ == "__main__":
    check()
""",
        )
    return  # noqa: PLR1711 - explicit return required by repository guidelines
