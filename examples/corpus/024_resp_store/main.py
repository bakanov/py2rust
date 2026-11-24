"""Several peers, fair command budgets, partial I/O and bounded input/output queues."""

from codec import error, parse
from commands import execute
from config import configuration, stopping
from storage import fault, load

from py2rust.stdlib import (
    Json,
    TcpStream,
    env_get,
    json_array,
    json_bool,
    json_float,
    json_int,
    json_is_null,
    json_loads,
    monotonic,
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
    policy: Json = configuration()
    load(policy)
    peers: dict[str, TcpStream] = {}
    incoming: dict[str, bytes] = {}
    outgoing: dict[str, bytes] = {}
    activity: dict[str, float] = {}
    started: dict[str, float] = {}
    closing: dict[str, bool] = {}
    ended: dict[str, bool] = {}
    sequence: int = 0
    delay: int = 25
    port: int = json_int(json_loads(env_get("KV_PORT", "6380")))
    with tcp_listen("127.0.0.1", port) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while not stopping():
            keys: list[str] = []
            for key in peers:
                keys.append(key)  # noqa: PERF402 - copy dictionary keys using supported typed iteration
            readers: list[TcpStream] = []
            read_keys: list[str] = []
            writers: list[TcpStream] = []
            for key in keys:
                if not closing[key] and not ended[key]:
                    readers.append(peers[key])
                    read_keys.append(key)
                if len(outgoing[key]) > 0:
                    writers.append(peers[key])
            events: Json = tcp_select(listener, readers, writers, delay)
            delay = 25
            if json_bool(events["accept"]):
                for stream in tcp_accept_ready(listener, 4, 1000):
                    if len(peers) >= json_int(policy["max_peers"]):
                        tcp_close(stream)
                    else:
                        sequence = sequence + 1
                        key: str = str(sequence)
                        peers[key] = stream
                        tcp_send_buffer(stream, 4096)
                        incoming[key] = b""
                        outgoing[key] = b""
                        activity[key] = monotonic()
                        started[key] = monotonic()
                        closing[key] = False
                        ended[key] = False
            for event in json_array(events["read"]):
                key: str = read_keys[json_int(event)]
                try:
                    part: tuple[bytes, bool] = tcp_recv_ready(peers[key], 4096)
                    if part[1]:
                        ended[key] = True
                    if len(part[0]) > 0:
                        if len(incoming[key]) == 0:
                            started[key] = monotonic()
                        incoming[key] = incoming[key] + part[0]
                        activity[key] = monotonic()
                    assert len(incoming[key]) <= 131072, "input queue exceeds limit"
                except Exception:  # noqa: BLE001 - isolate failed reads to this peer
                    closing[key] = True
                    incoming[key] = b""
                    outgoing[key] = outgoing[key] + error("connection failed")
                    if len(outgoing[key]) > 131072:
                        outgoing[key] = b""
            for key in keys:
                for index in range(4):
                    if len(incoming[key]) == 0 or closing[key]:
                        break
                    complete: bool = False
                    try:
                        frame: tuple[Json, int, int] = parse(incoming[key], 0, 0, 128)
                        assert not (json_is_null(frame[0]) and ended[key]), "truncated frame"
                        if not json_is_null(frame[0]):
                            complete = True
                            incoming[key] = incoming[key][frame[1] :]
                            started[key] = monotonic()
                            outgoing[key] = outgoing[key] + execute(frame[0], policy)
                            assert len(outgoing[key]) <= 131072, "output queue exceeds limit"
                    except Exception:  # noqa: BLE001 - malformed frames and storage failures close this peer
                        closing[key] = True
                        incoming[key] = b""
                        outgoing[key] = outgoing[key] + error("protocol or storage failure")
                        if len(outgoing[key]) > 131072:
                            outgoing[key] = b""
                    if not complete:
                        break
                    delay = 0
                try:
                    if len(outgoing[key]) > 0:
                        sent: int = tcp_send_ready(peers[key], outgoing[key][:16384])
                        outgoing[key] = outgoing[key][sent:]
                        if sent > 0:
                            activity[key] = monotonic()
                            if len(outgoing[key]) == 0:
                                fault("after_reply")
                except Exception:  # noqa: BLE001 - a failed write cannot be retried safely
                    closing[key] = True
                    outgoing[key] = b""
                elapsed: float = (monotonic() - activity[key]) * 1000.0
                partial: float = (monotonic() - started[key]) * 1000.0
                expired: bool = elapsed >= json_float(policy["idle_ms"])
                if len(incoming[key]) > 0 and partial >= json_float(policy["frame_ms"]):
                    expired = True
                finished: bool = closing[key] or (ended[key] and len(incoming[key]) == 0)
                if expired or (finished and len(outgoing[key]) == 0):
                    tcp_close(peers[key])
                    del peers[key]
                    del incoming[key]
                    del outgoing[key]
                    del activity[key]
                    del started[key]
                    del closing[key]
                    del ended[key]
        for key in peers:  # noqa: PLC0206 - typed dictionary key iteration is supported
            tcp_close(peers[key])
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
