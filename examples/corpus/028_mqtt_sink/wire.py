"""Bounded MQTT 3.1.1 packet lengths and UTF-8 fields."""

from dataclasses import dataclass

from py2rust.stdlib import int_from_bytes


@dataclass
class Packet:
    consumed: int = 0
    kind: int = 0
    retained: bool = False
    body: bytes = b""


def decode(data: bytes, limit: int) -> Packet:
    if len(data) < 2:
        return Packet()
    assert data[0] in [16, 48, 49, 192, 224], "unsupported packet type, flags or QoS"
    size: int = 0
    multiplier: int = 1
    header: int = 0
    for index in range(1, 5):
        if len(data) <= index:
            return Packet()
        digit: int = data[index]
        size = size + (digit & 127) * multiplier
        assert size <= limit, "packet exceeds limit"
        if digit & 128 == 0:
            assert index == 1 or digit != 0, "nonminimal remaining length"
            header = index + 1
            break
        assert index < 4, "remaining length exceeds four bytes"
        multiplier = multiplier * 128
    if len(data) < header + size:
        return Packet()
    return Packet(header + size, data[0] >> 4, data[0] & 1 != 0, data[header : header + size])


def field(data: bytes, offset: int) -> tuple[bytes, int]:
    assert offset + 2 <= len(data), "missing field length"
    end: int = offset + 2 + int_from_bytes(data[offset : offset + 2], "big")
    assert end <= len(data), "truncated field"
    return (data[offset + 2 : end], end)


def text(data: bytes) -> str:
    value: str = data.decode()
    assert "\x00" not in value, "NUL in MQTT text"
    return value


def topic_name(data: bytes, limit: int) -> str:
    assert len(data) > 0 and len(data) <= limit, "invalid topic size"
    topic: str = text(data)
    assert "+" not in topic and "#" not in topic, "wildcard in topic name"
    return topic
