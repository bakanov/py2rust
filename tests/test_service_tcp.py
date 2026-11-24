"""TCP resources, binary framing primitives and deadlines in the project/service profile."""

import socket
from pathlib import Path

import pytest

from .test_services import parity


def test_binary_integers_and_slices(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import int_from_bytes, int_to_bytes
def run() -> None:
    for order in ["big", "little"]:
        for number in [0, 1, 255, 256, 4294967295, 9223372036854775807]:
            data: bytes = number.to_bytes(8, order)
            assert int.from_bytes(data, order) == number
            assert int_to_bytes(number, 8, order) == data
        assert int_from_bytes(b"", order) == 0 and int_to_bytes(0, 0, order) == b""
    assert int_to_bytes(4294967295, 4, "big") == b"\\xff\\xff\\xff\\xff"
    assert int_from_bytes(b"\\x00\\x01\\x02\\x03", "big") == 66051
    assert int_from_bytes(b"\\x00\\x01\\x02\\x03", "little") == 50462976
    value: bytes = b"\\x00abc\\xff"
    assert value[-2:] == b"c\\xff" and value[:2] == b"\\x00a"
    assert value[-99:99] == value and value[3:1] == b""
    assert value[99:] == b"" and value[:-99] == b""
    assert value[:] + b"!" == b"\\x00abc\\xff!"
    errors: int = 0
    for length in [-1, 9]:
        try:
            int_to_bytes(0, length, "big")
        except Exception:
            errors = errors + 1
    for number in [-1, 256]:
        try:
            int_to_bytes(number, 1, "big")
        except Exception:
            errors = errors + 1
    for raw in [b"123456789", b"\\xff\\xff\\xff\\xff\\xff\\xff\\xff\\xff"]:
        try:
            int_from_bytes(raw, "big")
        except Exception:
            errors = errors + 1
    try:
        int_to_bytes(1, 0, "big")
    except Exception:
        errors = errors + 1
    try:
        int_from_bytes(b"", "unknown")
    except Exception:
        errors = errors + 1
    try:
        int_to_bytes(0, 0, "unknown")
    except Exception:
        errors = errors + 1
    assert errors == 9
    print("binary vectors passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "binary vectors passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_tcp_binary_half_close_and_scopes(tmp_path: Path, host: str) -> None:
    if host == "::1":
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as probe:
                probe.bind((host, 0))
        except OSError:
            pytest.skip("IPv6 loopback unavailable")
    source = """from py2rust.stdlib import (
    TcpStream, TcpListener, tcp_listen, tcp_port, tcp_connect, tcp_accept_timeout,
    tcp_recv, tcp_sendall, tcp_shutdown_write, tcp_close, tcp_close_listener,
)
def collect(stream: TcpStream) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk: bytes = tcp_recv(stream, 2)
        if len(chunk) == 0:
            break
        chunks.append(chunk)
    return b"".join(chunks)
def close_on_return(handle: TcpStream) -> None:
    with handle as stream:
        return
def run() -> None:
    host: str = "HOST"
    listener: TcpListener = tcp_listen(host, 0)
    errors: int = 0
    with listener as bound:
        with tcp_connect(host, tcp_port(bound), 2000) as client:
            with tcp_accept_timeout(bound, 1000, 2000) as peer:
                tcp_sendall(client, b"\\x00hello")
                tcp_sendall(client, b"\\xffworld")
                tcp_shutdown_write(client)
                data: bytes = collect(peer)
                assert data == b"\\x00hello\\xffworld"
                tcp_sendall(peer, data)
                tcp_shutdown_write(peer)
                assert collect(client) == data
            tcp_close(client)
        client2: TcpStream = tcp_connect(host, tcp_port(bound), 2000)
        with tcp_accept_timeout(bound, 1000, 2000) as peer2:
            close_on_return(client2)
            assert tcp_recv(peer2, 1) == b""
        try:
            tcp_recv(client2, 1)
        except Exception:
            errors = errors + 1
        client3: TcpStream = tcp_connect(host, tcp_port(bound), 2000)
        with tcp_accept_timeout(bound, 1000, 2000) as peer3:
            try:
                with client3 as scoped:
                    assert False, "test unwind"
            except Exception:
                errors = errors + 1
            assert tcp_recv(peer3, 1) == b""
        try:
            with client3 as closed:
                print("unreachable")
        except Exception:
            errors = errors + 1
        assert errors == 3
    try:
        tcp_port(listener)
    except Exception:
        errors = errors + 1
    tcp_close_listener(listener)
    assert errors == 4
    print("TCP bytes EOF and scoped aliases passed")
    return
if __name__ == "__main__":
    run()
""".replace("HOST", host)
    assert parity(tmp_path, source) == "TCP bytes EOF and scoped aliases passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_tcp_deadlines_and_validation(tmp_path: Path) -> None:
    (tmp_path / "large").write_bytes(b"x" * 1048577)
    source = """from py2rust.stdlib import (
    tcp_listen, tcp_port, tcp_connect, tcp_accept_timeout, tcp_recv, tcp_sendall,
    tcp_set_deadline, sleep, monotonic, read_bytes,
)
def run() -> None:
    errors: int = 0
    for host in ["localhost", "::1%0"]:
        try:
            tcp_listen(host, 0)
        except Exception:
            errors = errors + 1
    for port in [-1, 65536]:
        try:
            tcp_listen("127.0.0.1", port)
        except Exception:
            errors = errors + 1
    with tcp_listen("127.0.0.1", 0) as listener:
        for timeout in [0, -1, 86400001]:
            try:
                tcp_connect("127.0.0.1", tcp_port(listener), timeout)
            except Exception:
                errors = errors + 1
            try:
                tcp_accept_timeout(listener, timeout, 1000)
            except Exception:
                errors = errors + 1
            try:
                tcp_accept_timeout(listener, 1000, timeout)
            except Exception:
                errors = errors + 1
        began: float = monotonic()
        try:
            tcp_accept_timeout(listener, 40, 1000)
        except Exception:
            errors = errors + 1
        assert monotonic() - began >= 0.025 and monotonic() - began < 2.0
        with tcp_connect("127.0.0.1", tcp_port(listener), 2000) as client:
            with tcp_accept_timeout(listener, 1000, 2000) as peer:
                for count in [-1, 0, 1048577]:
                    try:
                        tcp_recv(peer, count)
                    except Exception:
                        errors = errors + 1
                try:
                    tcp_sendall(client, read_bytes("large"))
                except Exception:
                    errors = errors + 1
                try:
                    tcp_set_deadline(peer, 0)
                except Exception:
                    errors = errors + 1
                tcp_set_deadline(peer, 40)
                began = monotonic()
                try:
                    tcp_recv(peer, 1)
                except Exception:
                    errors = errors + 1
                assert monotonic() - began >= 0.025 and monotonic() - began < 2.0
                tcp_set_deadline(peer, 20)
                sleep(0.04)
                try:
                    tcp_sendall(peer, b"late")
                except Exception:
                    errors = errors + 1
                tcp_set_deadline(peer, 1000)
                tcp_sendall(client, b"ok")
                assert tcp_recv(peer, 2) == b"ok"
    assert errors == 21
    print("deadlines and validation passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "deadlines and validation passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
