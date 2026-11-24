"""Owned peer records and bounded queues preserve partially transmitted frames."""

from dataclasses import dataclass

from wire import encode

from py2rust.stdlib import TcpStream, int_to_bytes, json_dumps, monotonic


@dataclass
class Peer:
    key: str
    stream: TcpStream
    phase: str = "handshake"
    websocket: bool = False
    room: str = ""
    nick: str = ""
    incoming: bytes = b""
    outgoing: bytes = b""
    fragment: bytes = b""
    fragmented: bool = False
    active: float = 0.0
    partial: float = 0.0
    fragment_started: float = 0.0
    deadline: float = 0.0
    ack: bool = False
    reason: str = ""


def enqueue(peer: Peer, packet: bytes, policy: dict[str, int]) -> Peer:
    if peer.phase != "dead":
        if len(peer.outgoing) + len(packet) > policy["queue_bytes"]:
            peer.phase = "dead"
            peer.reason = "queue_limit"
            peer.outgoing = b""
        else:
            peer.outgoing = peer.outgoing + packet
    return peer


def closing(peer: Peer, payload: bytes, ack: bool, policy: dict[str, int]) -> Peer:
    if peer.phase == "open":
        peer = enqueue(peer, encode(8, payload), policy)
        if peer.phase != "dead":
            peer.phase = "closing"
            peer.deadline = monotonic() + float(policy["close_ms"]) * 0.001
            peer.ack = ack
            peer.reason = "close"
    elif peer.phase == "closing":
        peer.ack = peer.ack or ack
    else:
        peer.phase = "dead"
    return peer


def fail(peer: Peer, code: int, policy: dict[str, int]) -> Peer:
    peer.incoming = b""
    peer.fragment = b""
    return closing(peer, int_to_bytes(code, 2, "big"), False, policy)


def broadcast(
    peers: dict[str, Peer], sender: Peer, text: str, sequence: int, policy: dict[str, int]
) -> dict[str, Peer]:
    packet: bytes = encode(
        1,
        json_dumps(
            {"type": "message", "room": sender.room, "name": sender.nick, "sequence": sequence, "text": text}
        ).encode(),
    )
    for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
        target: Peer = peers[key]
        if target.phase == "open" and target.room == sender.room:
            peers[key] = enqueue(target, packet, policy)
    return peers
