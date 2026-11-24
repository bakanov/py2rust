"""Versioned binary Huffman containers with bounded decoding and two SHA-256 checks."""

from dataclasses import dataclass

from codebook import canonical, lengths

from py2rust.stdlib import sha256_digest, sha256_new, sha256_update


@dataclass
class Block:
    original_size: int
    bit_count: int
    codes: dict[int, tuple[int, int]]
    original_digest: bytes
    payload: bytes


def digest(data: bytes) -> bytes:
    return bytes.fromhex(sha256_digest(sha256_update(sha256_new(), data)))


def encode(data: bytes) -> bytes:
    assert len(data) <= 1048576, "original data exceeds 1 MiB"
    codes: dict[int, tuple[int, int]] = canonical(lengths(data))
    payload: bytearray = bytearray()
    accumulator: int = 0
    held: int = 0
    total: int = 0
    for symbol in data:
        entry: tuple[int, int] = codes[symbol]
        accumulator = (accumulator << entry[1]) | entry[0]
        held = held + entry[1]
        total = total + entry[1]
        while held >= 8:
            held = held - 8
            payload.append((accumulator >> held) & 255)
        accumulator = accumulator & ((1 << held) - 1)
    if held > 0:
        payload.append(accumulator << (8 - held))
    table: bytearray = bytearray()
    for symbol in range(256):
        if symbol in codes:
            table.append(symbol)
            table.append(codes[symbol][1])
    header: bytes = b"PYHF068!" + len(data).to_bytes(4, "big") + total.to_bytes(4, "big")
    header = header + len(codes).to_bytes(2, "big") + digest(data) + bytes(table)
    container: bytes = header + bytes(payload)
    return container + digest(container)


def parse(raw: bytes) -> Block:
    assert 82 <= len(raw) <= 4194898, "invalid container size"
    assert raw[:8] == b"PYHF068!", "invalid container magic"
    original: int = int.from_bytes(raw[8:12], "big")
    bits: int = int.from_bytes(raw[12:16], "big")
    count: int = int.from_bytes(raw[16:18], "big")
    assert original <= 1048576, "declared output exceeds 1 MiB"
    assert count <= 256 and count <= original, "invalid symbol count"
    assert original <= bits <= original * 32, "invalid payload bit count"
    offset: int = 50 + 2 * count
    assert len(raw) == offset + (bits + 7) // 8 + 32, "container length mismatch"
    assert digest(raw[:-32]) == raw[-32:], "container checksum mismatch"
    widths: dict[int, int] = {}
    previous: int = -1
    for position in range(count):
        symbol: int = raw[50 + 2 * position]
        assert symbol > previous, "codebook symbols must be strictly increasing"
        previous = symbol
        widths[symbol] = raw[51 + 2 * position]
    codes: dict[int, tuple[int, int]] = canonical(widths)
    assert (original == 0 and count == 0) or (original > 0 and count > 0), "missing codebook"
    payload: bytes = raw[offset:-32]
    if bits % 8 != 0:
        assert (payload[-1] & ((1 << (8 - bits % 8)) - 1)) == 0, "nonzero padding bits"
    return Block(original, bits, codes, raw[18:50], payload)


def decode(block: Block) -> bytes:
    reverse: dict[tuple[int, int], int] = {}
    maximum: int = 0
    for symbol in block.codes:
        reverse[block.codes[symbol]] = symbol
        maximum = max(maximum, block.codes[symbol][1])
    output: bytearray = bytearray()
    used: set[int] = set()
    code: int = 0
    width: int = 0
    for position in range(block.bit_count):
        code = (code << 1) | ((block.payload[position // 8] >> (7 - position % 8)) & 1)
        width = width + 1
        ticket: tuple[int, int] = (code, width)
        if ticket in reverse:
            symbol: int = reverse[ticket]
            output.append(symbol)
            used.add(symbol)
            assert len(output) <= block.original_size, "decoded output exceeds declared length"
            code = 0
            width = 0
        else:
            assert width < maximum, "invalid payload code"
    assert width == 0, "unfinished payload code"
    assert len(output) == block.original_size, "decoded length mismatch"
    assert len(used) == len(block.codes), "unused codebook symbol"
    result: bytes = bytes(output)
    assert digest(result) == block.original_digest, "decoded checksum mismatch"
    return result
