"""Walk RIFF chunks and read mono signed16 PCM; write canonical PCM without ancillary chunks."""

from dataclasses import dataclass

from binary import digest, signed16, unsigned

from py2rust.stdlib import Json


@dataclass
class Wave:
    rate: int
    samples: list[int]
    chunks: list[Json]


def decode(source: bytes) -> Wave:
    assert len(source) >= 12 and source[:4] == b"RIFF" and source[8:12] == b"WAVE", "expected RIFF/WAVE"
    assert unsigned(source[4:8]) == len(source) - 8, "RIFF length differs from file size"
    cursor: int = 12
    chunks: list[Json] = []
    found: list[bytes] = []
    format_data: bytes = b""
    audio: bytes = b""
    while cursor < len(source):
        assert len(chunks) < 1024, "chunk count limit"
        assert len(source) - cursor >= 8, "truncated chunk header"
        name: bytes = source[cursor : cursor + 4]
        size: int = unsigned(source[cursor + 4 : cursor + 8])
        end: int = cursor + 8 + size
        assert end + size % 2 <= len(source), "truncated chunk or padding"
        payload: bytes = source[cursor + 8 : end]
        if name in [b"fmt ", b"data"]:
            assert name not in found, "duplicate format or data chunk"
            found.append(name)
            if name == b"fmt ":
                format_data = payload
            else:
                audio = payload
        chunks.append(
            {
                "id_hex": name.hex(),
                "offset": cursor,
                "bytes": size,
                "padding_bytes": size % 2,
                "sha256": digest(payload),
            }
        )
        cursor = end + size % 2
    assert b"fmt " in found and b"data" in found, "format and data chunks required"
    assert len(format_data) in [16, 18], "format chunk must contain 16 or 18 bytes"
    assert unsigned(format_data[:2]) == 1, "only integer PCM is supported"
    assert unsigned(format_data[2:4]) == 1 and unsigned(format_data[14:16]) == 16, "only mono signed16 PCM is supported"
    rate: int = unsigned(format_data[4:8])
    assert 1 <= rate <= 384000, "sample rate range"
    assert (
        unsigned(format_data[8:12]) == rate * 2 and unsigned(format_data[12:14]) == 2
    ), "inconsistent byte rate or alignment"
    assert len(audio) % 2 == 0 and len(audio) // 2 <= 262144, "sample alignment or count limit"
    samples: list[int] = []
    for offset in range(0, len(audio), 2):
        samples.append(signed16(audio[offset : offset + 2]))
    return Wave(rate, samples, chunks)


def encode(rate: int, samples: list[int]) -> bytes:
    audio: bytearray = bytearray()
    for value in samples:
        unsigned_value: int = value + 65536 if value < 0 else value
        audio.extend(unsigned_value.to_bytes(2, "little"))
    format_data: bytes = b"\x01\x00\x01\x00" + rate.to_bytes(4, "little")
    format_data = format_data + (rate * 2).to_bytes(4, "little") + b"\x02\x00\x10\x00"
    body: bytes = b"WAVEfmt " + (16).to_bytes(4, "little") + format_data
    body = body + b"data" + len(audio).to_bytes(4, "little") + bytes(audio)
    return b"RIFF" + len(body).to_bytes(4, "little") + body
