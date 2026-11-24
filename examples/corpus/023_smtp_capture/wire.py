"""CRLF framing and transparent DATA octets with bounded memory and deadlines."""

from py2rust.stdlib import (
    Json,
    TcpStream,
    json_int,
    tcp_recv,
    tcp_sendall,
    tcp_set_deadline,
)


def reply(stream: TcpStream, text: str, policy: Json) -> None:
    tcp_set_deadline(stream, json_int(policy["command_ms"]))
    tcp_sendall(stream, (text + "\r\n").encode())
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def line(stream: TcpStream, buffer: bytes, limit: int) -> tuple[bytes, bytes, bool]:
    while True:
        end: int = buffer.find(b"\n")
        if end >= 0:
            assert end + 1 <= limit and end >= 1 and buffer[end - 1] == 13, "invalid CRLF line"
            value: bytes = buffer[: end - 1]
            assert value.find(b"\r") < 0, "bare carriage return"
            return (value, buffer[end + 1 :], True)
        assert len(buffer) < limit, "line exceeds limit"
        chunk: bytes = tcp_recv(stream, min(4096, limit - len(buffer)))
        if len(chunk) == 0:
            assert len(buffer) == 0, "truncated line"
            return (b"", b"", False)
        buffer = buffer + chunk
    return (b"", b"", False)


def data(stream: TcpStream, buffer: bytes, body: str, policy: Json) -> tuple[bytes, bytes, int]:
    tcp_set_deadline(stream, json_int(policy["data_ms"]))
    chunks: list[bytes] = []
    size: int = 0
    status: int = 250
    while True:
        incoming: tuple[bytes, bytes, bool] = line(stream, buffer, 1001)
        assert incoming[2], "EOF before DATA terminator"
        buffer = incoming[1]
        value: bytes = incoming[0]
        if value == b".":
            return (b"".join(chunks), buffer, status)
        if value.startswith(b"."):
            value = value[1:]
        assert len(value) <= 998, "DATA line exceeds 1000 octets"
        size = size + len(value) + 2
        assert size <= 2 * json_int(policy["max_bytes"]) + 4096, "discard budget exceeded"
        if size > json_int(policy["max_bytes"]):
            status = 552
        for index in range(len(value)):
            if status == 250 and (value[index] == 0 or (body == "7BIT" and value[index] >= 128)):
                status = 554
        if status == 250:
            chunks.append(value + b"\r\n")
    return (b"", b"", 451)
