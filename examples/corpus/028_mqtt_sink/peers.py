"""Connection state and finite output queues."""

from dataclasses import dataclass
from enum import Enum

from py2rust.stdlib import TcpStream


class Phase(Enum):
    CONNECT = "connect"
    OPEN = "open"
    DRAIN = "drain"
    DEAD = "dead"


@dataclass
class Peer:
    key: str
    stream: TcpStream
    phase: Phase
    client: str = ""
    incoming: bytes = b""
    outgoing: bytes = b""
    eof: bool = False
    keepalive: int = 0
    last_packet: float = 0.0
    partial: float = 0.0
    deadline: float = 0.0
    reason: str = ""


def enqueue(peer: Peer, data: bytes, policy: dict[str, int]) -> Peer:
    assert len(peer.outgoing) + len(data) <= policy["queue_bytes"], "reply queue exhausted"
    peer.outgoing = peer.outgoing + data
    return peer
