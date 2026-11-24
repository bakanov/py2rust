"""One socket per lookup, correlated replies and finite identical-query retries."""

from packets import query, response

from py2rust.stdlib import (
    Json,
    ceil,
    int_from_bytes,
    json_float,
    json_int,
    json_string,
    monotonic,
    random_token,
    udp_bind,
    udp_recvfrom,
    udp_sendto,
)


def lookup(item: Json, policy: Json) -> Json:
    name: str = json_string(item["name"])
    kind: int = 1
    if json_string(item["type"]) == "AAAA":
        kind = 28
    identifier: int = int_from_bytes(bytes.fromhex(random_token()[:4]), "big")
    payload: bytes = query(identifier, name, kind)
    host: str = json_string(policy["host"])
    port: int = json_int(policy["port"])
    ignored: dict[str, int] = {"source": 0, "id": 0, "malformed": 0}
    last_error: str = "no matching reply"
    with udp_bind("0.0.0.0", 0) as channel:
        for attempt in range(1, json_int(policy["attempts"]) + 1):
            deadline: float = monotonic() * 1000.0 + json_float(policy["timeout_ms"])
            try:
                udp_sendto(channel, payload, host, port, json_int(policy["timeout_ms"]))
                for packet_count in range(64):
                    remaining: int = ceil(deadline - monotonic() * 1000.0)
                    if remaining <= 0:
                        break
                    packet: tuple[bytes, str, int, bool] = udp_recvfrom(channel, 512, remaining)
                    if packet[1] != host or packet[2] != port:
                        ignored["source"] = ignored["source"] + 1
                        continue
                    if len(packet[0]) < 2 or int_from_bytes(packet[0][:2], "big") != identifier:
                        ignored["id"] = ignored["id"] + 1
                        continue
                    try:
                        assert not packet[3], "received datagram exceeds 512 bytes"
                        reply: Json = response(packet[0], identifier, name, kind)
                        reply["id"] = identifier
                        reply["attempts"] = attempt
                        reply["ignored"] = ignored
                        return reply
                    except Exception as error:  # noqa: BLE001 - isolate malformed correlated DNS packets
                        ignored["malformed"] = ignored["malformed"] + 1
                        last_error = str(error)
            except Exception:  # noqa: BLE001, S110 - transport failures consume a bounded attempt
                pass
    return {
        "status": "no_response",
        "id": identifier,
        "attempts": policy["attempts"],
        "ignored": ignored,
        "error": last_error,
        "answers": [],
    }
