"""Unicast UDP discovery with expiry sweeping and a readable registry report."""

from config import clock_ms, stopping
from model import identifier, registry, sweep
from protocol import failure, handle

from py2rust.stdlib import (
    Json,
    env_get,
    json_dumps,
    json_int,
    json_loads,
    log,
    pretty,
    udp_bind,
    udp_port,
    udp_recvfrom,
    udp_sendto,
    write_text_atomic,
)


def publish(state: Json, previous: str) -> str:
    result: Json = registry(state)
    text: str = pretty(result)
    if text != previous:
        write_text_atomic(env_get("DIR_REGISTRY", "registry.json"), text)
        print("REGISTRY " + json_dumps(result))
    return text


def serve(policy: Json, port: int) -> None:
    state: Json = {"clock": clock_ms(), "entries": {}}
    previous: str = publish(state, "")
    with udp_bind("127.0.0.1", port) as channel:
        print("LISTENING udp://127.0.0.1:" + str(udp_port(channel)))
        while not stopping():
            state = sweep(state, clock_ms())
            previous = publish(state, previous)
            packet: tuple[bytes, str, int, bool] = (b"", "", 0, False)
            received: bool = False
            try:
                packet = udp_recvfrom(channel, json_int(policy["max_datagram"]), 50)
                received = True
            except Exception:  # noqa: BLE001 - receive timeouts allow expiry and stop-marker checks
                received = False
            if received:
                nonce: str = ""
                response: Json = failure(nonce, "invalid_datagram")
                try:
                    assert not packet[3], "truncated datagram"
                    request: Json = json_loads(packet[0].decode())
                    nonce = identifier(request["request"])
                    state = sweep(state, clock_ms())
                    result: tuple[Json, Json] = handle(request, packet[1], state, policy)
                    state = result[0]
                    response = result[1]
                except Exception:  # noqa: BLE001 - reject one malformed request without stopping the directory
                    response = failure(nonce, "invalid_request")
                previous = publish(state, previous)
                body: bytes = json_dumps(response).encode()
                assert len(body) <= json_int(policy["max_datagram"]), "reply exceeds datagram limit"
                try:
                    udp_sendto(channel, body, packet[1], packet[2], json_int(policy["reply_ms"]))
                except Exception:  # noqa: BLE001 - a failed datagram reply must not stop other peers
                    log(30, "Directory reply could not be sent")
    return  # noqa: PLR1711 - explicit return required by repository guidelines
