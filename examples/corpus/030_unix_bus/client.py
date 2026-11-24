"""A batch client checks request/reply IDs and writes its report atomically."""

from wire import encode, exact

from py2rust.stdlib import (
    Json,
    env_get,
    int_from_bytes,
    json_array,
    json_bool,
    json_keys,
    json_loads,
    json_string,
    pretty,
    read_text,
    unix_connect,
    unix_sendall,
    unix_set_deadline,
    write_text_atomic,
)


def batch(policy: dict[str, int]) -> bool:
    text: str = read_text(env_get("BUS_REQUESTS", "requests.json"))
    assert len(text.encode()) <= 1048576, "batch exceeds 1 MiB"
    requests: list[Json] = json_array(json_loads(text))
    assert len(requests) > 0 and len(requests) <= 1000, "batch requires 1..1000 requests"
    identifiers: set[str] = set()
    for request in requests:
        assert json_keys(request) == ["args", "id", "op"], "invalid batch envelope"
        identifier: str = json_string(request["id"])
        assert identifier not in identifiers, "batch IDs must be unique"
        identifiers.add(identifier)
        assert len(encode(request)) <= policy["frame_bytes"] + 4, "request frame too large"
    responses: list[Json] = []
    success: bool = True
    with unix_connect(env_get("BUS_SOCKET", "command.sock"), policy["partial_ms"]) as stream:
        for request in requests:
            unix_set_deadline(stream, policy["partial_ms"])
            unix_sendall(stream, encode(request))
            size: int = int_from_bytes(exact(stream, 4), "big")
            assert size > 0 and size <= policy["frame_bytes"], "invalid reply length"
            reply: Json = json_loads(exact(stream, size).decode())
            assert json_string(reply["id"]) == json_string(request["id"]), "reply ID mismatch"
            if json_bool(reply["ok"]):
                assert json_keys(reply) == ["id", "ok", "result"], "invalid successful reply"
            else:
                assert json_keys(reply) == ["error", "id", "ok"], "invalid error reply"
                assert json_keys(reply["error"]) == ["code", "message"], "invalid error fields"
                assert len(json_string(reply["error"]["code"])) > 0, "missing error code"
                json_string(reply["error"]["message"])
                success = False
            responses.append(reply)
    report: Json = {"ok": success, "responses": responses}
    write_text_atomic(env_get("BUS_REPORT", "report.json"), pretty(report))
    print(pretty(report))
    return success
