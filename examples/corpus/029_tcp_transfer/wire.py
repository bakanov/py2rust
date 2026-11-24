"""Length-prefixed frames with absolute frame and whole-session deadlines."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    TcpStream,
    ceil,
    int_from_bytes,
    int_to_bytes,
    json_dumps,
    json_loads,
    monotonic,
    tcp_recv,
    tcp_sendall,
    tcp_set_deadline,
)


@dataclass
class Connection:
    stream: TcpStream
    deadline: float
    timeout: int


def connection(stream: TcpStream, policy: dict[str, int]) -> Connection:
    return Connection(stream, monotonic() + float(policy["session_ms"]) * 0.001, policy["io_ms"])


def deadline(wire: Connection) -> None:
    remaining: int = ceil((wire.deadline - monotonic()) * 1000.0)
    assert remaining > 0, "session deadline"
    tcp_set_deadline(wire.stream, min(wire.timeout, remaining))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def exact(wire: Connection, size: int) -> bytes:
    chunks: list[bytes] = []
    count: int = 0
    while count < size:
        data: bytes = tcp_recv(wire.stream, min(65536, size - count))
        assert len(data) > 0, "truncated frame"
        chunks.append(data)
        count = count + len(data)
    return b"".join(chunks)


def receive(wire: Connection, limit: int) -> bytes:
    deadline(wire)
    size: int = int_from_bytes(exact(wire, 4), "big")
    assert size > 0 and size <= limit, "invalid frame length"
    return exact(wire, size)


def read_json(wire: Connection) -> Json:
    return json_loads(receive(wire, 1024).decode())


def frame(data: bytes) -> bytes:
    return int_to_bytes(len(data), 4, "big") + data


def send_json(wire: Connection, value: Json) -> None:
    data: bytes = json_dumps(value).encode()
    assert len(data) <= 1024, "control frame exceeds limit"
    deadline(wire)
    tcp_sendall(wire.stream, frame(data))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def send_chunk(wire: Connection, header: Json, data: bytes) -> None:
    deadline(wire)
    tcp_sendall(wire.stream, frame(json_dumps(header).encode()) + frame(data))
    return  # noqa: PLR1711 - explicit return required by repository guidelines
