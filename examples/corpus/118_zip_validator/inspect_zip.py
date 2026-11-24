"""Inspect physical ZIP32 records without extracting any entry to the filesystem."""

# ruff: noqa: BLE001, C414 - forensic errors; sorted requires a list in this subset
from binary import digest
from headers import Entry, central, ending, local
from names import decode_name

from py2rust.stdlib import Json, crc32, deflate_decompress, json_int


def inspect(data: bytes, settings: Json) -> Json:
    entries: list[Json] = []
    errors: list[Json] = []
    seen: set[str] = set()
    spans: list[tuple[int, int]] = []
    budget: int = 0
    checked: int = 0
    verified: int = 0
    declared: int = 0
    cursor: int = 0
    try:
        end: tuple[int, int, int, list[str]] = ending(data)
        directory: int = end[1]
        declared = end[2]
        for code in end[3]:
            errors.append({"entry": -1, "offset": end[0], "code": code})
        if declared > json_int(settings["entries"]):
            errors.append({"entry": -1, "offset": end[0], "code": "entry_limit"})
        cursor = directory
        if len(errors) == 0:
            for index in range(declared):
                parsed: tuple[Entry, int] = central(data, cursor, end[0])
                entry: Entry = parsed[0]
                origin: int = cursor
                cursor = parsed[1]
                named: tuple[str, str, list[str]] = decode_name(entry.name, entry.flags, entry.extra)
                codes: list[str] = named[2]
                if named[1] in seen:
                    codes.append("duplicate_name")
                seen.add(named[1])
                mode: int = (entry.attributes >> 16) & 61440
                if entry.made >> 8 == 3 and mode not in [0, 16384, 32768]:
                    codes.append("unsafe_type")
                unsupported: bool = False
                reserved: int = 63478 if entry.method == 0 else 63472
                if entry.version > 20 or entry.method not in [0, 8] or entry.disk != 0 or entry.flags & reserved != 0:
                    codes.append("unsupported_entry")
                    unsupported = True
                if entry.flags & 1 != 0:
                    codes.append("encrypted")
                    unsupported = True
                if (
                    entry.compressed == 4294967295
                    or entry.expanded == 4294967295
                    or entry.offset == 4294967295
                    or "zip64" in codes
                ):
                    codes.append("zip64_entry")
                    unsupported = True
                size: int = -1
                actual_crc: int = -1
                payload_hash: str = ""
                stop: int = entry.offset
                try:
                    located: tuple[int, int, bytes, list[str]] = local(data, entry, directory)
                    stop = located[1]
                    codes = codes + located[3] + decode_name(entry.name, entry.flags, located[2])[2]
                    overlap: bool = False
                    for span in spans:
                        if entry.offset < span[1] and span[0] < stop:
                            overlap = True
                    if overlap:
                        codes.append("overlap")
                    else:
                        spans.append((entry.offset, stop))
                    compressed: bytes = data[located[0] : located[0] + entry.compressed] if not overlap else b""
                    allowance: int = min(json_int(settings["entry_bytes"]), json_int(settings["total_bytes"]) - budget)
                    if entry.expanded > allowance:
                        codes.append("expanded_limit")
                    elif not unsupported and not overlap and "zip64" not in codes:
                        try:
                            decoded: bytes = (
                                deflate_decompress(compressed, allowance) if entry.method == 8 else compressed
                            )
                            assert len(decoded) <= allowance, "stored expansion limit"
                            size = len(decoded)
                            budget = budget + size
                            checked = checked + size
                            actual_crc = crc32(decoded)
                            payload_hash = digest(decoded)
                            if size != entry.expanded:
                                codes.append("expanded_size")
                            if actual_crc != entry.crc:
                                codes.append("crc")
                            if (named[0].endswith("/") or mode == 16384 or entry.attributes & 16 != 0) and size != 0:
                                codes.append("directory_payload")
                            if size == entry.expanded and actual_crc == entry.crc:
                                verified = verified + 1
                        except Exception:
                            budget = budget + allowance
                            codes.append("decompression")
                except Exception:
                    codes.append("local_structure")
                distinct: list[str] = sorted(list(set(codes)))
                for code in distinct:
                    errors.append({"entry": index, "offset": origin, "code": code})
                entries.append(
                    {
                        "index": index,
                        "name": named[0],
                        "key": named[1],
                        "name_hex": entry.name.hex(),
                        "central_offset": origin,
                        "local_offset": entry.offset,
                        "end_offset": stop,
                        "flags": entry.flags,
                        "method": entry.method,
                        "compressed": entry.compressed,
                        "expanded": entry.expanded,
                        "crc": entry.crc,
                        "checked_bytes": size,
                        "computed_crc": actual_crc,
                        "sha256": payload_hash,
                        "codes": distinct,
                    }
                )
            if cursor != end[0]:
                errors.append({"entry": -1, "offset": cursor, "code": "central_trailing"})
            covered: int = 0
            for span in sorted(spans):
                if span[0] != covered:
                    errors.append({"entry": -1, "offset": covered, "code": "unclaimed_local_bytes"})
                covered = span[1]
            if covered != directory:
                errors.append({"entry": -1, "offset": covered, "code": "unclaimed_local_bytes"})
    except Exception:
        errors.append({"entry": -1, "offset": cursor, "code": "archive_structure"})
    return {
        "summary": {
            "bytes": len(data),
            "declared_entries": declared,
            "entries": len(entries),
            "verified_payloads": verified,
            "checked_bytes": checked,
            "budget_used": budget,
            "errors": len(errors),
        },
        "entries": entries,
        "errors": errors,
    }
