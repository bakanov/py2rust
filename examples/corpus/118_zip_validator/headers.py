"""Central-directory fields and matching local records, including ZIP32 data descriptors."""

from dataclasses import dataclass

from binary import number


@dataclass
class Entry:
    offset: int
    flags: int
    method: int
    crc: int
    compressed: int
    expanded: int
    name: bytes
    extra: bytes
    version: int
    made: int
    attributes: int
    disk: int


def ending(data: bytes) -> tuple[int, int, int, list[str]]:
    position: int = -1
    for offset in range(len(data) - 22, max(-1, len(data) - 65558), -1):
        if data[offset : offset + 4] == b"PK\x05\x06" and offset + 22 + number(data, offset + 20, 2) == len(data):
            position = offset
            break
    assert position >= 0, "end record missing"
    count: int = number(data, position + 10, 2)
    size: int = number(data, position + 12, 4)
    start: int = number(data, position + 16, 4)
    codes: list[str] = []
    if (
        number(data, position + 4, 2) != 0
        or number(data, position + 6, 2) != 0
        or number(data, position + 8, 2) != count
    ):
        codes.append("multi_disk")
    if (
        count == 65535
        or size == 4294967295
        or start == 4294967295
        or data[max(0, position - 20) : position - 16] == b"PK\x06\x07"
    ):
        codes.append("zip64")
    if len(codes) == 0:
        assert start <= position and size == position - start, "central directory bounds"
    return (position, start, count, codes)


def central(data: bytes, cursor: int, end: int) -> tuple[Entry, int]:
    assert cursor + 46 <= end and data[cursor : cursor + 4] == b"PK\x01\x02", "central header"
    names: int = number(data, cursor + 28, 2)
    extras: int = number(data, cursor + 30, 2)
    stop: int = cursor + 46 + names + extras + number(data, cursor + 32, 2)
    assert stop <= end, "central variable fields"
    entry: Entry = Entry(
        number(data, cursor + 42, 4),
        number(data, cursor + 8, 2),
        number(data, cursor + 10, 2),
        number(data, cursor + 16, 4),
        number(data, cursor + 20, 4),
        number(data, cursor + 24, 4),
        data[cursor + 46 : cursor + 46 + names],
        data[cursor + 46 + names : cursor + 46 + names + extras],
        number(data, cursor + 6, 2),
        number(data, cursor + 4, 2),
        number(data, cursor + 38, 4),
        number(data, cursor + 34, 2),
    )
    return (entry, stop)


def local(data: bytes, entry: Entry, end: int) -> tuple[int, int, bytes, list[str]]:
    start: int = entry.offset
    assert start + 30 <= end and data[start : start + 4] == b"PK\x03\x04", "local header"
    names: int = number(data, start + 26, 2)
    extras: int = number(data, start + 28, 2)
    payload: int = start + 30 + names + extras
    stop: int = payload + entry.compressed
    assert stop <= end, "local data bounds"
    codes: list[str] = []
    if data[start + 30 : start + 30 + names] != entry.name:
        codes.append("local_name")
    if (
        number(data, start + 4, 2) != entry.version
        or number(data, start + 6, 2) != entry.flags
        or number(data, start + 8, 2) != entry.method
    ):
        codes.append("local_fields")
    actual: list[int] = [number(data, start + 14, 4), number(data, start + 18, 4), number(data, start + 22, 4)]
    expected: list[int] = [entry.crc, entry.compressed, entry.expanded]
    if entry.flags & 8 != 0:
        if actual != [0, 0, 0] and actual != expected:
            codes.append("local_sizes")
        assert stop + 12 <= end, "data descriptor bounds"
        signed: bool = (
            data[stop : stop + 4] == b"PK\x07\x08"
            and [number(data, stop, 4), number(data, stop + 4, 4), number(data, stop + 8, 4)] != expected
        )
        descriptor: int = stop + (4 if signed else 0)
        assert descriptor + 12 <= end, "data descriptor bounds"
        if [number(data, descriptor, 4), number(data, descriptor + 4, 4), number(data, descriptor + 8, 4)] != expected:
            codes.append("descriptor")
        stop = descriptor + 12
    elif actual != expected:
        codes.append("local_sizes")
    return (payload, stop, data[start + 30 + names : payload], codes)
