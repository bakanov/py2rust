"""A bounded local SMTP capture server; no relaying or external mail delivery."""

from config import configuration, stopping
from session import serve
from storage import load
from wire import reply

from py2rust.stdlib import (
    Json,
    env_get,
    json_bool,
    json_int,
    json_loads,
    log,
    tcp_accept_ready,
    tcp_listen,
    tcp_port,
    tcp_select,
)


def main() -> None:
    policy: Json = configuration()
    load(policy, True)
    port: int = json_int(json_loads(env_get("SMTP_PORT", "2525")))
    with tcp_listen("127.0.0.1", port) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while not stopping():
            events: Json = tcp_select(listener, [], [], 50)
            if json_bool(events["accept"]):
                for accepted in tcp_accept_ready(listener, 1, 1000):
                    with accepted as stream:
                        try:
                            serve(stream, policy)
                        except Exception as error:  # noqa: BLE001 - isolate failures to this connection
                            log(30, str(error))
                            try:
                                reply(stream, "421 Session aborted", policy)
                            except Exception:  # noqa: BLE001 - a disconnected peer cannot receive the error
                                log(20, "Peer closed before error reply")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
