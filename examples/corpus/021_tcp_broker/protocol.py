"""Four-byte big-endian lengths and UTF-8 JSON, independent of TCP chunk boundaries."""

from py2rust.stdlib import (
    Json,
    TcpStream,
    json_dumps,
    tcp_recv,
    tcp_sendall,
    tcp_set_deadline,
)


def exact(stream: TcpStream, size: int, allow_eof: bool) -> bytes:
    chunks: list[bytes] = []
    received: int = 0
    while received < size:
        chunk: bytes = tcp_recv(stream, min(4096, size - received))
        if len(chunk) == 0:
            assert allow_eof and received == 0, "truncated frame"
            return b""
        chunks.append(chunk)
        received = received + len(chunk)
    return b"".join(chunks)


def receive(stream: TcpStream, limit: int, timeout: int) -> bytes:
    tcp_set_deadline(stream, timeout)
    header: bytes = exact(stream, 4, True)
    if len(header) == 0:
        return b""
    size: int = int.from_bytes(header, "big")
    assert size >= 1 and size <= limit, "invalid frame length"
    return exact(stream, size, False)


def send(stream: TcpStream, value: Json, limit: int, timeout: int) -> None:
    body: bytes = json_dumps(value).encode()
    assert len(body) >= 1 and len(body) <= limit, "reply exceeds frame limit"
    length: int = len(body)
    tcp_set_deadline(stream, timeout)
    tcp_sendall(stream, length.to_bytes(4, "big") + body)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
