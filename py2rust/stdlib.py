"""Python reference for the explicit, experimental service-library contract.

This is a tested subset, not an emulation of every Python stdlib feature.
"""

import base64
import binascii
import contextlib
import datetime as dt
import hashlib
import http.client
import ipaddress
import json
import logging
import math
import os
import re
import socket
import ssl
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BufferedReader
from pathlib import Path
from typing import Any, BinaryIO
from urllib.parse import quote, urlsplit

from ._gzip import (
    GzipReader as GzipReader,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    GzipWriter as GzipWriter,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_create as gzip_create,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_finish as gzip_finish,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_open as gzip_open,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_read as gzip_read,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_reader_close as gzip_reader_close,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_write as gzip_write,  # noqa: PLC0414 - public facade re-export
)
from ._gzip import (
    gzip_writer_close as gzip_writer_close,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    ProcessPool as ProcessPool,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_pipeline as process_pipeline,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_poll as process_poll,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_pool as process_pool,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_pool_close as process_pool_close,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_pool_signal as process_pool_signal,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_run as process_run,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_signal as process_signal,  # noqa: PLC0414 - public facade re-export
)
from ._processes import (
    process_spawn as process_spawn,  # noqa: PLC0414 - public facade re-export
)
from ._python_ast import (
    python_statement_tree as python_statement_tree,  # noqa: PLC0414 - public facade
)
from ._python_syntax import (
    python_syntax_tree as python_syntax_tree,  # noqa: PLC0414 - public facade
)
from ._rational import (
    Rational as Rational,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_add as rational_add,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_compare as rational_compare,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_decimal as rational_decimal,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_denominator as rational_denominator,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_div as rational_div,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_fixed as rational_fixed,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_mul as rational_mul,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_new as rational_new,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_numerator as rational_numerator,  # noqa: PLC0414 - public facade re-export
)
from ._rational import (
    rational_sub as rational_sub,  # noqa: PLC0414 - public facade re-export
)
from ._terminal import (
    terminal_cells as terminal_cells,  # noqa: PLC0414 - public facade
)
from ._terminal import (
    terminal_info as terminal_info,  # noqa: PLC0414 - public facade
)
from ._terminal import (
    terminal_write as terminal_write,  # noqa: PLC0414 - public facade
)
from ._timezones import (
    timezone_local as timezone_local,  # noqa: PLC0414 - public facade
)
from ._timezones import (
    timezone_project as timezone_project,  # noqa: PLC0414 - public facade
)

Json = Any
DateTime = dt.datetime


def unicode_normalize(form: str, text: str) -> str:
    """Canonical or compatibility normalization using the installed Unicode tables."""
    return unicodedata.normalize(form, text)


def base64_encode(data: bytes) -> str:
    if len(data) > 1048576:
        raise ValueError("codec input exceeds 1 MiB")
    return base64.b64encode(data).decode("ascii")


def base64_decode(text: str) -> bytes:
    if len(text.encode()) > 1398104:
        raise ValueError("encoded input exceeds the 1 MiB decoded limit")
    try:
        decoded = base64.b64decode(text, validate=True)
        if base64.b64encode(decoded).decode("ascii") != text:
            raise ValueError("expected canonical padded base64")
    except (binascii.Error, ValueError) as error:
        raise ValueError("expected canonical padded base64") from error
    if len(decoded) > 1048576:
        raise ValueError("codec input exceeds 1 MiB")
    return decoded


def deflate_decompress(data: bytes, maximum: int) -> bytes:
    """Decode exactly one raw DEFLATE stream, bounded before producing expanded data."""
    import zlib

    if type(data) is not bytes or len(data) > 33554432:
        raise ValueError("deflate input requires at most 32 MiB of bytes")
    if type(maximum) is not int or not 0 <= maximum <= 67108864:
        raise ValueError("deflate output limit must be 0..64 MiB")
    decoder = zlib.decompressobj(-15)
    output = decoder.decompress(data, maximum + 1)
    if len(output) > maximum:
        raise ValueError("deflate output exceeds limit")
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("expected exactly one complete deflate stream")
    return output


def sha1_digest(data: bytes) -> bytes:
    if len(data) > 1048576:
        raise ValueError("codec input exceeds 1 MiB")
    return hashlib.sha1(data, usedforsecurity=False).digest()


def bytes_xor(data: bytes, key: bytes) -> bytes:
    if len(data) > 1048576 or not 1 <= len(key) <= 4096:
        raise ValueError("XOR requires at most 1 MiB and a 1..4096-byte key")
    return bytes(value ^ key[index % len(key)] for index, value in enumerate(data))


def crc32(data: bytes | bytearray, value: int = 0) -> int:
    """Unsigned IEEE CRC-32, with an optional previous checksum for incremental input."""
    if type(data) not in {bytes, bytearray} or type(value) is not int or not -(2**63) <= value < 2**63:
        raise ValueError("CRC-32 requires bytes or bytearray and a signed 64-bit seed")
    return binascii.crc32(data, value)


def int_lshift(value: int, count: int) -> int:
    if type(value) is not int or type(count) is not int or not -(2**63) <= value < 2**63 or count >= 2**63:
        raise ValueError("shift operands must be signed 64-bit integers")
    if count < 0:
        raise ValueError("negative shift count")
    if value == 0:
        return 0
    if count >= 64:
        raise ValueError("integer overflow")
    result = value << count
    if not -(2**63) <= result < 2**63:
        raise ValueError("integer overflow")
    return result


def int_rshift(value: int, count: int) -> int:
    if type(value) is not int or type(count) is not int or not -(2**63) <= value < 2**63 or count >= 2**63:
        raise ValueError("shift operands must be signed 64-bit integers")
    if count < 0:
        raise ValueError("negative shift count")
    return value >> count


