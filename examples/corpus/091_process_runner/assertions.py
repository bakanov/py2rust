"""Output expectations operate on captured bytes, with explicit UTF-8 regex matching."""

# ruff: noqa: BLE001 - output decoding can fail for valid binary captures
from py2rust.stdlib import Json, base64_decode, json_string, regex_fullmatch


def matches(data: bytes, expected: Json) -> bool:
    mode: str = json_string(expected["mode"])
    value: str = json_string(expected["value"])
    if mode == "ignore":
        return True
    if mode == "utf8":
        return data == value.encode()
    if mode == "base64":
        return data == base64_decode(value)
    if mode == "contains":
        return value.encode() in data
    try:
        return regex_fullmatch(value, data.decode())
    except Exception:
        return False


def preview(data: bytes) -> Json:
    try:
        return data.decode()[:512]
    except Exception:
        return None
