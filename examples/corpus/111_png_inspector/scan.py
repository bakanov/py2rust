"""Scan framed chunks without inflating image data; retain exact offsets and all recoverable findings."""

# ruff: noqa: BLE001 - per-chunk forensic diagnostics

import zlib

from binary import digest, unsigned
from metadata import describe

from py2rust.stdlib import Json, json_int, json_kind


def inspect(data: bytes) -> Json:
    chunks: list[Json] = []
    errors: list[Json] = []
    unchecked: list[str] = ["image_data_decompression", "pixel_values"]
    header: Json = None
    seen: list[str] = []
    palette: int = 0
    idat_bytes: int = 0
    idat_ended: bool = False
    metadata_bytes: int = 0
    crc_errors: int = 0
    cursor: int = 8
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append({"offset": 0, "code": "signature", "detail": "invalid PNG signature"})
        cursor = 0
    else:
        while cursor < len(data):
            assert len(chunks) < 4096, "chunk count limit"
            if len(data) - cursor < 8:
                errors.append({"offset": cursor, "code": "truncated_header", "detail": "incomplete length and type"})
                break
            size: int = unsigned(data[cursor : cursor + 4])
            if size > 2147483647 or size + 12 > len(data) - cursor:
                errors.append({"offset": cursor, "code": "chunk_length", "detail": "invalid or truncated chunk length"})
                break
            raw_type: bytes = data[cursor + 4 : cursor + 8]
            valid_type: bool = True
            for value in raw_type:
                if not (65 <= value <= 90 or 97 <= value <= 122):
                    valid_type = False
            name: str = raw_type.decode() if valid_type else "?"
            payload: bytes = data[cursor + 8 : cursor + 8 + size]
            stored: int = unsigned(data[cursor + 8 + size : cursor + 12 + size])
            computed: int = zlib.crc32(payload, zlib.crc32(raw_type))
            codes: list[str] = []
            if not valid_type or raw_type[2] & 32 != 0:
                codes.append("chunk_type")
            if stored != computed:
                codes.append("crc")
                crc_errors = crc_errors + 1
            if len(chunks) == 0 and name != "IHDR":
                codes.append("header_first")
            single: list[str] = [
                "IHDR",
                "PLTE",
                "IEND",
                "tRNS",
                "gAMA",
                "sRGB",
                "pHYs",
                "iCCP",
                "cHRM",
                "sBIT",
                "bKGD",
                "hIST",
                "eXIf",
                "tIME",
                "acTL",
                "cICP",
                "mDCV",
                "cLLI",
            ]
            if name in single and name in seen:
                codes.append("duplicate_chunk")
            before_palette: list[str] = ["gAMA", "sRGB", "iCCP", "cHRM", "sBIT", "cICP", "mDCV", "cLLI"]
            before_data: list[str] = before_palette + ["PLTE", "tRNS", "pHYs", "bKGD", "hIST", "sPLT", "eXIf", "acTL"]
            if (name in before_palette and "PLTE" in seen) or (name in before_data and "IDAT" in seen):
                codes.append("chunk_order")
            if name == "PLTE" and ("tRNS" in seen or "bKGD" in seen or "hIST" in seen):
                codes.append("palette_order")
            if name == "IDAT":
                if idat_ended:
                    codes.append("nonconsecutive_idat")
                if json_kind(header) == "object" and json_int(header["color_type"]) == 3 and palette == 0:
                    codes.append("missing_palette")
                idat_bytes = idat_bytes + size
            elif "IDAT" in seen:
                idat_ended = True
            if valid_type and raw_type[0] & 32 == 0 and name not in ["IHDR", "PLTE", "IDAT", "IEND"]:
                codes.append("unknown_critical")
            metadata: Json = {}
            decoded: bool = name in [
                "IHDR",
                "PLTE",
                "IEND",
                "tRNS",
                "gAMA",
                "sRGB",
                "pHYs",
                "tIME",
                "tEXt",
                "zTXt",
                "iTXt",
                "iCCP",
            ]
            if decoded and (name in ["IHDR", "PLTE", "IEND"] or metadata_bytes + size <= 65536):
                metadata_bytes = metadata_bytes + size
                try:
                    metadata = describe(name, payload, header, palette)
                    if name == "IHDR" and "IHDR" not in seen:
                        header = metadata
                    if name == "PLTE":
                        palette = json_int(metadata["entries"])
                except Exception as error:
                    errors.append({"offset": cursor, "code": "metadata", "detail": str(error)})
            elif name != "IDAT":
                metadata = {"decoded": False}
            if name != "IDAT" and ((not decoded) or ("decoded" in metadata)) and name not in unchecked:
                unchecked.append(name)
            for code in codes:
                errors.append({"offset": cursor, "code": code, "detail": name})
            chunks.append(
                {
                    "index": len(chunks),
                    "offset": cursor,
                    "length": size,
                    "type": name,
                    "type_hex": raw_type.hex(),
                    "type_valid": valid_type,
                    "critical": raw_type[0] & 32 == 0,
                    "private": raw_type[1] & 32 != 0,
                    "safe_to_copy": raw_type[3] & 32 != 0,
                    "crc_stored": stored,
                    "crc_computed": computed,
                    "crc_ok": stored == computed,
                    "data_sha256": digest(payload),
                    "metadata": metadata,
                }
            )
            seen.append(name)
            cursor = cursor + size + 12
            if name == "IEND":
                break
        if "IHDR" not in seen or "IDAT" not in seen or "IEND" not in seen:
            errors.append(
                {"offset": cursor, "code": "missing_required_chunk", "detail": "IHDR, IDAT and IEND required"}
            )
        if "IDAT" in seen and idat_bytes == 0:
            errors.append({"offset": cursor, "code": "empty_image_data", "detail": "no compressed image bytes"})
        if "IEND" in seen and cursor != len(data):
            errors.append({"offset": cursor, "code": "trailing_data", "detail": "bytes after IEND"})
    return {
        "header": header,
        "chunks": chunks,
        "errors": errors,
        "unchecked": unchecked,
        "summary": {
            "bytes": len(data),
            "chunks": len(chunks),
            "errors": len(errors),
            "crc_errors": crc_errors,
            "idat_bytes": idat_bytes,
            "scanned_bytes": cursor,
            "unscanned_bytes": len(data) - cursor,
        },
    }
