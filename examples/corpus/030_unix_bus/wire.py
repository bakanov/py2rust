"""Length-prefixed UTF-8 JSON, peer buffers and explicit end-of-stream state."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    UnixStream,
    int_from_bytes,
    int_to_bytes,
    json_dumps,
    unix_recv,
)


@dataclass
class Peer:
    stream: UnixStream
    deadline: float
    incoming: bytes = b""
    outgoing: bytes = b""
    partial: float = 0.0
    eof: bool = False
    closing: bool = False


def encode(value: Json) -> bytes:
    body: bytes = json_dumps(value).encode()
    return int_to_bytes(len(body), 4, "big") + body


def ready(peer: Peer) -> bool:
    if len(peer.incoming) < 4:
        return False
    return len(peer.incoming) >= 4 + int_from_bytes(peer.incoming[:4], "big")


def exact(stream: UnixStream, count: int) -> bytes:
    result: bytes = b""
    while len(result) < count:
        part: bytes = unix_recv(stream, count - len(result))
        assert len(part) > 0, "truncated reply"
        result = result + part
    return result
