"""Five binary-safe commands with exact integer and expiration rules."""

from codec import arguments, bulk, error, integer
from storage import load, refresh, save, total

from py2rust.stdlib import (
    Json,
    int_from_decimal,
    json_get,
    json_int,
    json_keys,
    json_string,
    regex_fullmatch,
)


def dispatch(args: list[bytes], state: Json, policy: Json) -> tuple[Json, bytes]:
    command: str = args[0].decode().upper()
    if command == "PING":
        if len(args) == 1:
            return (state, b"+PONG\r\n")
        assert len(args) == 2, "PING requires zero or one argument"
        return (state, bulk(args[1]))
    assert command in ["GET", "SET", "DEL", "INCR"], "unknown command"
    assert len(args) >= 2, "key required"
    for index in range(1, len(args)):
        if index == 1 or command == "DEL":
            assert len(args[index]) <= json_int(policy["max_key"]), "key exceeds limit"
    key: str = args[1].hex()
    entries: Json = state["entries"]
    if command == "GET":
        assert len(args) == 2, "GET requires one key"
        if key not in entries:
            return (state, b"$-1\r\n")
        return (state, bulk(bytes.fromhex(json_string(entries[key]["value"]))))
    if command == "DEL":
        removed: int = 0
        for index in range(1, len(args)):
            name: str = args[index].hex()
            if name in entries:
                del entries[name]
                removed = removed + 1
        state["entries"] = entries
        return (state, integer(removed))
    previous: Json = json_get(entries, key, {"value": "30", "expires": 0})
    value: bytes = b""
    expires: int = 0
    response: bytes = b"+OK\r\n"
    if command == "INCR":
        assert len(args) == 2, "INCR requires one key"
        text: str = bytes.fromhex(json_string(previous["value"])).decode()
        number: int = int_from_decimal(text)
        assert str(number) == text and number < 9223372036854775807, "value is not an incrementable integer"
        number = number + 1
        value = str(number).encode()
        expires = json_int(previous["expires"])
        response = integer(number)
    else:
        assert len(args) == 3 or len(args) == 5, "SET requires key value and optional EX/PX duration"
        value = args[2]
        if len(args) == 5:
            unit: str = args[3].decode().upper()
            assert unit in ["EX", "PX"], "unsupported SET option"
            duration: str = args[4].decode()
            assert regex_fullmatch("[1-9][0-9]{0,9}", duration), "invalid expiration duration"
            ttl: int = int_from_decimal(duration)
            if unit == "EX":
                ttl = ttl * 1000
            assert ttl <= 2592000000, "expiration exceeds 30 days"
            expires = json_int(state["clock_ms"]) + ttl
            assert expires <= 253402214400000, "expiration outside clock range"
    assert len(value) <= json_int(policy["max_value"]), "value exceeds limit"
    size: int = total(entries) + len(args[1]) + len(value)
    if key in entries:
        size = size - len(args[1]) - len(bytes.fromhex(json_string(previous["value"])))
    else:
        assert len(json_keys(entries)) < json_int(policy["max_keys"]), "key capacity exhausted"
    assert size <= json_int(policy["max_total"]), "byte capacity exhausted"
    entries[key] = {"value": value.hex(), "expires": expires}
    state["entries"] = entries
    return (state, response)


def execute(frame: Json, policy: Json) -> bytes:
    response: bytes = error("invalid command or arguments")
    state: Json = refresh(load(policy))
    try:
        result: tuple[Json, bytes] = dispatch(arguments(frame), state, policy)
        state = result[0]
        response = result[1]
    except Exception:  # noqa: BLE001 - command errors are recoverable within the connection
        response = error("invalid command or arguments")
    save(state)
    return response
