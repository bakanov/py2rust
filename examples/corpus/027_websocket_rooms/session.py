"""Text fragmentation, control frames and deadlines without blocking other peers."""

from handshake import http_reply, upgrade
from peers import Peer, broadcast, closing, enqueue, fail
from wire import Frame, close_error, decode, encode

from py2rust.stdlib import json_dumps, monotonic


def advance(
    peers: dict[str, Peer], key: str, sequence: int, home: bytes, policy: dict[str, int]
) -> tuple[dict[str, Peer], int, bool]:
    peer: Peer = peers[key]
    now: float = monotonic()
    if peer.phase == "handshake":
        try:
            if now >= peer.deadline:
                peer = http_reply(peer, "408 Request Timeout", b"Handshake timeout\n", policy, "")
            else:
                peer = upgrade(peer, peers, home, policy)
        except Exception:  # noqa: BLE001 - reject malformed HTTP independently for each peer
            peer = http_reply(peer, "400 Bad Request", b"Invalid handshake\n", policy, "")
        if peer.phase == "open":
            peer = enqueue(
                peer,
                encode(
                    1,
                    json_dumps(
                        {"type": "welcome", "room": peer.room, "name": peer.nick, "max_bytes": policy["message_bytes"]}
                    ).encode(),
                ),
                policy,
            )
    if peer.phase == "open":
        if now - peer.active >= float(policy["idle_ms"]) * 0.001:
            peer = fail(peer, 1001, policy)
        elif (len(peer.incoming) > 0 and now - peer.partial >= float(policy["partial_ms"]) * 0.001) or (
            peer.fragmented and now - peer.fragment_started >= float(policy["partial_ms"]) * 0.001
        ):
            peer = fail(peer, 1008, policy)
    again: bool = False
    for index in range(policy["frames_per_tick"]):
        if not peer.websocket or peer.phase not in ["open", "closing"]:
            break
        frame: Frame = decode(peer.incoming, policy["message_bytes"])
        if frame.close_code != 0:
            if peer.phase == "closing":
                peer.phase = "dead"
            else:
                peer = fail(peer, frame.close_code, policy)
            break
        if frame.consumed == 0:
            break
        peer.incoming = peer.incoming[frame.consumed :]
        peer.partial = monotonic()
        again = index + 1 == policy["frames_per_tick"] and len(peer.incoming) > 0
        if frame.opcode == 8:
            error: int = close_error(frame.payload)
            if error != 0:
                peer = fail(peer, error, policy)
            else:
                peer = closing(peer, frame.payload, True, policy)
            break
        if peer.phase == "closing":
            continue
        if frame.opcode == 9:
            peer = enqueue(peer, encode(10, frame.payload), policy)
        elif frame.opcode in [0, 1]:
            if (frame.opcode == 0 and not peer.fragmented) or (frame.opcode == 1 and peer.fragmented):
                peer = fail(peer, 1002, policy)
                break
            if len(peer.fragment) + len(frame.payload) > policy["message_bytes"]:
                peer = fail(peer, 1009, policy)
                break
            if frame.opcode == 1:
                peer.fragment_started = monotonic()
            peer.fragment = peer.fragment + frame.payload
            peer.fragmented = not frame.finished
            if frame.finished:
                try:
                    text: str = peer.fragment.decode()
                    peer.fragment = b""
                    sequence = sequence + 1
                    peers[key] = peer
                    peers = broadcast(peers, peer, text, sequence, policy)
                    peer = peers[key]
                except Exception:  # noqa: BLE001 - finished text must be valid UTF-8
                    peer = fail(peer, 1007, policy)
    peers[key] = peer
    return (peers, sequence, again)
