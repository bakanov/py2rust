"""Correlated commands and a bounded, shared receipt cache; all state is process-local."""

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_dumps,
    json_equal,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


def error(identifier: str, code: str, message: str) -> Json:
    return {"id": identifier, "ok": False, "error": {"code": code, "message": message}}


def execute(request: Json, state: Json, policy: dict[str, int]) -> tuple[Json, Json, bool]:
    identifier: str = ""
    try:
        identifier = json_string(request["id"])
        assert regex_fullmatch("[A-Za-z0-9_.:-]{1,64}", identifier), "invalid id"
    except Exception:  # noqa: BLE001 - convert supported-subset validation failures to protocol errors
        return (state, error("", "request", "id must be 1..64 ASCII identifier characters"), False)
    if json_keys(request) != ["args", "id", "op"] or json_kind(request["op"]) != "string":
        return (state, error(identifier, "request", "expected exactly id, op and args"), False)
    cache: Json = state["receipts"]
    if identifier in cache:
        receipt: Json = cache[identifier]
        if not json_equal(receipt["request"], request):
            return (state, error(identifier, "conflict", "id already belongs to another request"), False)
        return (state, receipt["reply"], False)
    values: Json = state["values"]
    operation: str = json_string(request["op"])
    args: Json = request["args"]
    result: Json = None
    response: Json = error(identifier, "command", "invalid arguments or unknown command")
    stopping: bool = False
    try:
        if operation == "echo":
            assert len(json_dumps(args).encode()) <= policy["value_bytes"], "echo too large"
            result = args
        elif operation == "sum":
            items: list[Json] = json_array(args)
            assert len(items) <= 128, "too many numbers"
            total: int = 0
            for item in items:
                number: int = json_int(item)
                assert number >= -1000000000000 and number <= 1000000000000, "number out of range"
                total = total + number
            result = total
        elif operation == "set":
            assert json_keys(args) == ["key", "value"], "invalid set fields"
            key: str = json_string(args["key"])
            assert regex_fullmatch("[A-Za-z0-9_.:-]{1,64}", key), "invalid key"
            value: str = json_string(args["value"])
            assert len(json_dumps(value).encode()) <= policy["value_bytes"], "value too large"
            assert key in values or len(json_keys(values)) < policy["keys"], "key capacity exhausted"
            values[key] = value
            result = {"key": key, "stored": True}
        elif operation == "get" or operation == "delete":
            key: str = json_string(args)
            assert key in values, "unknown key"
            result = values[key]
            if operation == "delete":
                del values[key]
        elif operation == "keys":
            assert json_kind(args) == "null", "keys takes null"
            result = json_keys(values)
        elif operation == "stats":
            assert json_kind(args) == "null", "stats takes null"
            result = {"keys": len(json_keys(values)), "receipts": len(json_keys(cache))}
        elif operation == "stop":
            assert policy["allow_stop"] == 1 and json_kind(args) == "null", "stop is disabled or invalid"
            result = "stopping"
            stopping = True
        else:
            assert False, "unknown command"
        response = {"id": identifier, "ok": True, "result": result}
        assert len(json_dumps(response).encode()) <= policy["frame_bytes"], "reply too large"
    except Exception:  # noqa: BLE001 - convert supported-subset validation failures to protocol errors
        response = error(identifier, "command", "invalid arguments, limit exceeded or unknown command")
        stopping = False
    if json_bool(response["ok"]):
        state["values"] = values
    order: list[Json] = json_array(state["order"])
    if len(order) >= policy["receipts"]:
        del cache[json_string(order[0])]
        order = order[1:]
    order.append(identifier)
    cache[identifier] = {"request": request, "reply": response}
    state["order"] = order
    state["receipts"] = cache
    return (state, response, stopping)
