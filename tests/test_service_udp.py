"""Datagram boundaries, exact-fit/truncated/empty payloads, deadlines and resource scopes."""

import socket
from pathlib import Path

import pytest

from .test_services import parity


@pytest.mark.parametrize("host", ["127.0.0.1", "::1"])
def test_datagram_boundaries_sources_and_truncation(tmp_path: Path, host: str) -> None:
    if host == "::1":
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as probe:
                probe.bind((host, 0))
        except OSError:
            pytest.skip("IPv6 loopback unavailable")
    (tmp_path / "large.bin").write_bytes(bytes(range(256)) * 255 + bytes(range(227)))
    source = """from py2rust.stdlib import UdpSocket, udp_bind, udp_port, udp_recvfrom, udp_sendto, read_bytes
def run() -> None:
    host: str = "HOST"
    with udp_bind(host, 0) as receiver:
        with udp_bind(host, 0) as sender:
            receiver_port: int = udp_port(receiver)
            sender_port: int = udp_port(sender)
            for value in [b"", b"abc", b"\\x00\\xff\\r\\n"]:
                udp_sendto(sender, value, host, receiver_port, 1000)
                packet: tuple[bytes, str, int, bool] = udp_recvfrom(receiver, max(1, len(value)), 1000)
                assert packet[0] == value and packet[1] == host and packet[2] == sender_port and not packet[3]
                udp_sendto(receiver, packet[0], packet[1], packet[2], 1000)
                assert udp_recvfrom(sender, 32, 1000)[0] == value
            udp_sendto(sender, b"abcdef", host, receiver_port, 1000)
            udp_sendto(sender, b"tail", host, receiver_port, 1000)
            short: tuple[bytes, str, int, bool] = udp_recvfrom(receiver, 3, 1000)
            assert short[0] == b"abc" and short[3]
            intact: tuple[bytes, str, int, bool] = udp_recvfrom(receiver, 4, 1000)
            assert intact[0] == b"tail" and not intact[3]
            large: bytes = read_bytes("large.bin")
            assert len(large) == 65507
            udp_sendto(sender, large, host, receiver_port, 1000)
            intact = udp_recvfrom(receiver, 65507, 1000)
            assert intact[0] == large and not intact[3]
    print("datagram boundaries and sources passed")
    return
if __name__ == "__main__":
    run()
""".replace("HOST", host)
    assert parity(tmp_path, source) == "datagram boundaries and sources passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_udp_deadlines_and_validation(tmp_path: Path) -> None:
    (tmp_path / "oversized.bin").write_bytes(b"x" * 65508)
    source = """from py2rust.stdlib import (
    udp_bind, udp_port, udp_recvfrom, udp_sendto, read_bytes, monotonic,
)
def run() -> None:
    errors: int = 0
    for host in ["localhost", "127.000.0.1", "fe80::1%lo"]:
        try:
            udp_bind(host, 0)
        except Exception:
            errors = errors + 1
    for port in [-1, 65536]:
        try:
            udp_bind("127.0.0.1", port)
        except Exception:
            errors = errors + 1
    with udp_bind("127.0.0.1", 0) as channel:
        for limit in [0, 65508]:
            try:
                udp_recvfrom(channel, limit, 1000)
            except Exception:
                errors = errors + 1
        for timeout in [0, 86400001]:
            try:
                udp_recvfrom(channel, 1, timeout)
            except Exception:
                errors = errors + 1
            try:
                udp_sendto(channel, b"x", "127.0.0.1", udp_port(channel), timeout)
            except Exception:
                errors = errors + 1
        try:
            udp_sendto(channel, read_bytes("oversized.bin"), "127.0.0.1", udp_port(channel), 1000)
        except Exception:
            errors = errors + 1
        for host in ["localhost", "::1"]:
            try:
                udp_sendto(channel, b"x", host, udp_port(channel), 1000)
            except Exception:
                errors = errors + 1
        for port in [0, -1, 65536]:
            try:
                udp_sendto(channel, b"x", "127.0.0.1", port, 1000)
            except Exception:
                errors = errors + 1
        began: float = monotonic()
        try:
            udp_recvfrom(channel, 8, 30)
        except Exception:
            errors = errors + 1
        elapsed: float = monotonic() - began
        assert elapsed >= 0.02 and elapsed < 1.0
        udp_sendto(channel, b"still open", "127.0.0.1", udp_port(channel), 1000)
        assert udp_recvfrom(channel, 32, 1000)[0] == b"still open"
    assert errors == 18
    print("UDP deadlines and bounds passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "UDP deadlines and bounds passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def test_udp_scope_exit_closes_aliases_and_releases_port(tmp_path: Path) -> None:
    source = """from py2rust.stdlib import UdpSocket, udp_bind, udp_port, udp_close, udp_recvfrom, udp_sendto
def finish(handle: UdpSocket) -> None:
    with handle as scoped:
        return
def run() -> None:
    handle: UdpSocket = udp_bind("127.0.0.1", 0)
    alias: UdpSocket = handle
    port: int = udp_port(handle)
    errors: int = 0
    try:
        udp_bind("127.0.0.1", port)
    except Exception:
        errors = errors + 1
    finish(handle)
    udp_close(alias)
    try:
        udp_port(alias)
    except Exception:
        errors = errors + 1
    with udp_bind("127.0.0.1", port) as rebound:
        assert udp_port(rebound) == port
    handle = udp_bind("127.0.0.1", port)
    try:
        with handle as unwound:
            assert False, "unwind this scope"
    except Exception:
        errors = errors + 1
    try:
        udp_recvfrom(handle, 1, 1000)
    except Exception:
        errors = errors + 1
    try:
        udp_sendto(handle, b"", "127.0.0.1", port, 1000)
    except Exception:
        errors = errors + 1
    with udp_bind("127.0.0.1", port) as released:
        assert udp_port(released) == port
    assert errors == 5
    print("UDP scopes passed")
    return
if __name__ == "__main__":
    run()
"""
    assert parity(tmp_path, source) == "UDP scopes passed\n"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
