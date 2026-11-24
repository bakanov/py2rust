"""Bounded WebSocket frames, masks and close payloads."""

from dataclasses import dataclass

from py2rust.stdlib import bytes_xor, int_from_bytes, int_to_bytes


@dataclass
class Frame:
    consumed: int = 0
    opcode: int = 0
    finished: bool = False
    payload: bytes = b""
    close_code: int = 0


def encode(opcode: int, payload: bytes) -> bytes:
    size: int = len(payload)
    header: bytes = int_to_bytes(128 | opcode, 1, "big")
    if size < 126:
        header = header + int_to_bytes(size, 1, "big")
    elif size <= 65535:
        header = header + b"\x7e" + int_to_bytes(size, 2, "big")
    else:
        header = header + b"\x7f" + int_to_bytes(size, 8, "big")
    return header + payload


def decode(data: bytes, limit: int) -> Frame:
    if len(data) < 2:
        return Frame()
    opcode: int = data[0] & 15
    finished: bool = data[0] & 128 != 0
    if data[0] & 112 != 0 or data[1] & 128 == 0 or opcode not in [0, 1, 2, 8, 9, 10]:
        return Frame(close_code=1002)
    size: int = data[1] & 127
    header: int = 2
    if size == 126:
        if len(data) < 4:
            return Frame()
        size = int_from_bytes(data[2:4], "big")
        header = 4
        if size < 126:
            return Frame(close_code=1002)
    elif size == 127:
        if len(data) < 10:
            return Frame()
        if data[2] & 128 != 0:
            return Frame(close_code=1002)
        size = int_from_bytes(data[2:10], "big")
        header = 10
        if size <= 65535:
            return Frame(close_code=1002)
    if opcode >= 8 and (not finished or size > 125):
        return Frame(close_code=1002)
    if opcode < 8 and size > limit:
        return Frame(close_code=1009)
    if opcode == 2:
        return Frame(close_code=1003)
    if len(data) < header + 4 + size:
        return Frame()
    payload: bytes = bytes_xor(data[header + 4 : header + 4 + size], data[header : header + 4])
    return Frame(header + 4 + size, opcode, finished, payload)


def close_error(payload: bytes) -> int:
    if len(payload) == 0:
        return 0
    if len(payload) == 1:
        return 1002
    code: int = int_from_bytes(payload[:2], "big")
    if not ((code >= 1000 and code <= 1014 and code not in [1004, 1005, 1006]) or (code >= 3000 and code <= 4999)):
        return 1002
    try:
        payload[2:].decode()
    except Exception:  # noqa: BLE001 - invalid UTF-8 is a protocol error
        return 1007
    return 0