@dataclass
class UdpSocket:
    _socket: socket.socket | None

    def __enter__(self) -> "UdpSocket":  # noqa: PYI034 - concrete compiled handle type
        _udp_socket(self)
        return self

    def __exit__(self, *args: object) -> None:
        udp_close(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def _udp_socket(handle: UdpSocket) -> socket.socket:
    if handle._socket is None:
        raise ValueError("UDP socket is closed")
    return handle._socket


def _udp_timeout(timeout_ms: int) -> float:
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 86400000:
        raise ValueError("UDP timeout must be 1..86400000 milliseconds")
    return timeout_ms / 1000


def udp_bind(host: str, port: int) -> UdpSocket:
    family, endpoint = _tcp_address(host, port)
    raw = socket.socket(family, socket.SOCK_DGRAM)
    try:
        raw.bind(endpoint)
        return UdpSocket(raw)
    except BaseException:
        raw.close()
        raise


def udp_port(handle: UdpSocket) -> int:
    return _udp_socket(handle).getsockname()[1]


def udp_sendto(handle: UdpSocket, data: bytes, host: str, port: int, timeout_ms: int) -> None:
    if len(data) > 65507 or port == 0:
        raise ValueError("UDP send requires at most 65507 bytes and a nonzero destination port")
    family, endpoint = _tcp_address(host, port)
    raw = _udp_socket(handle)
    if raw.family != family:
        raise ValueError("UDP address family mismatch")
    raw.settimeout(_udp_timeout(timeout_ms))
    if raw.sendto(data, endpoint) != len(data):
        raise ValueError("UDP send did not accept the complete datagram")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def udp_recvfrom(handle: UdpSocket, limit: int, timeout_ms: int) -> tuple[bytes, str, int, bool]:
    if type(limit) is not int or not 1 <= limit <= 65507:
        raise ValueError("UDP receive limit must be 1..65507 bytes")
    raw = _udp_socket(handle)
    raw.settimeout(_udp_timeout(timeout_ms))
    data, source = raw.recvfrom(limit + 1)
    if len(source) == 4 and source[3] != 0:
        raise ValueError("scoped IPv6 datagrams are unsupported")
    return data[:limit], source[0], source[1], len(data) > limit


def udp_close(handle: UdpSocket) -> None:
    if handle._socket is not None:
        handle._socket.close()
        handle._socket = None
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def int_from_decimal(text: str) -> int:
    """Parse bounded ASCII decimal text into a signed 64-bit integer."""
    if len(text) > 4096 or not text.isascii():
        raise ValueError("decimal input must contain at most 4096 ASCII bytes")
    value = text.strip(" \t\n\r\v\f")
    if re.fullmatch(r"[+-]?[0-9]+", value) is None:
        raise ValueError("expected signed decimal digits")
    number = int(value)
    if not -(2**63) <= number < 2**63:
        raise ValueError("decimal value outside signed 64-bit range")
    return number


@dataclass
class TcpListener:
    _socket: socket.socket | None

    def __enter__(self) -> "TcpListener":  # noqa: PYI034 - concrete handle type is the compiled library contract
        _tcp_socket(self)
        return self

    def __exit__(self, *args: object) -> None:
        tcp_close_listener(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


@dataclass
class TcpStream:
    _socket: socket.socket | None
    _deadline: float

    def __enter__(self) -> "TcpStream":  # noqa: PYI034 - concrete handle type is the compiled library contract
        _tcp_socket(self)
        return self

    def __exit__(self, *args: object) -> None:
        tcp_close(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def _tcp_socket(handle: TcpListener | TcpStream) -> socket.socket:
    if handle._socket is None:
        raise ValueError("TCP handle is closed")
    return handle._socket


def _tcp_timeout(timeout_ms: int) -> float:
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 86400000:
        raise ValueError("TCP timeout must be 1..86400000 milliseconds")
    return timeout_ms / 1000


def _tcp_address(host: str, port: int) -> tuple:
    if type(port) is not int or not 0 <= port <= 65535 or "%" in host:
        raise ValueError("invalid TCP address")
    address = ipaddress.ip_address(host)
    return (socket.AF_INET if address.version == 4 else socket.AF_INET6), (host, port)


def _tcp_remaining(handle: TcpStream) -> float:
    remaining = handle._deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("TCP deadline exceeded")
    return remaining


def tcp_listen(host: str, port: int) -> TcpListener:
    family, address = _tcp_address(host, port)
    listener = socket.socket(family, socket.SOCK_STREAM)
    try:
        listener.bind(address)
        listener.listen(128)
        return TcpListener(listener)
    except BaseException:
        listener.close()
        raise


def tcp_port(handle: TcpListener) -> int:
    return _tcp_socket(handle).getsockname()[1]


def tcp_connect(host: str, port: int, timeout_ms: int) -> TcpStream:
    timeout = _tcp_timeout(timeout_ms)
    family, address = _tcp_address(host, port)
    stream = socket.socket(family, socket.SOCK_STREAM)
    try:
        stream.settimeout(timeout)
        stream.connect(address)
        return TcpStream(stream, time.monotonic() + timeout)
    except BaseException:
        stream.close()
        raise


def tcp_accept_timeout(handle: TcpListener, accept_ms: int, io_ms: int) -> TcpStream:
    accept_timeout = _tcp_timeout(accept_ms)
    io_timeout = _tcp_timeout(io_ms)
    listener = _tcp_socket(handle)
    listener.settimeout(accept_timeout)
    stream, _ = listener.accept()
    return TcpStream(stream, time.monotonic() + io_timeout)


def tcp_set_deadline(handle: TcpStream, timeout_ms: int) -> None:
    timeout = _tcp_timeout(timeout_ms)
    _tcp_socket(handle)
    handle._deadline = time.monotonic() + timeout
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_recv(handle: TcpStream, count: int) -> bytes:
    if type(count) is not int or not 1 <= count <= 1048576:
        raise ValueError("TCP read size must be 1..1048576 bytes")
    stream = _tcp_socket(handle)
    stream.settimeout(_tcp_remaining(handle))
    data = stream.recv(count)
    _tcp_remaining(handle)
    return data


def tcp_sendall(handle: TcpStream, data: bytes) -> None:
    if len(data) > 1048576:
        raise ValueError("TCP write exceeds 1048576 bytes")
    stream = _tcp_socket(handle)
    stream.settimeout(_tcp_remaining(handle))
    stream.sendall(data)
    _tcp_remaining(handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_shutdown_write(handle: TcpStream) -> None:
    _tcp_socket(handle).shutdown(socket.SHUT_WR)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_close(handle: TcpStream) -> None:
    if handle._socket is not None:
        handle._socket.close()
        handle._socket = None
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_close_listener(handle: TcpListener) -> None:
    if handle._socket is not None:
        handle._socket.close()
        handle._socket = None
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_accept_ready(handle: TcpListener, limit: int, io_ms: int) -> list[TcpStream]:
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("ready accept limit must be 1..64")
    timeout = _tcp_timeout(io_ms)
    listener = _tcp_socket(handle)
    listener.setblocking(False)
    accepted = []
    try:
        while len(accepted) < limit:
            try:
                stream, _ = listener.accept()
            except BlockingIOError:
                break
            accepted.append(TcpStream(stream, time.monotonic() + timeout))
        return accepted
    except BaseException:
        for stream in accepted:
            tcp_close(stream)
        raise


def tcp_recv_ready(handle: TcpStream, count: int) -> tuple[bytes, bool]:
    if type(count) is not int or not 1 <= count <= 1048576:
        raise ValueError("TCP read size must be 1..1048576 bytes")
    stream = _tcp_socket(handle)
    stream.setblocking(False)
    try:
        data = stream.recv(count)
        return data, not data
    except BlockingIOError:
        return b"", False


def tcp_send_ready(handle: TcpStream, data: bytes) -> int:
    if len(data) > 1048576:
        raise ValueError("TCP write exceeds 1048576 bytes")
    stream = _tcp_socket(handle)
    stream.setblocking(False)
    try:
        size = stream.send(data)
        if size == 0 and data:
            raise OSError("TCP write returned zero bytes")
        return size
    except BlockingIOError:
        return 0


def tcp_send_buffer(handle: TcpStream, size: int) -> None:
    if type(size) is not int or not 1024 <= size <= 1048576:
        raise ValueError("TCP send buffer must be 1024..1048576 bytes")
    _tcp_socket(handle).setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, size)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def tcp_select(listener: TcpListener, readers: list[TcpStream], writers: list[TcpStream], timeout_ms: int) -> Json:
    import selectors

    if type(timeout_ms) is not int or not 0 <= timeout_ms <= 60000 or len(readers) > 1024 or len(writers) > 1024:
        raise ValueError("TCP select requires 0..60000 ms and at most 1024 entries per list")
    entries = {}
    for key, handles in [("read", readers), ("write", writers)]:
        for index, handle in enumerate(handles):
            stream = _tcp_socket(handle)
            entry = entries.setdefault(stream.fileno(), {"socket": stream, "read": [], "write": []})
            entry[key].append(index)
    accept = False
    read = []
    write = []
    with selectors.DefaultSelector() as selector:
        selector.register(_tcp_socket(listener), selectors.EVENT_READ, None)
        for entry in entries.values():
            mask = (selectors.EVENT_READ if entry["read"] else 0) | (selectors.EVENT_WRITE if entry["write"] else 0)
            selector.register(entry["socket"], mask, entry)
        for key, mask in selector.select(timeout_ms / 1000):
            if key.data is None:
                accept = True
            else:
                if mask & selectors.EVENT_READ:
                    read.extend(key.data["read"])
                if mask & selectors.EVENT_WRITE:
                    write.extend(key.data["write"])
    return {"accept": accept, "read": sorted(read), "write": sorted(write)}


@dataclass
class UnixListener(TcpListener):
    """A filesystem listener; aliases share both the descriptor and owned socket path."""

    _path: Path
    _identity: tuple[int, int]

    def __enter__(self) -> "UnixListener":  # noqa: PYI034 - concrete library handle
        _tcp_socket(self)
        return self

    def __exit__(self, *args: object) -> None:
        unix_close_listener(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def __del__(self) -> None:
        with contextlib.suppress(OSError):
            unix_close_listener(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


@dataclass
class UnixStream(TcpStream):
    def __enter__(self) -> "UnixStream":  # noqa: PYI034 - concrete library handle
        _tcp_socket(self)
        return self


def _unix_path(path: str) -> Path:
    if not path or "\x00" in path or path.endswith("/") or not Path(path).name:
        raise ValueError("Unix socket requires a nonempty filesystem path")
    absolute = Path(path).parent.resolve(strict=True) / Path(path).name
    if len(str(absolute).encode()) > 107:
        raise ValueError("Unix socket path exceeds 107 UTF-8 bytes")
    return absolute


def _unix_identity(path: Path) -> tuple[int, int]:
    import stat

    metadata = path.lstat()
    if not stat.S_ISSOCK(metadata.st_mode):
        raise FileExistsError("Unix socket path is not a socket")
    return metadata.st_dev, metadata.st_ino


def _unix_remove(path: Path, identity: tuple[int, int]) -> None:
    try:
        if _unix_identity(path) == identity:
            path.unlink()
    except (FileNotFoundError, FileExistsError):
        pass
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_listen(path: str, recover_stale: bool) -> UnixListener:
    absolute = _unix_path(path)
    if absolute.exists() or absolute.is_symlink():
        identity = _unix_identity(absolute)
        if not recover_stale:
            raise FileExistsError("Unix socket path already exists")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.1)
            try:
                probe.connect(str(absolute))
            except ConnectionRefusedError:
                pass
            else:
                raise FileExistsError("Unix socket has an active listener")
        if _unix_identity(absolute) != identity:
            raise OSError("Unix socket path changed during recovery")
        absolute.unlink()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    owned = None
    try:
        listener.bind(str(absolute))
        owned = UnixListener(listener, absolute, _unix_identity(absolute))
        listener.listen(128)
        return owned
    except BaseException:
        listener.close()
        if owned is not None:
            unix_close_listener(owned)
        raise


def unix_connect(path: str, timeout_ms: int) -> UnixStream:
    timeout = _tcp_timeout(timeout_ms)
    absolute = _unix_path(path)
    stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        stream.settimeout(timeout)
        stream.connect(str(absolute))
        return UnixStream(stream, time.monotonic() + timeout)
    except BaseException:
        stream.close()
        raise


def unix_close_listener(handle: UnixListener) -> None:
    if handle._socket is not None:
        tcp_close_listener(handle)
        _unix_remove(handle._path, handle._identity)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_accept_timeout(handle: UnixListener, accept_ms: int, io_ms: int) -> UnixStream:
    accepted = tcp_accept_timeout(handle, accept_ms, io_ms)
    return UnixStream(accepted._socket, accepted._deadline)


def unix_accept_ready(handle: UnixListener, limit: int, io_ms: int) -> list[UnixStream]:
    return [UnixStream(item._socket, item._deadline) for item in tcp_accept_ready(handle, limit, io_ms)]


def unix_set_deadline(handle: UnixStream, timeout_ms: int) -> None:
    tcp_set_deadline(handle, timeout_ms)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_recv(handle: UnixStream, count: int) -> bytes:
    return tcp_recv(handle, count)


def unix_sendall(handle: UnixStream, data: bytes) -> None:
    tcp_sendall(handle, data)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_shutdown_write(handle: UnixStream) -> None:
    tcp_shutdown_write(handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_close(handle: UnixStream) -> None:
    tcp_close(handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_recv_ready(handle: UnixStream, count: int) -> tuple[bytes, bool]:
    return tcp_recv_ready(handle, count)


def unix_send_ready(handle: UnixStream, data: bytes) -> int:
    return tcp_send_ready(handle, data)


def unix_send_buffer(handle: UnixStream, size: int) -> None:
    tcp_send_buffer(handle, size)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def unix_select(listener: UnixListener, readers: list[UnixStream], writers: list[UnixStream], timeout_ms: int) -> Json:
    return tcp_select(listener, readers, writers, timeout_ms)


def int_from_bytes(data: bytes, byteorder: str) -> int:
    if len(data) > 8 or byteorder not in {"big", "little"}:
        raise ValueError("integer byte conversion requires 0..8 bytes and big/little byte order")
    value = int.from_bytes(data, byteorder)
    if value >= 2**63:
        raise ValueError("decoded integer exceeds signed 64-bit range")
    return value


def int_to_bytes(value: int, length: int, byteorder: str) -> bytes:
    if type(value) is not int or not 0 <= value < 2**63 or type(length) is not int or not 0 <= length <= 8:
        raise ValueError("integer byte conversion requires nonnegative value and 0..8 bytes")
    if byteorder not in {"big", "little"}:
        raise ValueError("integer byte order must be big or little")
    return value.to_bytes(length, byteorder)


def parallel_map(callback: Callable[[Json], Json], items: list[Json], workers: int) -> list[Json]:
    """Run bounded independent callbacks; retain input order and join every worker, including on error."""
    import copy
    from concurrent.futures import ThreadPoolExecutor

    if type(workers) is not int or not 1 <= workers <= 64 or type(items) is not list or len(items) > 10000:
        raise ValueError("parallel_map requires 1..64 workers and at most 10000 JSON items")
    for item in items:
        _json_check(item)
    if not items:
        return []

    def invoke(item: Json) -> Json:
        result = callback(item)
        _json_check(result)
        return result

    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as pool:
        futures = [pool.submit(invoke, copy.deepcopy(item)) for item in items]
        return [future.result() for future in futures]


def ceil(value: float) -> int:
    """Round upward to a signed 64-bit integer, preserving integer arguments."""
    result = math.ceil(value)
    if not -(2**63) <= result < 2**63:
        raise ValueError("ceiling result is outside signed 64-bit range")
    return result


def floor(value: float) -> int:
    """Round downward to a signed 64-bit integer, preserving integer arguments."""
    result = math.floor(value)
    if not -(2**63) <= result < 2**63:
        raise ValueError("floor result is outside signed 64-bit range")
    return result


def math_log(value: float) -> float:
    """Natural logarithm of a positive finite number."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError("logarithm requires a positive finite number")
    return math.log(value)


def math_sqrt(value: float) -> float:
    """Square root of a nonnegative finite number; preserve signed zero."""
    if not math.isfinite(value) or value < 0.0:
        raise ValueError("square root requires a nonnegative finite number")
    return math.sqrt(value)


def limit_address_space(maximum: int) -> int:
    """Lower this Unix process's address-space soft limit; preserve its hard limit."""
    import resource

    if type(maximum) is not int or not 33554432 <= maximum <= 17179869184:
        raise ValueError("address-space limit must be 32 MiB..16 GiB")
    current, hard = resource.getrlimit(resource.RLIMIT_AS)
    chosen = maximum if current == resource.RLIM_INFINITY else min(current, maximum)
    resource.setrlimit(resource.RLIMIT_AS, (chosen, hard))
    return chosen


def process_exit(code: int) -> None:
    """Terminate with a POSIX-style eight-bit process status."""
    import sys

    sys.exit(code % 256)


class HttpServer(HTTPServer):
    tls_context: ssl.SSLContext | None = None


def html_links(document: str, max_links: int) -> Json:
    """Extract static links in DOM order; template contents and foreign tags are inert."""
    import html5lib

    if len(document.encode()) > 1048576 or not 1 <= max_links <= 10000:
        raise ValueError("invalid HTML document or link limit")
    tree = html5lib.parse(document, scripting=True)
    pending = [tree]
    base = None
    links = []
    namespace = "{http://www.w3.org/1999/xhtml}"
    while pending:
        element = pending.pop()
        name = element.tag
        if name == namespace + "template":
            continue
        pending.extend(reversed(list(element)))
        if not isinstance(name, str) or not name.startswith(namespace):
            continue
        tag = name[len(namespace) :]
        if tag == "base" and base is None and "href" in element.attrib:
            base = element.attrib["href"]
        attributes = []
        if tag in {"a", "area", "link"}:
            attributes = ["href"]
        elif tag in {"img", "script", "iframe", "audio", "source", "input"}:
            attributes = ["src"]
        elif tag == "video":
            attributes = ["src", "poster"]
        elif tag == "object":
            attributes = ["data"]
        for attribute in attributes:
            if attribute in element.attrib:
                if len(links) >= max_links:
                    raise ValueError("HTML link limit exceeded")
                links.append({"tag": tag, "attribute": attribute, "value": element.attrib[attribute]})
    return {"base": base, "links": links}


def _url_reference(value: str, absolute: bool) -> None:
    if (
        len(value.encode()) > 8192
        or value.startswith(" ")
        or value.endswith(" ")
        or any(ord(c) < 32 or c in "\x7f\\" for c in value)
    ):
        raise ValueError("invalid URL characters or length")
    if re.search(r"%(?![0-9A-Fa-f]{2})", value):
        raise ValueError("invalid URL percent escape")
    scheme = re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", value)
    authority = None
    if value.startswith("//") and not absolute:
        authority = value[2:]
    elif scheme:
        if scheme.group().lower() not in {"http:", "https:"} or not value[scheme.end() :].startswith("//"):
            raise ValueError("expected an absolute HTTP(S) URL")
        authority = value[scheme.end() + 2 :]
    elif absolute:
        raise ValueError("expected an absolute HTTP(S) URL")
    if authority is not None:
        pieces = re.split(r"[/?#]", authority, maxsplit=1)[0].split(":")
        if len(pieces) > 2 or not pieces[0]:
            raise ValueError("expected a DNS name or canonical IPv4 address")
        host = pieces[0].removesuffix(".")
        if len(host) > 253 or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in host.split(".")
        ):
            raise ValueError("invalid URL hostname")
        last = host.rsplit(".", 1)[-1].lower()
        if last.isdigit() or re.fullmatch(r"0x[0-9a-f]*", last):
            ipaddress.IPv4Address(host)
        if len(pieces) == 2 and (not re.fullmatch(r"[0-9]{1,5}", pieces[1]) or not 1 <= int(pieces[1]) <= 65535):
            raise ValueError("invalid URL port")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def _url_path(path: str) -> str:
    output = []
    pieces = (path or "/").split("/")
    for index, segment in enumerate(pieces[1:]):
        dots = re.sub(r"%2e", ".", segment, flags=re.IGNORECASE)
        if dots in {".", ".."}:
            if dots == ".." and output:
                output.pop()
            if index == len(pieces) - 2:
                output.append("")
        else:
            output.append(segment)
    return "/" + "/".join(output)


def url_resolve(base: str, reference: str) -> str:
    """Resolve the shared HTTP(S) subset with WHATWG path and query spelling."""
    _url_reference(base, True)
    _url_reference(reference, False)
    source = urlsplit(base)
    link = urlsplit(reference)
    scheme = link.scheme or source.scheme
    authority = link.netloc or source.netloc
    host, separator, port = authority.lower().partition(":")
    host_part = host.removesuffix(".")
    if host_part.rsplit(".", 1)[-1].isdigit():
        host = host_part
    if separator and not ((scheme == "http" and int(port) == 80) or (scheme == "https" and int(port) == 443)):
        host += ":" + str(int(port))
    if link.scheme or link.netloc:
        path = link.path or "/"
    elif link.path.startswith("/"):
        path = link.path
    elif link.path:
        path = _url_path(source.path).rsplit("/", 1)[0] + "/" + link.path
    else:
        path = source.path or "/"
    has_query = "?" in reference.split("#", 1)[0]
    query = link.query
    if not (link.scheme or link.netloc or link.path or has_query):
        has_query = "?" in base.split("#", 1)[0]
        query = source.query
    path = quote(_url_path(path), safe="/:@-._~!$&'()*+,;=%[]|^")
    query = quote(query, safe="/?:@-._~!$&()*+,;=%[]|^`{}")
    result = scheme + "://" + host + path + ("?" + query if has_query else "")
    result = re.sub(r"%[0-9a-fA-F]{2}", lambda match: match.group().upper(), result)
    if len(result.encode()) > 8192:
        raise ValueError("resolved URL exceeds 8192 bytes")
    return result


def url_origin(value: str) -> str:
    parsed = urlsplit(url_resolve(value, ""))
    return parsed.scheme + "://" + parsed.netloc


def _json_check(value: Json, depth: int = 0) -> None:
    if depth > 64:
        raise ValueError("JSON nesting exceeds 64")
    if type(value) is int and not -(2**63) <= value < 2**63:
        raise ValueError("JSON integers must fit signed 64 bits")
    if type(value) is float and not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, (list, tuple)):
        for item in value:
            _json_check(item, depth + 1)
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            key.encode("utf-8")
            _json_check(item, depth + 1)


def json_loads(text: str) -> Json:
    value = json.loads(text)
    _json_check(value)
    return value


def json_loads_unique(text: str) -> Json:
    """Parse subset JSON, rejecting repeated decoded object keys at every depth."""

    def object_pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
        result: dict[str, Json] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    value = json.loads(text, object_pairs_hook=object_pairs)
    _json_check(value)
    return value


def json_equal(left: Json, right: Json) -> bool:
    """Structural JSON equality: numeric spelling is ignored, booleans stay distinct."""
    if json_kind(left) != json_kind(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(json_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(json_equal(value, right[key]) for key, value in left.items())
    return left == right


def json_scalar_compare(left: Json, right: Json) -> int:
    """Compare compatible JSON scalars, preserving exact mixed integer/float order."""
    kind = json_kind(left)
    if kind != json_kind(right) or kind not in {"null", "bool", "number", "string"}:
        raise TypeError("expected compatible JSON scalars")
    _json_check(left)
    _json_check(right)
    if kind == "null":
        return 0
    return int(left > right) - int(left < right)


def json_number_add(left: Json, right: Json) -> Json:
    """Add JSON numbers with checked integer and finite binary64 results."""
    if type(left) not in {int, float} or type(right) not in {int, float}:
        raise TypeError("expected JSON numbers")
    _json_check(left)
    _json_check(right)
    result = left + right
    if type(result) is int and not -(2**63) <= result < 2**63:
        raise ValueError("integer overflow")
    if type(result) is float and not math.isfinite(result):
        raise ValueError("non-finite floating point result")
    return result


def json_keys(value: Json) -> list[str]:
    """Sorted object keys for deterministic traversal across both runtimes."""
    if not isinstance(value, dict):
        raise TypeError("expected JSON object")
    return sorted(value)


def json_dumps(value: Json) -> str:
    _json_check(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def json_canonical(value: Json) -> str:
    """Deterministic subset JSON: sorted keys and normalized 17-digit binary64 numbers."""
    _json_check(value)

    def render(item: Json) -> str:
        if type(item) is float:
            mantissa, exponent = format(item, ".16e").split("e")
            return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
        if isinstance(item, (list, tuple)):
            return "[" + ",".join(render(child) for child in item) + "]"
        if isinstance(item, dict):
            return "{" + ",".join(json_dumps(key) + ":" + render(item[key]) for key in sorted(item)) + "}"
        return json_dumps(item)

    return render(value)


def pretty(value: Json) -> str:
    _json_check(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)


def json_string(value: Json) -> str:
    if type(value) is not str:
        raise ValueError("expected JSON string")
    return value


def json_int(value: Json) -> int:
    if type(value) is not int:
        raise ValueError("expected JSON integer")
    _json_check(value)
    return value


def json_bool(value: Json) -> bool:
    if type(value) is not bool:
        raise ValueError("expected JSON boolean")
    return value


def json_float(value: Json) -> float:
    if type(value) not in (int, float):
        raise ValueError("expected JSON number")
    _json_check(value)
    return float(value)


def json_is_null(value: Json) -> bool:
    return value is None


def json_array(value: Json) -> list[Json]:
    if type(value) is not list:
        raise ValueError("expected JSON array")
    return value.copy()


def json_get(value: Json, key: str, default: Json) -> Json:
    if type(value) is not dict:
        raise ValueError("expected JSON object")
    return value.get(key, default)


def unix_time() -> float:
    return time.time()


def monotonic() -> float:
    return time.monotonic()


def sleep(seconds: float) -> None:
    if not math.isfinite(seconds) or not 0 <= seconds <= 86400:
        raise ValueError("sleep must be between 0 and 86400 seconds")
    time.sleep(seconds)


def utc_now() -> DateTime:
    return dt.datetime.now(dt.timezone.utc)


def datetime_parse(text: str) -> DateTime:
    if not text.isascii() or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", text):
        raise ValueError("expected RFC3339 timestamp with explicit offset and at most 6 fractional digits")
    if not text.endswith("Z") and (int(text[-5:-3]) > 23 or int(text[-2:]) > 59):
        raise ValueError("invalid timezone offset")
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def datetime_iso(value: DateTime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")


def datetime_add_seconds(value: DateTime, seconds: int) -> DateTime:
    return value + dt.timedelta(seconds=seconds)


def datetime_from_unix(seconds: int) -> DateTime:
    """An integral Unix timestamp in UTC, bounded to Gregorian years 0001..9999."""
    if type(seconds) is not int or not -62135596800 <= seconds <= 253402300799:
        raise ValueError("Unix timestamp must be an integer within years 0001..9999")
    return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=seconds)


def datetime_unix_microseconds(value: DateTime) -> int:
    """Exact UTC microseconds since the Unix epoch, without a float timestamp round trip."""
    delta = value.astimezone(dt.timezone.utc) - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def datetime_format(value: DateTime, pattern: str) -> str:
    """Portable, locale-independent UTC formatting with explicitly supported directives."""
    if value.tzinfo is None or len(pattern.encode()) > 1024:
        raise ValueError("expected an aware datetime and a format of at most 1024 bytes")
    utc = value.astimezone(dt.timezone.utc)
    weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    fields = {
        "%": "%",
        "Y": f"{utc.year:04d}",
        "m": f"{utc.month:02d}",
        "d": f"{utc.day:02d}",
        "H": f"{utc.hour:02d}",
        "M": f"{utc.minute:02d}",
        "S": f"{utc.second:02d}",
        "f": f"{utc.microsecond:06d}",
        "z": "+0000",
        "Z": "UTC",
        "j": f"{utc.timetuple().tm_yday:03d}",
        "a": weekdays[utc.weekday()][:3],
        "A": weekdays[utc.weekday()],
        "b": months[utc.month - 1][:3],
        "B": months[utc.month - 1],
        "w": str((utc.weekday() + 1) % 7),
        "u": str(utc.isoweekday()),
    }
    result: list[str] = []
    escaped = False
    for char in pattern:
        if escaped:
            if char not in fields:
                raise ValueError("unsupported datetime format directive")
            result.append(fields[char])
            escaped = False
        elif char == "%":
            escaped = True
        else:
            result.append(char)
    if escaped:
        raise ValueError("incomplete datetime format directive")
    return "".join(result)


def http_retry_after(value: str, now: float) -> float:
    """Resolve Retry-After to a Unix deadline, using now for obsolete two-digit years."""
    if not math.isfinite(now) or not 0 <= now <= 253402300799 or len(value.encode()) > 64:
        raise ValueError("invalid Retry-After input or reference time")
    text = value.strip(" \t")
    if re.fullmatch(r"[0-9]+", text):
        deadline = now + int(text)
        if deadline > 253402300799:
            raise ValueError("Retry-After exceeds year 9999")
        return deadline
    patterns = [
        r"([A-Z][a-z]{2}), ([0-9]{2}) ([A-Z][a-z]{2}) ([0-9]{4}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) GMT",
        r"([A-Z][a-z]+), ([0-9]{2})-([A-Z][a-z]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2}):([0-9]{2}) GMT",
        r"([A-Z][a-z]{2}) ([A-Z][a-z]{2}) ([ 0-9][0-9]) ([0-9]{2}):([0-9]{2}):([0-9]{2}) ([0-9]{4})",
    ]
    for index, pattern in enumerate(patterns):
        match = re.fullmatch(pattern, text)
        if match is None:
            continue
        if index == 2:
            weekday, month, day, hour, minute, second, year = match.groups()
        else:
            weekday, day, month, year, hour, minute, second = match.groups()
        numbers = (int(year), int(day), int(hour), int(minute), int(second))
        year_number, day_number, hour_number, minute_number, second_number = numbers
        month_number = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"].index(
            month
        ) + 1
        if index == 1:
            reference = dt.datetime.fromtimestamp(math.floor(now), dt.timezone.utc)
            year_number += (reference.year + 50) // 100 * 100
            candidate = (year_number, month_number, day_number, hour_number, minute_number, second_number)
            boundary = (reference.year + 50, *reference.timetuple()[1:6])
            if candidate > boundary:
                year_number -= 100
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        if index == 1:
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if second_number > 60:
            raise ValueError("invalid HTTP date seconds")
        parsed = dt.datetime(
            year_number,
            month_number,
            day_number,
            hour_number,
            minute_number,
            min(second_number, 59),
            tzinfo=dt.timezone.utc,
        )
        if weekdays[parsed.weekday()] != weekday:
            raise ValueError("HTTP date weekday does not match date")
        parsed += dt.timedelta(seconds=second_number == 60)
        return max(now, parsed.timestamp())
    raise ValueError("expected delay-seconds or HTTP-date")


def log_configure(level: int) -> None:
    if level not in (10, 20, 30, 40, 50):
        raise ValueError("logging level must be 10, 20, 30, 40 or 50")
    logging.basicConfig(level=level, format="%(levelname)s:%(message)s", force=True)


def log(level: int, message: str) -> None:
    if level not in (10, 20, 30, 40, 50):
        raise ValueError("invalid logging level")
    # The service profile intentionally exposes the root logger.
    logging.log(level, message)  # noqa: LOG015


def read_text(path: str) -> str:
    # Preserve line endings, unlike Path.read_text's universal newline mode.
    return Path(path).read_bytes().decode("utf-8")


def write_text(path: str, text: str) -> None:
    Path(path).write_bytes(text.encode("utf-8"))


def read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def write_bytes(path: str, data: bytes) -> None:
    Path(path).write_bytes(data)


@dataclass
class LineReader:
    reader: BufferedReader

    def __enter__(self) -> "LineReader":  # noqa: PYI034 - Python 3.10 runtime baseline
        if self.reader.closed:
            raise ValueError("line reader is closed")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.reader.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def line_open(path: str, offset: int) -> LineReader:
    if not 0 <= offset < 2**63:
        raise ValueError("line offset must fit a nonnegative signed 64-bit integer")
    if Path(path).exists() and not Path(path).is_file():
        raise ValueError("expected a regular file")
    reader = open(path, "rb", buffering=65536)  # noqa: SIM115 - ownership transfers to LineReader
    try:
        if offset > os.fstat(reader.fileno()).st_size:
            raise ValueError("line offset exceeds file size")
        reader.seek(offset)
        return LineReader(reader)
    except Exception:
        reader.close()
        raise


def line_read(handle: LineReader, limit: int) -> tuple[bytes, bool]:
    """Return at most limit raw bytes, with true at LF or physical EOF."""
    if not 1 <= limit <= 1048576:
        raise ValueError("line read limit must be 1..1 MiB")
    if handle.reader.closed:
        raise ValueError("line reader is closed")
    data = handle.reader.readline(limit)
    complete = data.endswith(b"\n") or len(data) < limit or not handle.reader.peek(1)
    return data, complete


def line_position(handle: LineReader) -> int:
    if handle.reader.closed:
        raise ValueError("line reader is closed")
    position = handle.reader.tell()
    if not 0 <= position < 2**63:
        raise ValueError("line position exceeds signed 64-bit range")
    return position


def line_close(handle: LineReader) -> None:
    handle.reader.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


@dataclass
class FileHandle:
    file: BinaryIO

    def __enter__(self) -> "FileHandle":  # noqa: PYI034 - retain the Python 3.10 runtime baseline
        if self.file.closed:
            raise ValueError("file is closed")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.file.close()
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def file_open(path: str, mode: str) -> FileHandle:
    if mode not in {"rb", "r+b", "x+b", "w+b"}:
        raise ValueError("file mode must be rb, r+b, x+b or w+b")
    if Path(path).exists() and not Path(path).is_file():
        raise ValueError("expected a regular file")
    return FileHandle(open(path, mode, buffering=0))


def file_read(handle: FileHandle, count: int) -> bytes:
    if not 1 <= count <= 33554432:
        raise ValueError("file read size must be 1..32 MiB")
    return handle.file.read(count)


def file_write(handle: FileHandle, data: bytes) -> None:
    if len(data) > 33554432:
        raise ValueError("file write exceeds 32 MiB")
    if handle.file.closed:
        raise ValueError("file is closed")
    pending = memoryview(data)
    while pending:
        written = handle.file.write(pending)
        if not written:
            raise OSError("file write made no progress")
        pending = pending[written:]
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def file_seek(handle: FileHandle, offset: int, whence: int) -> int:
    if whence not in {0, 1, 2} or not -(2**63) <= offset < 2**63:
        raise ValueError("invalid seek offset or whence")
    result = handle.file.seek(offset, whence)
    if not 0 <= result < 2**63:
        raise ValueError("file position exceeds signed 64 bits")
    return result


def file_size(handle: FileHandle) -> int:
    size = os.fstat(handle.file.fileno()).st_size
    if not 0 <= size < 2**63:
        raise ValueError("file size exceeds signed 64 bits")
    return size


def file_truncate(handle: FileHandle, length: int) -> None:
    if not 0 <= length < 2**63:
        raise ValueError("invalid file length")
    handle.file.truncate(length)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def file_sync(handle: FileHandle) -> None:
    os.fsync(handle.file.fileno())
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def file_close(handle: FileHandle) -> None:
    handle.file.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def file_lock(path: str) -> FileHandle:
    """Hold a nonblocking advisory lock until this shared handle closes."""
    import fcntl
    import stat

    descriptor = os.open(_filesystem_path(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("lock requires a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stream = os.fdopen(descriptor, "r+b", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise
    return FileHandle(stream)


def rename_no_replace(source: str, destination: str) -> None:
    """Linux atomic no-overwrite move, including directories and symlink entries."""
    import ctypes
    import sys

    if sys.platform != "linux":
        raise OSError("rename_no_replace currently requires Linux")
    source_bytes = os.fsencode(_filesystem_path(source))
    destination_bytes = os.fsencode(_filesystem_path(destination))
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, source_bytes, -100, destination_bytes, 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), source, None, destination)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def link_file(source: str, destination: str) -> None:
    if not Path(source).is_file():
        raise ValueError("expected a regular source file")
    os.link(source, destination)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def replace_file(source: str, destination: str) -> None:
    """Atomically publish a regular file, replacing only a distinct regular file."""
    import stat

    incoming = _filesystem_path(source)
    target = _filesystem_path(destination)
    before = incoming.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("replacement source must be a regular file")
    try:
        previous = target.lstat()
    except FileNotFoundError:
        previous = None
    if previous is not None:
        if not stat.S_ISREG(previous.st_mode):
            raise ValueError("replacement destination must be a regular file or absent")
        if (before.st_dev, before.st_ino) == (previous.st_dev, previous.st_ino):
            raise ValueError("replacement paths alias")
    os.replace(incoming, target)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def sync_directory(path: str) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def path_parent(path: str) -> str:
    return str(Path(path).parent)


def path_name(path: str) -> str:
    name = Path(path).name
    if name in {"", ".", ".."}:
        raise ValueError("path needs a file name")
    return name


def path_is_symlink(path: str) -> bool:
    try:
        return Path(path).lstat().st_mode & 0o170000 == 0o120000
    except FileNotFoundError:
        return False


def path_same(left: str, right: str) -> bool:
    return Path(left).samefile(right)


@dataclass
class Sha256:
    context: Any


def sha256_new() -> Sha256:
    return Sha256(hashlib.sha256())


def sha256_update(state: Sha256, data: bytes) -> Sha256:
    updated = state.context.copy()
    updated.update(data)
    return Sha256(updated)


def sha256_digest(state: Sha256) -> str:
    return state.context.hexdigest()


def mkdir_all(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def mkdir_new(path: str) -> None:
    """Create one private directory, failing if any entry already exists."""
    _filesystem_path(path).mkdir(mode=0o700)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def create_symlink(target: str, path: str) -> None:
    if not target or "\x00" in target:
        raise ValueError("symlink target must be nonempty and NUL-free")
    target.encode("utf-8")
    os.symlink(target, _filesystem_path(path))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def path_set_metadata(path: str, mode: int, mtime_ns: int) -> None:
    """Set ordinary permissions and exact mtime without following the final symlink."""
    import stat

    if type(mode) is not int or not 0 <= mode <= 0o777:
        raise ValueError("mode must contain only ordinary permission bits")
    if type(mtime_ns) is not int or not -(2**63) <= mtime_ns < 2**63:
        raise ValueError("mtime must fit signed 64-bit nanoseconds")
    value = _filesystem_path(path)
    metadata = value.lstat()
    if stat.S_ISLNK(metadata.st_mode):
        if mode != 0o777:
            raise ValueError("symlink mode must be 0777")
        os.utime(value, ns=(metadata.st_atime_ns, mtime_ns), follow_symlinks=False)
        return
    descriptor = os.open(value, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        metadata = os.fstat(descriptor)
        if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
            raise ValueError("metadata update requires a file, directory or symlink")
        os.fchmod(descriptor, mode)
        os.utime(descriptor, ns=(metadata.st_atime_ns, mtime_ns))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return


def _filesystem_path(value: str) -> Path:
    if not value or "\x00" in value:
        raise ValueError("filesystem path must be nonempty and NUL-free")
    value.encode("utf-8")
    return Path(value)


def path_stat(path: str, follow_links: bool) -> Json:
    """Unix metadata in explicit signed integers; follow only when requested."""
    import stat

    if type(follow_links) is not bool:
        raise ValueError("follow_links must be a bool")
    metadata = _filesystem_path(path).stat(follow_symlinks=follow_links)
    kind = "other"
    for name, check in [
        ("file", stat.S_ISREG),
        ("directory", stat.S_ISDIR),
        ("symlink", stat.S_ISLNK),
        ("fifo", stat.S_ISFIFO),
        ("socket", stat.S_ISSOCK),
        ("block", stat.S_ISBLK),
        ("char", stat.S_ISCHR),
    ]:
        if check(metadata.st_mode):
            kind = name
            break
    values = {
        "size": metadata.st_size,
        "mode": stat.S_IMODE(metadata.st_mode),
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "links": metadata.st_nlink,
        "mtime_ns": metadata.st_mtime_ns,
        "atime_ns": metadata.st_atime_ns,
        "ctime_ns": metadata.st_ctime_ns,
    }
    if any(not -(2**63) <= value < 2**63 for value in values.values()):
        raise ValueError("metadata exceeds signed 64-bit range")
    return {"kind": kind, **values}


def directory_names(path: str, limit: int) -> list[str]:
    """All sorted names or an error; never return an arbitrary truncated subset."""
    import stat

    if type(limit) is not int or not 1 <= limit <= 100000:
        raise ValueError("directory name limit must be 1..100000")
    directory = _filesystem_path(path)
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise ValueError("directory listing requires a directory, not a symlink")
    names = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(names) == limit:
                raise ValueError("directory name limit exceeded")
            entry.name.encode("utf-8")
            names.append(entry.name)
    return sorted(names)


def read_link(path: str) -> str:
    value = os.readlink(_filesystem_path(path))
    value.encode("utf-8")
    return value


def list_dir(path: str) -> list[str]:
    return sorted(child.name for child in Path(path).iterdir())


def path_exists(path: str) -> bool:
    return Path(path).exists()


def path_resolve(path: str) -> str:
    """Canonical absolute path; require the path and every parent to exist."""
    return str(Path(path).resolve(strict=True))


def path_join(parent: str, child: str) -> str:
    return str(Path(parent) / child)


def remove_file(path: str) -> None:
    Path(path).unlink()


def remove_dir(path: str) -> None:
    Path(path).rmdir()


def _regex(pattern: str, text: str) -> re.Pattern:
    if "(?" in pattern or re.search(r"\\[1-9]", pattern):
        raise ValueError("regex extensions and backreferences are unsupported")
    return re.compile(pattern, re.ASCII)


def regex_search(pattern: str, text: str) -> bool:
    return _regex(pattern, text).search(text) is not None


def regex_fullmatch(pattern: str, text: str) -> bool:
    return _regex(pattern, text).fullmatch(text) is not None


def regex_capture(pattern: str, text: str, full_match: bool) -> Json:
    """Return numbered captures and character spans, including group zero, or None."""
    if len(pattern.encode()) > 4096 or len(text.encode()) > 65536:
        raise ValueError("regex capture exceeds pattern or input byte limit")
    compiled = _regex(pattern, text)
    if compiled.groups > 64:
        raise ValueError("regex capture exceeds 64 groups")
    matched = compiled.fullmatch(text) if full_match else compiled.search(text)
    if matched is None:
        return None
    groups = [matched.group(index) for index in range(compiled.groups + 1)]
    spans = [list(matched.span(index)) if groups[index] is not None else None for index in range(len(groups))]
    return {"groups": groups, "spans": spans}


def regex_findall(pattern: str, text: str) -> list[str]:
    matches = list(_regex(pattern, text).finditer(text))
    if any(match.start() == match.end() for match in matches):
        raise ValueError("zero-width findall/replace matches are unsupported")
    return [match.group(0) for match in matches]


def regex_replace(pattern: str, replacement: str, text: str) -> str:
    regex_findall(pattern, text)
    return _regex(pattern, text).sub(lambda match: replacement, text)


@dataclass
class HttpResponse:
    status: int
    body: str


def http_request(method: str, url: str, body: str, timeout_ms: int, max_body: int) -> HttpResponse:
    return _http_request(method, url, body, timeout_ms, max_body, None)


def https_request_ca(method: str, url: str, body: str, timeout_ms: int, max_body: int, ca_file: str) -> HttpResponse:
    """Trust only this CA bundle, keeping certificate and hostname verification."""
    return _http_request(method, url, body, timeout_ms, max_body, ca_file)


def _http_request(
    method: str,
    url: str,
    body: str,
    timeout_ms: int,
    max_body: int,
    ca_file: str | None,
) -> HttpResponse:
    if not 1 <= max_body <= 1048576:
        raise ValueError("invalid HTTP body limit")
    response = _web_request(
        method, url, body.encode("utf-8"), {"Content-Type": "application/json"}, timeout_ms, max_body, ca_file
    )
    return HttpResponse(response.status, response.body.decode("utf-8"))


def web_request(
    method: str, url: str, body: bytes, headers: dict[str, str], timeout_ms: int, max_body: int
) -> "WebResponse":
    return _web_request(method, url, body, headers, timeout_ms, max_body, None)


def web_request_ca(
    method: str, url: str, body: bytes, headers: dict[str, str], timeout_ms: int, max_body: int, ca_file: str
) -> "WebResponse":
    return _web_request(method, url, body, headers, timeout_ms, max_body, ca_file)


def _web_request(
    method: str, url: str, body: bytes, headers: dict[str, str], timeout_ms: int, max_body: int, ca_file: str | None
) -> "WebResponse":
    with _open_http(method, url, body, headers, timeout_ms, max_body, ca_file) as response:
        data = bytearray()
        while True:
            chunk = web_read(response, 65536)
            if not chunk:
                break
            data.extend(chunk)
        return WebResponse(response.status, bytes(data), response.headers.copy())


@dataclass
class HttpReader:
    status: int
    headers: dict[str, str]
    connection: http.client.HTTPConnection
    response: http.client.HTTPResponse
    maximum: int
    deadline: float
    timer: threading.Timer
    received: int = 0
    closed: bool = False

    def __enter__(self) -> "HttpReader":  # noqa: PYI034 - retain the Python 3.10 runtime baseline
        if self.closed:
            raise ValueError("HTTP reader is closed")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        web_close(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            web_close(self)
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def web_open(url: str, headers: dict[str, str], timeout_ms: int, max_body: int) -> HttpReader:
    return _open_http("GET", url, b"", headers, timeout_ms, max_body, None)


def web_open_ca(url: str, headers: dict[str, str], timeout_ms: int, max_body: int, ca_file: str) -> HttpReader:
    return _open_http("GET", url, b"", headers, timeout_ms, max_body, ca_file)


def web_read(handle: HttpReader, count: int) -> bytes:
    if not 1 <= count <= 33554432:
        raise ValueError("HTTP read size must be 1..32 MiB")
    if handle.closed:
        raise ValueError("HTTP reader is closed")
    try:
        if time.monotonic() >= handle.deadline:
            raise TimeoutError("HTTP response deadline exceeded")
        data = handle.response.read(min(count, handle.maximum - handle.received + 1))
        if time.monotonic() >= handle.deadline:
            raise TimeoutError("HTTP response deadline exceeded")
        if len(data) > handle.maximum - handle.received:
            raise ValueError("HTTP body limit exceeded")
        if not data and handle.response.length is not None and handle.response.length > 0:
            raise http.client.IncompleteRead(data, handle.response.length)
        handle.received += len(data)
        return data
    except BaseException:
        web_close(handle)
        raise


def web_close(handle: HttpReader) -> None:
    if not handle.closed:
        handle.closed = True
        handle.timer.cancel()
        handle.timer.join()
        handle.response.close()
        handle.connection.close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def _open_http(
    method: str, url: str, body: bytes, headers: dict[str, str], timeout_ms: int, max_body: int, ca_file: str | None
) -> HttpReader:
    if method not in ("GET", "POST", "PUT", "DELETE"):
        raise ValueError("unsupported HTTP method")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("expected an http/https URL without credentials or fragment")
    if ca_file is not None and parsed.scheme != "https":
        raise ValueError("https_request_ca requires an https URL")
    if not 1 <= timeout_ms <= 86400000 or not 1 <= max_body <= 33554432 or len(body) > 33554432:
        raise ValueError("invalid HTTP timeout or body limit")
    normalized: dict[str, str] = {}
    for name, value in headers.items():
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-zA-Z-]+", name):
            raise ValueError("invalid HTTP header name")
        if not all(char == "\t" or 32 <= ord(char) <= 126 for char in value):
            raise ValueError("HTTP header values must be printable ASCII or tab")
        name = name.lower()
        if name in {"host", "content-length", "transfer-encoding", "connection"}:
            raise ValueError("transport header is managed by the client")
        if name in normalized:
            raise ValueError("duplicate HTTP header")
        normalized[name] = value
    normalized.setdefault("content-type", "application/octet-stream")
    normalized["connection"] = "close"
    if parsed.scheme == "https":
        context = ssl.create_default_context(cafile=ca_file)
        connection = http.client.HTTPSConnection(
            parsed.hostname, parsed.port, timeout=timeout_ms / 1000, context=context
        )
    else:
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout_ms / 1000)
    timer = None
    response = None
    deadline = time.monotonic() + timeout_ms / 1000
    try:
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        connection.request(
            method,
            path,
            body,
            normalized,
        )
        peer = connection.sock

        def expire() -> None:
            with contextlib.suppress(OSError):
                peer.shutdown(socket.SHUT_RDWR)
            peer.close()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        timer = threading.Timer(max(0.0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        response = connection.getresponse()
        response_headers: dict[str, str] = {}
        for name, value in response.getheaders():
            if not all(char == "\t" or 32 <= ord(char) <= 126 for char in value):
                raise ValueError("response header is not printable ASCII")
            response_headers.setdefault(name.lower(), value)
        return HttpReader(response.status, response_headers, connection, response, max_body, deadline, timer)
    except BaseException:
        if timer is not None:
            timer.cancel()
            timer.join()
        if response is not None:
            response.close()
        connection.close()
        raise


def http_listen(host: str, port: int) -> HttpServer:
    ipaddress.IPv4Address(host)
    if not 0 <= port <= 65535:
        raise ValueError("invalid port")
    return HttpServer((host, port), BaseHTTPRequestHandler)


def https_listen(host: str, port: int, cert_file: str, key_file: str) -> HttpServer:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # An explicit empty password rejects encrypted keys without prompting stdin.
    context.load_cert_chain(cert_file, key_file, password="")
    server = http_listen(host, port)
    server.tls_context = context
    return server


def http_port(server: HttpServer) -> int:
    return server.server_port


def http_serve_json(server: HttpServer, handler: Callable, count: int, max_body: int) -> None:
    http_serve_json_timeout(server, handler, count, max_body, 30000, 10000)


@contextlib.contextmanager
def _connection_deadline(connection: socket.socket, timeout_ms: int):
    # Absolute deadline, not just a timeout reset by each received byte. Shutdown
    # interrupts buffered reads, TLS handshakes and blocked response writes.
    def expire() -> None:
        with contextlib.suppress(OSError):
            connection.shutdown(socket.SHUT_RDWR)
        connection.close()

    timer = threading.Timer(timeout_ms / 1000, expire)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()
        connection.close()


def http_serve_json_timeout(
    server: HttpServer,
    handler: Callable,
    count: int,
    max_body: int,
    accept_timeout_ms: int,
    connection_timeout_ms: int,
) -> None:
    if not 1 <= count <= 100000 or not 1 <= max_body <= 1048576:
        raise ValueError("invalid HTTP request count or body limit")
    if not 1 <= accept_timeout_ms <= 86400000 or not 1 <= connection_timeout_ms <= 86400000:
        raise ValueError("server timeouts must be between 1 and 86400000 milliseconds")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.dispatch()

        do_POST = do_GET
        do_PUT = do_GET
        do_DELETE = do_GET

        def log_message(self, *args) -> None:
            return

        def dispatch(self) -> None:
            status = 200
            try:
                if self.headers.get("Transfer-Encoding"):
                    status = 400
                    raise ValueError("request transfer encoding is unsupported")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 <= length <= max_body:
                    status = 413
                    raise ValueError("HTTP body limit exceeded")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("incomplete HTTP body")
                request = json_loads(raw.decode("utf-8")) if raw else None
            except (ValueError, UnicodeError):
                if status == 200:
                    status = 400
                result = {"error": "invalid request"}
            else:
                try:
                    result = handler(self.command, self.path, request)
                    json_dumps(result)
                # Application handler failures become HTTP errors.
                except Exception:  # noqa: BLE001
                    status, result = 500, {"error": "handler failed"}
            data = json_dumps(result).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)

    try:
        server.socket.settimeout(accept_timeout_ms / 1000)
        for _ in range(count):
            # A stalled/broken peer consumes a connection slot. An idle accept
            # timeout propagates, allowing the process to stop predictably.
            connection, address = server.get_request()
            try:
                if server.tls_context is not None:
                    connection = server.tls_context.wrap_socket(
                        connection, server_side=True, do_handshake_on_connect=False
                    )
                with _connection_deadline(connection, connection_timeout_ms):
                    connection.settimeout(connection_timeout_ms / 1000)
                    if isinstance(connection, ssl.SSLSocket):
                        connection.do_handshake()
                    Handler(connection, address, server)
            except OSError:
                pass  # Connection errors do not kill the next healthy request.
            finally:
                connection.close()
    finally:
        server.server_close()


@dataclass
class WebRequest:
    method: str
    path: str
    headers: dict[str, str]
    query: dict[str, str]
    body: bytes
    target: str = ""


@dataclass
class WebResponse:
    status: int
    body: bytes
    headers: dict[str, str]
    stream: tuple[Json, int] | None = None


@dataclass
class StreamChunk:
    body: bytes
    state: Json
    done: bool


def _check_stream_state(state: Json) -> None:
    if len(json_dumps(state).encode()) > 65536:
        raise ValueError("stream state exceeds 64 KiB")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def stream_chunk(body: bytes, state: Json, done: bool) -> StreamChunk:
    if len(body) > 65536:
        raise ValueError("stream chunk exceeds 64 KiB")
    _check_stream_state(state)
    return StreamChunk(body, json_loads(json_dumps(state)), done)


def web_stream(headers: dict[str, str], state: Json, interval_ms: int) -> WebResponse:
    if not 1 <= interval_ms <= 60000:
        raise ValueError("stream interval must be 1..60000 milliseconds")
    if any(key.lower() in {"content-length", "transfer-encoding", "connection", "trailer"} for key in headers):
        raise ValueError("stream framing headers are managed by the server")
    _check_stream_state(state)
    response = web_response(200, b"", headers)
    response.stream = (json_loads(json_dumps(state)), interval_ms)
    return response


def web_response(status: int, body: bytes, headers: dict[str, str]) -> WebResponse:
    if not 200 <= status <= 599:
        raise ValueError("invalid response status")
    for key, value in headers.items():
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-zA-Z-]+", key) or "\r" in value or "\n" in value:
            raise ValueError("invalid response header")
    return WebResponse(status, body, headers.copy())


def web_serve(host: str, port: int, handler: Callable[[WebRequest], WebResponse]) -> None:
    _web_serve(host, port, handler, None)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def web_serve_stream(
    host: str,
    port: int,
    handler: Callable[[WebRequest], WebResponse],
    poll: Callable[[Json], StreamChunk],
) -> None:
    _web_serve(host, port, handler, poll)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def _web_serve(
    host: str,
    port: int,
    handler: Callable[[WebRequest], WebResponse],
    poll: Callable[[Json], StreamChunk] | None,
) -> None:
    from http.server import ThreadingHTTPServer
    from urllib.parse import parse_qsl

    lock = threading.Lock()
    streams = threading.BoundedSemaphore(32)
    connections = threading.BoundedSemaphore(64)

    class BoundedServer(ThreadingHTTPServer):
        def process_request(self, request: socket.socket, client_address: tuple) -> None:
            if not connections.acquire(blocking=False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                connections.release()
                raise
            return

        def process_request_thread(self, request: socket.socket, client_address: tuple) -> None:
            try:
                super().process_request_thread(request, client_address)
            finally:
                connections.release()
            return  # noqa: PLR1711 - explicit return required by repository guidelines

    class Adapter(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def do_GET(self) -> None:
            try:
                with _connection_deadline(self.connection, 60000):
                    self.respond(time.monotonic() + 60)
            except (OSError, ValueError):
                pass
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        def respond(self, deadline: float) -> None:
            self.connection.settimeout(60)
            headers = {key.lower(): value for key, value in self.headers.items()}
            if (
                self.command not in {"GET", "HEAD"}
                and "origin" in headers
                and urlsplit(headers["origin"]).netloc != headers.get("host", "")
            ):
                self.send_error(403)
                return
            length = int(headers.get("content-length", "0"))
            if length < 0 or length > 32 * 1024 * 1024 or "transfer-encoding" in headers:
                self.send_error(413)
                return
            parsed = urlsplit(self.path)
            request = WebRequest(
                self.command,
                parsed.path,
                headers,
                dict(parse_qsl(parsed.query)),
                self.rfile.read(length),
                self.requestline.split()[1],
            )
            try:
                with lock:
                    result = handler(request)
            except Exception:
                logging.getLogger(__name__).exception("request failed")
                result = web_response(
                    500, b'{"error":"The request could not be completed"}', {"content-type": "application/json"}
                )
            acquired = False
            if result.stream is not None:
                if poll is None:
                    result = web_response(500, b'{"error":"No stream poll callback configured"}', {})
                else:
                    acquired = streams.acquire(blocking=False)
                    if not acquired:
                        result = web_response(503, b'{"error":"Stream capacity reached"}', {})
            try:
                self.send_response(result.status)
                for key, value in result.headers.items():
                    self.send_header(key, value)
                if result.stream is None:
                    self.send_header("Content-Length", str(len(result.body)))
                self.send_header("Connection", "close")
                self.send_header("X-Content-Type-Options", "nosniff")
                if not any(name.lower() == "cache-control" for name in result.headers):
                    self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if result.stream is None:
                    self.wfile.write(result.body)
                else:
                    state, interval_ms = result.stream
                    while time.monotonic() < deadline:
                        with lock:
                            chunk = poll(state)
                        state = chunk.state
                        # Network writes never hold the application callback lock.
                        # The next callback waits for this bounded write to finish.
                        if chunk.body:
                            self.wfile.write(chunk.body)
                            self.wfile.flush()
                        if chunk.done:
                            break
                        time.sleep(min(interval_ms / 1000, max(0.0, deadline - time.monotonic())))
            except Exception:
                if result.stream is None:
                    raise
                # A stream error/disconnect ends its response, not the server.
            finally:
                if acquired:
                    streams.release()
            return

        do_POST = do_GET
        do_DELETE = do_GET
        do_PUT = do_GET

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = BoundedServer((host, port), Adapter)
    print(f"LISTENING http://{host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def env_get(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


def random_token() -> str:
    import secrets

    return secrets.token_hex(32)


def constant_time_equal(left: bytes, right: bytes) -> bool:
    """Compare byte contents without early mismatch exits; lengths are not secret."""
    import hmac

    return hmac.compare_digest(left, right)


def write_text_atomic(path: str, text: str) -> None:
    import os
    import tempfile

    parent = Path(path).parent
    name = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=parent, delete=False) as output:
            name = output.name
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
        descriptor = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def json_kind(value: Json) -> str:
    if value is None:
        return "null"
    return {bool: "bool", int: "number", float: "number", str: "string", list: "array", dict: "object"}[type(value)]


def json_parse(text: str, default: Json) -> Json:
    try:
        return json_loads(text)
    except (ValueError, UnicodeError):
        return default


def url_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
