"""A fair readiness loop; every peer owns bounded input and output buffers."""

from config import configuration, stopping
from model import add, drop, ready_to_close, remove, store
from transport import expire, flush, parse

from py2rust.stdlib import (
    Json,
    TcpStream,
    env_get,
    json_array,
    json_bool,
    json_int,
    json_keys,
    json_loads,
    json_string,
    monotonic,
    tcp_accept_ready,
    tcp_close,
    tcp_listen,
    tcp_port,
    tcp_recv_ready,
    tcp_select,
    tcp_send_buffer,
)


def main() -> None:
    policy: Json = configuration()
    port: int = json_int(json_loads(env_get("ROOM_PORT", "8788")))
    state: Json = {
        "peers": {},
        "sequence": 0,
        "closed": {"slow": 0, "protocol": 0, "quit": 0, "disconnect": 0, "timeout": 0, "io": 0},
    }
    streams: dict[str, TcpStream] = {}
    buffers: dict[str, bytes] = {}
    next_id: int = 0
    capacity: int = json_int(policy["line_bytes"]) + 8192
    with tcp_listen("127.0.0.1", port) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while not stopping():
            readers: list[TcpStream] = []
            writers: list[TcpStream] = []
            read_keys: list[str] = []
            write_keys: list[str] = []
            delay: int = 20
            for key in json_keys(state["peers"]):
                peer: Json = state["peers"][key]
                if json_string(peer["closing"]) == "":
                    if len(buffers[key]) < capacity:
                        readers.append(streams[key])
                        read_keys.append(key)
                    if buffers[key].find(b"\n") >= 0:
                        delay = 0
                if json_int(peer["queued"]) > 0:
                    writers.append(streams[key])
                    write_keys.append(key)
            events: Json = tcp_select(listener, readers, writers, delay)
            if json_bool(events["accept"]):
                for stream in tcp_accept_ready(listener, 8, 1000):
                    if len(json_keys(state["peers"])) >= json_int(policy["max_peers"]):
                        tcp_close(stream)
                    else:
                        next_id = next_id + 1
                        key: str = str(next_id)
                        tcp_send_buffer(stream, json_int(policy["send_buffer"]))
                        streams[key] = stream
                        buffers[key] = b""
                        state = add(state, key, policy)
            for value in json_array(events["read"]):
                key: str = read_keys[json_int(value)]
                try:
                    part: tuple[bytes, bool] = tcp_recv_ready(streams[key], min(4096, capacity - len(buffers[key])))
                    if part[1]:
                        state = drop(state, key, "disconnect", False, policy)
                    elif len(part[0]) > 0:
                        peer: Json = state["peers"][key]
                        peer["active"] = monotonic()
                        if len(buffers[key]) == 0:
                            peer["partial"] = monotonic()
                        state = store(state, key, peer)
                        buffers[key] = buffers[key] + part[0]
                except Exception:  # noqa: BLE001 - recoverable subset boundary isolates peer failures
                    state = drop(state, key, "io", False, policy)
            for key in json_keys(state["peers"]):
                if json_string(state["peers"][key]["closing"]) == "":
                    parsed: tuple[Json, bytes] = parse(state, key, buffers[key], policy)
                    state = parsed[0]
                    buffers[key] = parsed[1]
            for value in json_array(events["write"]):
                key: str = write_keys[json_int(value)]
                try:
                    state = flush(state, key, streams[key], policy)
                except Exception:  # noqa: BLE001 - recoverable subset boundary isolates peer failures
                    state = drop(state, key, "io", False, policy)
            for key in json_keys(state["peers"]):
                state = expire(state, key, buffers[key], policy)
                if ready_to_close(state["peers"][key]):
                    tcp_close(streams[key])
                    del streams[key]
                    del buffers[key]
                    state = remove(state, key, policy)
        for key in json_keys(state["peers"]):
            tcp_close(streams[key])
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
