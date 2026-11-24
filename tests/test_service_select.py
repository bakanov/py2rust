"""Ready I/O, readiness snapshots, partial sends and collection mutation parity."""

from pathlib import Path

from .test_services import parity


def test_collection_removal_and_byte_search(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import Json, json_equal
def run() -> None:
    values: list[int] = [3, 4, 5]
    assert values.pop() == 5
    assert values.pop(0) == 3 and values.pop(-1) == 4
    caught: int = 0
    try:
        values.pop()
    except Exception:
        caught = caught + 1
    values = [1, 1]
    try:
        values.pop(values.pop())
    except Exception:
        caught = caught + 1
    assert len(values) == 1 and values[0] == 1
    mapping: dict[str, int] = {"a": 1, "b": 2}
    del mapping["a"]
    assert "a" not in mapping and mapping["b"] == 2
    document: Json = {"a": [1], "b": None}
    del document["a"]
    assert json_equal(document, {"b": None})
    try:
        del document["missing"]
    except Exception:
        caught = caught + 1
    try:
        del mapping["missing"]
    except Exception:
        caught = caught + 1
    assert caught == 4
    data: bytes = b"a\\x00b\\xffa"
    assert data.find(b"\\x00b") == 1 and data.find(b"a") == 0
    assert data.find(b"long absent") == -1 and data.find(b"z") == -1 and data.find(b"") == 0
    print("checked removals and binary search passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "checked removals and binary search passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_select_ready_eof_and_blocking_interoperation(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import (
    Json, TcpStream, tcp_listen, tcp_connect, tcp_port, tcp_accept_ready, tcp_select,
    tcp_recv_ready, tcp_send_ready, tcp_recv, tcp_sendall, tcp_shutdown_write, tcp_close,
    json_bool, json_equal, monotonic,
)
def run() -> None:
    with tcp_listen("127.0.0.1", 0) as listener:
        began: float = monotonic()
        event: Json = tcp_select(listener, [], [], 30)
        assert monotonic() - began >= 0.02 and monotonic() - began < 2.0
        assert json_equal(event, {"accept": False, "read": [], "write": []})
        assert len(tcp_accept_ready(listener, 4, 2000)) == 0
        with tcp_connect("127.0.0.1", tcp_port(listener), 2000) as client:
            assert json_bool(tcp_select(listener, [], [], 500)["accept"])
            accepted: list[TcpStream] = tcp_accept_ready(listener, 1, 2000)
            assert len(accepted) == 1 and len(tcp_accept_ready(listener, 1, 2000)) == 0
            with accepted[0] as peer:
                quiet: tuple[bytes, bool] = tcp_recv_ready(peer, 10)
                assert quiet[0] == b"" and not quiet[1]
                event = tcp_select(listener, [peer], [peer, peer], 100)
                assert json_equal(event["read"], []) and json_equal(event["write"], [0, 1])
                tcp_sendall(client, b"ab")
                event = tcp_select(listener, [peer, peer], [], 500)
                assert json_equal(event["read"], [0, 1])
                part: tuple[bytes, bool] = tcp_recv_ready(peer, 1)
                assert part[0] == b"a" and not part[1]
                assert json_equal(tcp_select(listener, [peer], [], 500)["read"], [0])
                part = tcp_recv_ready(peer, 1)
                assert part[0] == b"b" and not part[1]
                assert tcp_send_ready(peer, b"reply") == 5
                assert tcp_recv(client, 5) == b"reply"
                tcp_sendall(peer, b"blocking")
                assert tcp_recv(client, 8) == b"blocking"
                tcp_shutdown_write(client)
                assert json_equal(tcp_select(listener, [peer], [], 500)["read"], [0])
                part = tcp_recv_ready(peer, 1)
                assert part[0] == b"" and part[1]
                tcp_close(peer)
                caught: bool = False
                try:
                    tcp_select(listener, [peer], [], 0)
                except Exception:
                    caught = True
                assert caught
    print("readiness, partial reads, EOF and blocking interoperation passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "readiness, partial reads, EOF and blocking interoperation passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_nonreading_peer_produces_partial_writes_without_blocking(tmp_path: Path) -> None:
    (tmp_path / "block.bin").write_bytes(b"x" * 65536)
    source = """from py2rust.stdlib import (
    TcpStream, tcp_listen, tcp_connect, tcp_port, tcp_accept_ready, tcp_select,
    tcp_send_ready, tcp_recv_ready, tcp_send_buffer, read_bytes, monotonic,
)
def run() -> None:
    with tcp_listen("127.0.0.1", 0) as listener:
        with tcp_connect("127.0.0.1", tcp_port(listener), 2000) as client:
            tcp_select(listener, [], [], 1000)
            peers: list[TcpStream] = tcp_accept_ready(listener, 1, 2000)
            with peers[0] as peer:
                tcp_send_buffer(client, 1024)
                data: bytes = read_bytes("block.bin")
                sent: int = 0
                blocked: bool = False
                partial: bool = False
                began: float = monotonic()
                for index in range(128):
                    count: int = tcp_send_ready(client, data)
                    if count == 0:
                        blocked = True
                        break
                    if count < len(data):
                        partial = True
                    sent = sent + count
                assert blocked and partial and sent > 0 and monotonic() - began < 1.0
                received: int = 0
                while received < sent:
                    assert monotonic() - began < 3.0
                    tcp_select(listener, [peer], [], 100)
                    chunk: tuple[bytes, bool] = tcp_recv_ready(peer, 65536)
                    assert not chunk[1]
                    received = received + len(chunk[0])
                assert received == sent
    print("slow peer does not block partial sends")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "slow peer does not block partial sends\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_ready_api_limits(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import (
    TcpStream, tcp_listen, tcp_connect, tcp_port, tcp_accept_ready, tcp_select,
    tcp_recv_ready, tcp_send_buffer, tcp_close,
)
def run() -> None:
    errors: int = 0
    with tcp_listen("127.0.0.1", 0) as listener:
        for limit in [0, 65]:
            try:
                tcp_accept_ready(listener, limit, 1000)
            except Exception:
                errors = errors + 1
        for timeout in [-1, 60001]:
            try:
                tcp_select(listener, [], [], timeout)
            except Exception:
                errors = errors + 1
        with tcp_connect("127.0.0.1", tcp_port(listener), 2000) as client:
            tcp_select(listener, [], [], 1000)
            peers: list[TcpStream] = tcp_accept_ready(listener, 1, 2000)
            with peers[0] as peer:
                for count in [0, 1048577]:
                    try:
                        tcp_recv_ready(peer, count)
                    except Exception:
                        errors = errors + 1
                for size in [1023, 1048577]:
                    try:
                        tcp_send_buffer(peer, size)
                    except Exception:
                        errors = errors + 1
                large: list[TcpStream] = []
                for index in range(1025):
                    large.append(peer)
                try:
                    tcp_select(listener, large, [], 0)
                except Exception:
                    errors = errors + 1
                try:
                    tcp_select(listener, [], large, 0)
                except Exception:
                    errors = errors + 1
                tcp_close(peer)
                try:
                    tcp_recv_ready(peer, 1)
                except Exception:
                    errors = errors + 1
    assert errors == 11
    print("ready API limits passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "ready API limits passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
