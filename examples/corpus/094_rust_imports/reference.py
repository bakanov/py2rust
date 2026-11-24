"""Expected semantics, implemented in Python without calling the native adapters."""

# ruff: noqa: I001 - compact runtime imports
from py2rust.stdlib import Json, base64_decode, base64_encode, int_to_bytes, json_bool, json_int, json_string


def value(result: Json) -> Json:
    return {"kind": "value", "value": result}


def error(code: str) -> Json:
    return {"kind": "error", "code": code}


def expected(operation: str, args: Json) -> Json:
    maximum: int = 9223372036854775807
    minimum: int = -9223372036854775808
    if operation in ["narrow", "unsigned", "double"]:
        number: int = json_int(args["value"])
        if operation == "narrow" and not 0 <= number <= 255:
            return error("integer_range")
        if operation == "unsigned" and number < 0:
            return error("integer_range")
        if operation == "double":
            if number > maximum // 2 or number < minimum // 2:
                return error("integer_range")
            number = number * 2
        return value(number)
    if operation == "add":
        left: int = json_int(args["left"])
        right: int = json_int(args["right"])
        if (right > 0 and left > maximum - right) or (right < 0 and left < minimum - right):
            return error("overflow")
        return value(left + right)
    if operation == "invert":
        return value(not json_bool(args["value"]))
    if operation == "unicode":
        text: str = json_string(args["text"])
        reversed_text: str = ""
        for character in text:
            reversed_text = character + reversed_text
        return value([len(text), len(text.encode()), reversed_text])
    if operation == "bytes":
        data: bytes = base64_decode(json_string(args["data"]))
        result: bytes = b""
        for index in range(len(data) - 1, -1, -1):
            result = result + int_to_bytes(data[index] ^ 165, 1, "big")
        return value([base64_encode(result), len(data)])
    if operation == "accept":
        text: str = json_string(args["text"])
        if text == "deny":
            return error("rejected")
        return value("accepted:" + text)
    if operation == "unit":
        return value(None)
    if operation in ["float", "nested"]:
        if json_string(args["mode"]) != "finite":
            return error("nonfinite")
        if operation == "float":
            return value(1.25)
        return value([[1.25, -0.0], [2.5, "ok"]])
    if operation == "json":
        if json_string(args["mode"]) == "wide":
            return error("json_range")
        return value({"items": [1, True, None, {"text": "世界"}]})
    return value(args["value"])
