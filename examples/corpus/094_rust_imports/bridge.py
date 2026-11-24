"""Ordinary imports resolve directly to adjacent Rust files during project compilation."""

# ruff: noqa: I001, BLE001 - compact imports and deliberate native error boundary
from native_numbers import checked_add, double_width, invert, narrow, unsigned_result
from native_text import accept, inspect, transform, unit
from native_values import document, nested, roundtrip, special
from reference import value
from py2rust.stdlib import Json, base64_decode, base64_encode, json_bool, json_int, json_string


def invoke(operation: str, args: Json) -> Json:
    if operation == "narrow":
        return value(narrow(json_int(args["value"])))
    if operation == "unsigned":
        return value(unsigned_result(json_int(args["value"])))
    if operation == "double":
        return value(double_width(json_int(args["value"])))
    if operation == "add":
        return value(checked_add(json_int(args["left"]), json_int(args["right"])))
    if operation == "invert":
        return value(invert(json_bool(args["value"])))
    if operation == "unicode":
        text_info: tuple[int, int, str] = inspect(json_string(args["text"]))
        return value([text_info[0], text_info[1], text_info[2]])
    if operation == "bytes":
        binary_info: tuple[bytes, int] = transform(base64_decode(json_string(args["data"])))
        return value([base64_encode(binary_info[0]), binary_info[1]])
    if operation == "accept":
        return value(accept(json_string(args["text"])))
    if operation == "unit":
        unit(json_string(args["text"]))
        return value(None)
    if operation == "float":
        return value(special(json_string(args["mode"])))
    if operation == "nested":
        values: tuple[list[float], tuple[float, str]] = nested(json_string(args["mode"]))
        return value([values[0], [values[1][0], values[1][1]]])
    if operation == "json":
        return value(document(json_string(args["mode"])))
    return value(roundtrip(args["value"]))


def observed(operation: str, args: Json) -> Json:
    try:
        return invoke(operation, args)
    except Exception as failure:
        message: str = str(failure)
        code: str = "unexpected"
        if message == "out of range integral type conversion attempted":
            code = "integer_range"
        elif message == "native integer overflow":
            code = "overflow"
        elif message == "non-finite floating point result":
            code = "nonfinite"
        elif message == "JSON integers must fit signed 64 bits":
            code = "json_range"
        elif message == "native rejected text":
            code = "rejected"
        return {"kind": "error", "code": code, "message": message}
