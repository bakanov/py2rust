"""Finite retry batches reject wrong-source, stale, malformed and truncated replies."""

from model import identifier

from py2rust.stdlib import (
    Json,
    UdpSocket,
    ceil,
    env_get,
    json_array,
    json_bool,
    json_dumps,
    json_float,
    json_get,
    json_int,
    json_loads,
    json_string,
    monotonic,
    pretty,
    process_exit,
    read_text,
    udp_bind,
    udp_recvfrom,
    udp_sendto,
    write_text_atomic,
)


def exchange(channel: UdpSocket, request: Json, port: int, policy: Json) -> Json:
    nonce: str = identifier(request["request"])
    payload: bytes = json_dumps(request).encode()
    assert len(payload) <= json_int(policy["max_datagram"]), "request exceeds datagram limit"
    for attempt in range(1, json_int(policy["attempts"]) + 1):
        deadline: float = monotonic() * 1000.0 + json_float(policy["reply_ms"])
        try:
            udp_sendto(channel, payload, "127.0.0.1", port, json_int(policy["reply_ms"]))
            for ignored in range(32):
                remaining: int = ceil(deadline - monotonic() * 1000.0)
                if remaining <= 0:
                    break
                packet: tuple[bytes, str, int, bool] = udp_recvfrom(
                    channel, json_int(policy["max_datagram"]), remaining
                )
                if packet[1] == "127.0.0.1" and packet[2] == port and not packet[3]:
                    try:
                        response: Json = json_loads(packet[0].decode())
                        if json_string(json_get(response, "request", "")) == nonce:
                            accepted: bool = json_bool(response["ok"])
                            return {"request": request, "reply": response, "attempts": attempt, "accepted": accepted}
                    except Exception:  # noqa: BLE001, S110 - discard malformed replies within the receive budget
                        pass
        except Exception:  # noqa: BLE001, S110 - transport failures consume one bounded retry attempt
            pass
    return {"request": request, "reply": None, "attempts": policy["attempts"], "accepted": False}


def run_client(policy: Json, port: int) -> None:
    assert port >= 1, "client needs a nonzero directory port"
    text: str = read_text(env_get("DIR_REQUESTS", "requests.json"))
    assert len(text.encode()) <= 1048576, "request batch exceeds 1 MiB"
    requests: list[Json] = json_array(json_loads(text))
    assert len(requests) >= 1 and len(requests) <= 100, "request batch needs 1..100 items"
    names: set[str] = set()
    for request in requests:
        nonce: str = identifier(request["request"])
        assert nonce not in names and len(json_dumps(request).encode()) <= json_int(
            policy["max_datagram"]
        ), "invalid batch"
        names.add(nonce)
    results: list[Json] = []
    failures: int = 0
    path: str = env_get("DIR_REPORT", "client-report.json")
    write_text_atomic(path, pretty({"complete": False, "results": results, "errors": failures}))
    with udp_bind("127.0.0.1", 0) as channel:
        for request in requests:
            result: Json = exchange(channel, request, port, policy)
            if not json_bool(result["accepted"]):
                failures = failures + 1
            results.append(result)
            write_text_atomic(path, pretty({"complete": False, "results": results, "errors": failures}))
    report: Json = {"complete": True, "results": results, "errors": failures}
    write_text_atomic(path, pretty(report))
    print(pretty(report))
    if failures > 0:
        process_exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
