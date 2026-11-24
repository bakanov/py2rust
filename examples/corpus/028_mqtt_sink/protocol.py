"""CONNECT negotiation, client takeover, QoS-0 ingestion and control packets."""

from peers import Peer, Phase, enqueue
from storage import publish
from wire import Packet, decode, field, text, topic_name

from py2rust.stdlib import int_from_bytes, int_to_bytes, monotonic


def connect(peer: Peer, body: bytes, policy: dict[str, int]) -> Peer:
    assert len(body) >= 10 and body[:6] == b"\x00\x04MQTT", "invalid protocol name"
    code: int = 0
    if body[6] != 4:
        code = 1
    else:
        flags: int = body[7]
        assert flags & 1 == 0 and (flags & 128 != 0 or flags & 64 == 0), "invalid CONNECT flags"
        assert (flags & 4 != 0 or flags & 56 == 0) and flags & 24 != 24, "invalid Will flags"
        parsed: tuple[bytes, int] = field(body, 10)
        client: str = text(parsed[0])
        offset: int = parsed[1]
        if flags & 4 != 0:
            parsed = field(body, offset)
            topic_name(parsed[0], policy["topic_bytes"])
            parsed = field(body, parsed[1])
            offset = parsed[1]
        if flags & 128 != 0:
            parsed = field(body, offset)
            text(parsed[0])
            offset = parsed[1]
        if flags & 64 != 0:
            parsed = field(body, offset)
            offset = parsed[1]
        assert offset == len(body), "trailing CONNECT data"
        if len(client.encode()) == 0 or len(client.encode()) > 64:
            code = 2
        elif flags != 2:
            code = 5
        else:
            peer.client = client
            peer.keepalive = int_from_bytes(body[8:10], "big")
    peer = enqueue(peer, b"\x20\x02\x00" + int_to_bytes(code, 1, "big"), policy)
    if code == 0:
        peer.phase = Phase.OPEN
    else:
        peer.phase = Phase.DRAIN
        peer.reason = "connect_refused"
        peer.deadline = monotonic() + float(policy["close_ms"]) * 0.001
    return peer


def advance(peers: dict[str, Peer], key: str, policy: dict[str, int]) -> tuple[dict[str, Peer], bool]:
    peer: Peer = peers[key]
    again: bool = False
    try:
        now: float = monotonic()
        assert peer.phase != Phase.CONNECT or now < peer.deadline, "handshake deadline"
        assert len(peer.incoming) == 0 or now - peer.partial < float(policy["partial_ms"]) * 0.001, "partial deadline"
        assert (
            peer.phase != Phase.OPEN or peer.keepalive == 0 or now - peer.last_packet < float(peer.keepalive) * 1.5
        ), "keepalive deadline"
        for index in range(policy["packets_per_tick"]):
            if peer.phase not in [Phase.CONNECT, Phase.OPEN]:
                break
            packet: Packet = decode(peer.incoming, policy["packet_bytes"])
            if packet.consumed == 0:
                break
            peer.incoming = peer.incoming[packet.consumed :]
            peer.partial = monotonic()
            peer.last_packet = peer.partial
            again = index + 1 == policy["packets_per_tick"] and len(peer.incoming) > 0
            if peer.phase == Phase.CONNECT:
                assert packet.kind == 1, "CONNECT must be first"
                peer = connect(peer, packet.body, policy)
                if peer.phase == Phase.OPEN:
                    for other_key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
                        other: Peer = peers[other_key]
                        if other_key != key and other.phase == Phase.OPEN and other.client == peer.client:
                            other.phase = Phase.DEAD
                            other.reason = "client_takeover"
                            peers[other_key] = other
            elif packet.kind == 3:
                parsed: tuple[bytes, int] = field(packet.body, 0)
                topic: str = topic_name(parsed[0], policy["topic_bytes"])
                data: bytes = packet.body[parsed[1] :]
                assert len(data) <= policy["payload_bytes"], "payload exceeds limit"
                number: int = publish(topic, data, peer.client, packet.retained, policy)
                print("STORED " + str(number))
            else:
                assert len(packet.body) == 0 and packet.kind in [12, 14], "unexpected control packet"
                if packet.kind == 12:
                    peer = enqueue(peer, b"\xd0\x00", policy)
                else:
                    peer.phase = Phase.DEAD
                    peer.reason = "disconnect"
        if peer.eof and not again and peer.phase in [Phase.CONNECT, Phase.OPEN]:
            peer.phase = Phase.DRAIN
            peer.reason = "eof"
            peer.deadline = monotonic() + float(policy["close_ms"]) * 0.001
            if len(peer.incoming) > 0:
                peer.phase = Phase.DEAD
                peer.reason = "truncated_packet"
    except Exception as error:  # noqa: BLE001 - malformed peers and failed storage do not stop other clients
        peer.phase = Phase.DEAD
        peer.reason = str(error)
    peers[key] = peer
    return (peers, again)
