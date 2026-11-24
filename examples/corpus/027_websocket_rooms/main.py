"""Fair socket readiness, per-peer state and bounded shutdown for a room server."""

from peers import Peer, fail
from session import advance

from py2rust.stdlib import (
    Json,
    TcpStream,
    env_get,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_keys,
    json_loads,
    monotonic,
    path_exists,
    read_bytes,
    read_text,
    tcp_accept_ready,
    tcp_close,
    tcp_listen,
    tcp_port,
    tcp_recv_ready,
    tcp_select,
    tcp_send_buffer,
    tcp_send_ready,
)


def configuration() -> dict[str, int]:
    text: str = read_text(env_get("WS_CONFIG", "rooms.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_peers": (32, 1, 64),
        "message_bytes": (8192, 1, 65536),
        "queue_bytes": (262144, 8192, 1048576),
        "frames_per_tick": (4, 1, 32),
        "handshake_ms": (3000, 50, 30000),
        "partial_ms": (3000, 50, 30000),
        "idle_ms": (60000, 100, 300000),
        "close_ms": (500, 50, 5000),
        "send_buffer": (8192, 1024, 65536),
        "write_bytes": (16384, 1, 65536),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: dict[str, int] = {}
    for key in bounds:  # noqa: PLC0206 - use the supported dictionary-key iterator
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    assert policy["queue_bytes"] >= 6 * policy["message_bytes"] + 512, "queue cannot hold a JSON message"
    policy["port"] = json_int(json_loads(env_get("WS_PORT", "8791")))
    assert policy["port"] >= 0 and policy["port"] <= 65535, "invalid port"
    return policy


def main() -> None:
    policy: dict[str, int] = configuration()
    home: bytes = read_bytes(env_get("WS_HOME", "client.html"))
    assert len(home) <= 4096, "browser client exceeds 4 KiB"
    peers: dict[str, Peer] = {}
    next_id: int = 0
    sequence: int = 0
    stopped: bool = False
    delay: int = 20
    capacity: int = max(8192, policy["message_bytes"] + 14) + 4096
    with tcp_listen("127.0.0.1", policy["port"]) as listener:
        policy["port"] = tcp_port(listener)
        print("LISTENING tcp://127.0.0.1:" + str(policy["port"]))
        while not stopped or len(peers) > 0:
            marker: str = env_get("WS_STOP", "")
            if not stopped and marker != "" and path_exists(marker):
                stopped = True
                for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
                    peers[key] = fail(peers[key], 1001, policy)
            readers: list[TcpStream] = []
            writers: list[TcpStream] = []
            read_keys: list[str] = []
            write_keys: list[str] = []
            for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
                peer: Peer = peers[key]
                if (peer.phase in ["handshake", "open"] or (peer.phase == "closing" and peer.websocket)) and len(
                    peer.incoming
                ) < capacity:
                    readers.append(peer.stream)
                    read_keys.append(key)
                if peer.phase != "dead" and len(peer.outgoing) > 0:
                    writers.append(peer.stream)
                    write_keys.append(key)
            events: Json = tcp_select(listener, readers, writers, delay)
            if json_bool(events["accept"]):
                for stream in tcp_accept_ready(listener, 8, 1000):
                    if stopped or len(peers) >= policy["max_peers"]:
                        tcp_close(stream)
                    else:
                        next_id = next_id + 1
                        tcp_send_buffer(stream, policy["send_buffer"])
                        key: str = str(next_id)
                        peers[key] = Peer(
                            key,
                            stream,
                            active=monotonic(),
                            deadline=monotonic() + float(policy["handshake_ms"]) * 0.001,
                        )
            for value in json_array(events["write"]):
                key: str = write_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    sent: int = tcp_send_ready(peer.stream, peer.outgoing[: policy["write_bytes"]])
                    peer.outgoing = peer.outgoing[sent:]
                except Exception:  # noqa: BLE001 - isolate write failures
                    peer.phase = "dead"
                    peer.reason = "io"
                peers[key] = peer
            for value in json_array(events["read"]):
                key: str = read_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    part: tuple[bytes, bool] = tcp_recv_ready(peer.stream, min(4096, capacity - len(peer.incoming)))
                    if part[1]:
                        if peer.phase == "closing":
                            peer.ack = True
                        else:
                            peer.phase = "dead"
                            peer.reason = "disconnect"
                    elif len(part[0]) > 0:
                        if len(peer.incoming) == 0:
                            peer.partial = monotonic()
                        peer.incoming = peer.incoming + part[0]
                        peer.active = monotonic()
                except Exception:  # noqa: BLE001 - isolate read failures
                    peer.phase = "dead"
                    peer.reason = "io"
                peers[key] = peer
            delay = 20
            for key in list(peers):
                result: tuple[dict[str, Peer], int, bool] = advance(peers, key, sequence, home, policy)
                peers = result[0]
                sequence = result[1]
                if result[2]:
                    delay = 0
                peer: Peer = peers[key]
                if peer.phase == "dead" or (
                    peer.phase == "closing" and ((peer.ack and len(peer.outgoing) == 0) or monotonic() >= peer.deadline)
                ):
                    tcp_close(peer.stream)
                    del peers[key]
                    print("CLOSED " + key + " " + peer.nick + " " + peer.reason)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
