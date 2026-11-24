"""Independent struct/zlib PNG fixtures and byte-level report oracles; no application imports."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from html.parser import HTMLParser
from typing import Any

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def chunk(name: bytes, payload: bytes = b"") -> bytes:
    assert len(name) == 4
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", zlib.crc32(name + payload))


def header(width: int = 3, height: int = 2, depth: int = 8, color: int = 3, interlace: int = 0) -> bytes:
    return struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, interlace)


def image(parts: list[tuple[bytes, bytes]]) -> bytes:
    return SIGNATURE + b"".join(chunk(name, payload) for name, payload in parts)


def minimal() -> list[tuple[bytes, bytes]]:
    return [(b"IHDR", header(1, 1, 8, 0)), (b"IDAT", zlib.compress(b"\0\x80")), (b"IEND", b"")]


def rich_parts() -> list[tuple[bytes, bytes]]:
    compressed = zlib.compress(b"\0\0\1\0\0\1\0\1")
    return [
        (b"IHDR", header()),
        (b"gAMA", struct.pack(">I", 45455)),
        (b"sRGB", b"\0"),
        (b"PLTE", b"\xff\0\0\0\0\xff"),
        (b"tRNS", b"\xff\x80"),
        (b"pHYs", struct.pack(">IIB", 3780, 3780, 1)),
        (b"tEXt", b'Author\0Caf\xe9 <script> & "quoted"'),
        (b"iTXt", b"Title\0\0\x7fen\0" + "Заголовок\0Hello 😀 <img>&".encode()),
        (b"tIME", struct.pack(">HBBBBB", 2024, 2, 29, 23, 59, 60)),
        (b"IDAT", b""),
        (b"IDAT", compressed[:5]),
        (b"IDAT", compressed[5:]),
        (b"vpAg", b"opaque\x00\xff"),
        (b"IEND", b""),
    ]


def rich_metadata() -> dict[int, dict]:
    return {
        0: {"width": 3, "height": 2, "bit_depth": 8, "color_type": 3, "compression": 0, "filter": 0, "interlace": 0},
        1: {"gamma_times_100000": 45455},
        2: {"intent": 0},
        3: {"entries": 2},
        4: {"alpha": [255, 128]},
        5: {"x": 3780, "y": 3780, "unit": 1},
        6: {"keyword": "Author", "text": 'Café <script> & "quoted"'},
        7: {"keyword": "Title", "language": "en", "translated": "Заголовок", "text": "Hello 😀 <img>&"},
        8: {"year": 2024, "month": 2, "day": 29, "hour": 23, "minute": 59, "second": 60},
        9: {},
        10: {},
        11: {},
        12: {"decoded": False},
        13: {},
    }


def frames(raw: bytes) -> tuple[list[dict], int]:
    rows = []
    cursor = 8 if raw.startswith(SIGNATURE) else 0
    if not cursor:
        return rows, cursor
    while len(raw) - cursor >= 12:
        length, name = struct.unpack_from(">I4s", raw, cursor)
        end = cursor + 12 + length
        if length > 0x7FFFFFFF or end > len(raw):
            break
        body = raw[cursor + 8 : end - 4]
        (stored,) = struct.unpack_from(">I", raw, end - 4)
        actual = zlib.crc32(name + body)
        valid = all(65 <= c <= 90 or 97 <= c <= 122 for c in name)
        rows.append(
            {
                "index": len(rows),
                "offset": cursor,
                "length": length,
                "type": name.decode("ascii") if valid else "?",
                "type_hex": name.hex(),
                "type_valid": valid,
                "critical": not bool(name[0] & 32),
                "private": bool(name[1] & 32),
                "safe_to_copy": bool(name[3] & 32),
                "crc_stored": stored,
                "crc_computed": actual,
                "crc_ok": stored == actual,
                "data_sha256": digest(body),
            }
        )
        cursor = end
        if name == b"IEND":
            break
    return rows, cursor


def inspect_results(raw: bytes, results: dict) -> None:
    assert results.keys() == {"header", "chunks", "errors", "unchecked", "summary"}
    expected, scanned = frames(raw)
    assert len(results["chunks"]) == len(expected)
    for wanted, found in zip(expected, results["chunks"]):
        assert found.keys() == wanted.keys() | {"metadata"}
        assert canonical({k: found[k] for k in wanted}) == canonical(wanted), (wanted, found)
        assert type(found["metadata"]) is dict
    assert canonical(results["summary"]) == canonical(
        {
            "bytes": len(raw),
            "chunks": len(expected),
            "errors": len(results["errors"]),
            "crc_errors": sum(not row["crc_ok"] for row in expected),
            "idat_bytes": sum(row["length"] for row in expected if row["type"] == "IDAT"),
            "scanned_bytes": scanned,
            "unscanned_bytes": len(raw) - scanned,
        }
    )
    assert results["unchecked"][:2] == ["image_data_decompression", "pixel_values"]
    assert len(results["unchecked"]) == len(set(results["unchecked"]))
    for error in results["errors"]:
        assert error.keys() == {"offset", "code", "detail"}
        assert type(error["offset"]) is int and 0 <= error["offset"] <= len(raw)
        assert isinstance(error["code"], str) and isinstance(error["detail"], str)
    return  # noqa: PLR1711


class ReportHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.active = False
        self.rows = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        assert tag in {
            "html",
            "meta",
            "title",
            "style",
            "h1",
            "p",
            "h2",
            "pre",
            "table",
            "tr",
            "th",
            "td",
            "details",
            "summary",
        }, tag
        assert all(not key.startswith("on") and key not in {"src", "href"} for key, _ in attrs)
        if tag == "pre":
            self.active = True
            self.blocks.append("")
        if tag == "tr":
            self.rows += 1
        return  # noqa: PLR1711

    def handle_endtag(self, tag: str) -> None:
        if tag == "pre":
            self.active = False
        return  # noqa: PLR1711

    def handle_data(self, data: str) -> None:
        if self.active:
            self.blocks[-1] += data
        return  # noqa: PLR1711


def inspect_html(raw: bytes, results: dict) -> None:
    parsed = ReportHTML()
    parsed.feed(raw.decode())
    parsed.close()
    assert parsed.rows == len(results["chunks"]) + 1
    expected = [results[k] for k in ["summary", "header", "errors", "unchecked"]] + results["chunks"]
    assert canonical([json.loads(block) for block in parsed.blocks]) == canonical(expected)
    return  # noqa: PLR1711
