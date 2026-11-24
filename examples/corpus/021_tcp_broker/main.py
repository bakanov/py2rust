"""A serial, persistent task broker with bounded per-frame I/O and graceful stop polling."""

from broker import dispatch, failure
from client import exchange
from config import configuration, shutdown_requested
from protocol import receive, send
from storage import fault, load

from py2rust.stdlib import (
    Json,
    TcpStream,
    env_get,
    json_int,
    json_loads,
    log,
    log_configure,
    tcp_accept_timeout,
    tcp_listen,
    tcp_port,
)


def connection(stream: TcpStream, policy: Json) -> None:
    limit: int = json_int(policy["max_frame"])
    timeout: int = json_int(policy["frame_timeout_ms"])
    for index in range(json_int(policy["connection_frames"])):
        if shutdown_requested():
            return
        body: bytes = b""
        try:
            body = receive(stream, limit, timeout)
        except Exception:  # noqa: BLE001 - recoverable subset boundary isolates failed requests
            send(stream, failure("frame_error"), limit, timeout)
            return
        if len(body) == 0:
            return
        request: Json = None
        try:
            request = json_loads(body.decode())
        except Exception:  # noqa: BLE001 - recoverable subset boundary isolates failed requests
            send(stream, failure("invalid_json"), limit, timeout)
            continue
        reply: Json = None
        try:
            reply = dispatch(request, policy)
        except Exception:  # noqa: BLE001 - recoverable subset boundary isolates failed requests
            reply = failure("request_failed")
        send(stream, reply, limit, timeout)
        fault("after_reply")
    return


def main() -> None:
    policy: Json = configuration()
    port: int = json_int(json_loads(env_get("BROKER_PORT", "8787")))
    assert port >= 0 and port <= 65535, "invalid listen port"
    mode: str = env_get("BROKER_MODE", "serve")
    assert mode in ["serve", "client"], "invalid broker mode"
    if mode == "client":
        exchange(policy, port)
        return
    load(policy)
    log_configure(30)
    with tcp_listen("127.0.0.1", port) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while not shutdown_requested():
            try:
                with tcp_accept_timeout(listener, 100, json_int(policy["frame_timeout_ms"])) as stream:
                    connection(stream, policy)
            except Exception:  # noqa: BLE001 - recoverable subset boundary isolates failed requests
                log(10, "connection closed or accept deadline elapsed")
    return


if __name__ == "__main__":
    main()
