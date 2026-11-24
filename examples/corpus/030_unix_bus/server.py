"""A fair readiness loop with bounded queues and graceful reply draining."""

from commands import error, execute
from wire import Peer, encode, ready

from py2rust.stdlib import (
    Json,
    UnixStream,
    env_get,
    int_from_bytes,
    json_array,
    json_bool,
    json_int,
    json_loads,
    monotonic,
    path_exists,
    unix_accept_ready,
    unix_close,
    unix_listen,
    unix_recv_ready,
    unix_select,
    unix_send_buffer,
    unix_send_ready,
)


def advance(peer: Peer, state: Json, policy: dict[str, int]) -> tuple[Peer, Json, bool]:
    stopping: bool = False
    for turn in range(8):
        if peer.closing or stopping or len(peer.outgoing) + policy["frame_bytes"] + 4 > policy["queue_bytes"]:
            break
        if len(peer.incoming) < 4:
            break
        size: int = int_from_bytes(peer.incoming[:4], "big")
        if size == 0 or size > policy["frame_bytes"]:
            peer.outgoing = peer.outgoing + encode(error("", "frame", "invalid frame length"))
            peer.closing = True
            break
        if not ready(peer):
            break
        body: bytes = peer.incoming[4 : size + 4]
        peer.incoming = peer.incoming[size + 4 :]
        peer.partial = monotonic() if len(peer.incoming) > 0 else 0.0
        response: Json = error("", "json", "invalid UTF-8 JSON")
        try:
            request: Json = json_loads(body.decode())
            outcome: tuple[Json, Json, bool] = execute(request, state, policy)
            state = outcome[0]
            response = outcome[1]
            stopping = outcome[2]
        except Exception:  # noqa: BLE001, S110 - return the structured JSON error already prepared
            pass
        peer.outgoing = peer.outgoing + encode(response)
    if peer.eof and not ready(peer) and not peer.closing and len(peer.outgoing) + 512 <= policy["queue_bytes"]:
        if len(peer.incoming) > 0:
            peer.outgoing = peer.outgoing + encode(error("", "frame", "truncated request"))
        peer.closing = True
    if peer.closing:
        peer.deadline = min(peer.deadline, monotonic() + float(policy["drain_ms"]) * 0.001)
    return (peer, state, stopping)


def serve(policy: dict[str, int]) -> None:
    peers: dict[str, Peer] = {}
    state: Json = {"values": {}, "receipts": {}, "order": []}
    next_id: int = 0
    stopping: bool = False
    delay: int = 20
    capacity: int = policy["frame_bytes"] + 4
    with unix_listen(env_get("BUS_SOCKET", "command.sock"), True) as listener:
        print("LISTENING unix://" + env_get("BUS_SOCKET", "command.sock"))
        while True:
            marker: str = env_get("BUS_STOP", "")
            if marker != "" and path_exists(marker):
                stopping = True
            readers: list[UnixStream] = []
            writers: list[UnixStream] = []
            read_keys: list[str] = []
            write_keys: list[str] = []
            for key in peers:  # noqa: PLC0206 - supported dictionary-key iteration
                peer: Peer = peers[key]
                if stopping and not peer.closing:
                    peer.closing = True
                    peer.deadline = min(peer.deadline, monotonic() + float(policy["drain_ms"]) * 0.001)
                    peers[key] = peer
                if not peer.closing and not peer.eof and len(peer.incoming) < capacity:
                    readers.append(peer.stream)
                    read_keys.append(key)
                if len(peer.outgoing) > 0:
                    writers.append(peer.stream)
                    write_keys.append(key)
            events: Json = unix_select(listener, readers, writers, delay)
            if json_bool(events["accept"]):
                for stream in unix_accept_ready(listener, 8, 1000):
                    if stopping or len(peers) >= policy["max_peers"]:
                        unix_close(stream)
                    else:
                        next_id = next_id + 1
                        unix_send_buffer(stream, 1024)
                        peers[str(next_id)] = Peer(stream, monotonic() + float(policy["session_ms"]) * 0.001)
            for value in json_array(events["write"]):
                key: str = write_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    sent: int = unix_send_ready(peer.stream, peer.outgoing[: policy["write_bytes"]])
                    peer.outgoing = peer.outgoing[sent:]
                except Exception:  # noqa: BLE001 - isolate one disconnected peer
                    peer.deadline = 0.0
                peers[key] = peer
            for value in json_array(events["read"]):
                key: str = read_keys[json_int(value)]
                peer: Peer = peers[key]
                try:
                    part: tuple[bytes, bool] = unix_recv_ready(peer.stream, min(4096, capacity - len(peer.incoming)))
                    peer.eof = part[1]
                    if len(part[0]) > 0:
                        if len(peer.incoming) == 0:
                            peer.partial = monotonic()
                        peer.incoming = peer.incoming + part[0]
                except Exception:  # noqa: BLE001 - isolate one disconnected peer
                    peer.deadline = 0.0
                peers[key] = peer
            delay = 20
            for key in list(peers):
                peer: Peer = peers[key]
                if not stopping and not peer.closing:
                    outcome: tuple[Peer, Json, bool] = advance(peer, state, policy)
                    peer = outcome[0]
                    state = outcome[1]
                    stopping = outcome[2]
                if ready(peer) and len(peer.outgoing) + capacity <= policy["queue_bytes"]:
                    delay = 0
                if peer.partial > 0.0 and monotonic() - peer.partial >= float(policy["partial_ms"]) * 0.001:
                    peer.deadline = 0.0
                if monotonic() >= peer.deadline or (peer.closing and len(peer.outgoing) == 0):
                    unix_close(peer.stream)
                    del peers[key]
                else:
                    peers[key] = peer
            if stopping and len(peers) == 0:
                break
    return  # noqa: PLR1711 - explicit return required by repository guidelines
