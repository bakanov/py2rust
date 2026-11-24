"""A loopback MQTT telemetry sink; all packet handling and persistence are Python."""

from peers import Peer, Phase
from protocol import advance
from settings import configuration
from storage import load

from py2rust.stdlib import (
    Json,
    TcpStream,
    env_get,
    json_array,
    json_bool,
    json_int,
    monotonic,
    path_exists,
    pretty,
    tcp_accept_ready,
    tcp_close,
    tcp_listen,
    tcp_port,
    tcp_recv_ready,
    tcp_select,
    tcp_send_buffer,
    tcp_send_ready,
)


def main() -> None:
    policy: dict[str, int] = configuration()
    state: Json = load(policy)
    mode: str = env_get("MQTT_MODE", "serve")
    assert mode in ["serve", "report"], "mode must be serve or report"
    if mode == "report":
        print(pretty(state))
        return
    peers: dict[str, Peer] = {}
    next_id: int = 0
    delay: int = 20
    capacity: int = policy["packet_bytes"] + 4101
    with tcp_listen("127.0.0.1", policy["port"]) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while True:
            marker: str = env_get("MQTT_STOP", "")
            if marker != "" and path_exists(marker):
                break
            readers: list[TcpStream] = []
            writers: list[TcpStream] = []
            read_keys: list[str] = []
            write_keys: list[str] = []
            for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
                peer: Peer = peers[key]
                if not peer.eof and peer.phase in [Phase.CONNECT, Phase.OPEN] and len(peer.incoming) < capacity:
                    readers.append(peer.stream)
                    read_keys.append(key)
                if peer.phase != Phase.DEAD and len(peer.outgoing) > 0:
                    writers.append(peer.stream)
                    write_keys.append(key)
            events: Json = tcp_select(listener, readers, writers, delay)
            if json_bool(events["accept"]):
                for stream in tcp_accept_ready(listener, 8, 1000):
                    if len(peers) >= policy["max_peers"]:
                        tcp_close(stream)
                    else:
                        next_id = next_id + 1
                        tcp_send_buffer(stream, 1024)
                        key: str = str(next_id)
                        peers[key] = Peer(
                            key,
                            stream,
                            Phase.CONNECT,
                            deadline=monotonic() + float(policy["handshake_ms"]) * 0.001,
                        )
            for value in json_array(events["write"]):
                key: str = write_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    sent: int = tcp_send_ready(peer.stream, peer.outgoing[: policy["write_bytes"]])
                    peer.outgoing = peer.outgoing[sent:]
                except Exception:  # noqa: BLE001 - isolate socket failures
                    peer.phase = Phase.DEAD
                    peer.reason = "write_error"
                peers[key] = peer
            for value in json_array(events["read"]):
                key: str = read_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    part: tuple[bytes, bool] = tcp_recv_ready(peer.stream, min(4096, capacity - len(peer.incoming)))
                    if part[1]:
                        peer.eof = True
                    elif len(part[0]) > 0:
                        if len(peer.incoming) == 0:
                            peer.partial = monotonic()
                        peer.incoming = peer.incoming + part[0]
                except Exception:  # noqa: BLE001 - isolate socket failures
                    peer.phase = Phase.DEAD
                    peer.reason = "read_error"
                peers[key] = peer
            delay = 20
            for key in list(peers):
                result: tuple[dict[str, Peer], bool] = advance(peers, key, policy)
                peers = result[0]
                if result[1]:
                    delay = 0
                peer: Peer = peers[key]
                if peer.phase == Phase.DEAD or (
                    peer.phase == Phase.DRAIN and (len(peer.outgoing) == 0 or monotonic() >= peer.deadline)
                ):
                    tcp_close(peer.stream)
                    del peers[key]
                    print("CLOSED " + key + " " + peer.reason)
        for key in peers:
            tcp_close(peers[key].stream)
    return


if __name__ == "__main__":
    main()
