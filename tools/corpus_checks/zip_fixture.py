"""Independent ZIP construction, standard-library extraction oracle and exact report inspection."""

from __future__ import annotations

import binascii
import hashlib
import io
import json
import struct
import zipfile
import zlib
from pathlib import Path

from .population_fixture import canonical, digest

__all__ = ["canonical", "check_valid", "craft", "digest", "files_at", "inspect", "raw_deflate", "save", "standard"]


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def raw_deflate(data: bytes, level: int = 6) -> bytes:
    compressor = zlib.compressobj(level, zlib.DEFLATED, -15)
    return compressor.compress(data) + compressor.flush()


def craft(entries: list[dict], comment: bytes = b"") -> bytes:
    """Assemble independent ZIP32 records; overrides deliberately make malformed fixtures."""
    body = bytearray()
    directory = bytearray()
    for item in entries:
        name = item.get("name", b"notes.txt")
        data = item.get("data", b"Saved network message\n")
        flags = item.get("flags", 0)
        method = item.get("method", 8)
        extra = item.get("extra", b"")
        local_extra = item.get("local_extra", extra)
        local_name = item.get("local_name", name)
        compressed = item.get("compressed", raw_deflate(data) if method == 8 else data)
        checksum = item.get("crc", binascii.crc32(data))
        expanded = item.get("expanded", len(data))
        length = item.get("compressed_size", len(compressed))
        version = item.get("version", 20)
        offset = len(body)
        local_values = (0, 0, 0) if flags & 8 else (checksum, length, expanded)
        local_values = item.get("local_values", local_values)
        body.extend(
            struct.pack(
                "<4s5H3I2H",
                b"PK\x03\x04",
                version,
                flags,
                method,
                0,
                33,
                *local_values,
                len(local_name),
                len(local_extra),
            )
        )
        body.extend(local_name + local_extra + compressed)
        if flags & 8:
            body.extend(
                (b"PK\x07\x08" if item.get("signed", True) else b"") + struct.pack("<3I", checksum, length, expanded)
            )
        note = item.get("comment", b"")
        directory.extend(
            struct.pack(
                "<4s6H3I5H2I",
                b"PK\x01\x02",
                item.get("made", 3 << 8 | 20),
                version,
                flags,
                method,
                0,
                33,
                checksum,
                length,
                expanded,
                len(name),
                len(extra),
                len(note),
                item.get("disk", 0),
                0,
                item.get("attributes", 0o100644 << 16),
                offset,
            )
        )
        directory.extend(name + extra + note)
    return bytes(
        body
        + directory
        + struct.pack(
            "<4s4H2IH", b"PK\x05\x06", 0, 0, len(entries), len(entries), len(directory), len(body), len(comment)
        )
        + comment
    )


def standard(entries: list[tuple[str, bytes, int]], streaming: bool = False, zip64: bool = False) -> bytes:
    class Nonseekable(io.BytesIO):
        def seekable(self) -> bool:
            return False

        def seek(self, *args: object) -> int:
            raise io.UnsupportedOperation("seek")

    output = Nonseekable() if streaming else io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, raw, method in entries:
            info = zipfile.ZipInfo(name, (2026, 10, 15, 12, 0, 0))
            info.compress_type = method
            info.external_attr = (0o40755 if name.endswith("/") else 0o100644) << 16
            with archive.open(info, "w", force_zip64=zip64) as target:
                target.write(raw)
    return output.getvalue()


def files_at(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def inspect(root: Path, config: dict) -> dict:
    original = (root / config["input"]).read_bytes()
    imported = json.loads(original) if config["mode"] == "verify" else None
    source = bytes.fromhex(imported["source_hex"]) if imported else original
    settings = imported["limits"] if imported else config["limits"]
    directory = root / config["output"]
    encoded = (directory / "archive.json").read_bytes()
    archive = json.loads(encoded)
    assert archive.keys() == {"version", "source_hex", "limits", "results"}
    assert type(archive["version"]) is int and archive["version"] == 1
    assert archive["source_hex"] == source.hex() and archive["limits"] == settings and encoded == canonical(archive)
    results = archive["results"]
    assert results.keys() == {"summary", "entries", "errors"}
    summary = results["summary"]
    assert summary.keys() == {
        "bytes",
        "declared_entries",
        "entries",
        "verified_payloads",
        "checked_bytes",
        "budget_used",
        "errors",
    }
    assert all(type(value) is int and value >= 0 for value in summary.values())
    assert summary["bytes"] == len(source) and summary["entries"] == len(results["entries"])
    assert summary["errors"] == len(results["errors"])
    assert 0 <= summary["checked_bytes"] <= summary["budget_used"] <= settings["total_bytes"]
    assert len(results["entries"]) <= settings["entries"]
    fields = {
        "index",
        "name",
        "key",
        "name_hex",
        "central_offset",
        "local_offset",
        "end_offset",
        "flags",
        "method",
        "compressed",
        "expanded",
        "crc",
        "checked_bytes",
        "computed_crc",
        "sha256",
        "codes",
    }
    for index, entry in enumerate(results["entries"]):
        assert entry.keys() == fields and entry["index"] == index
        assert type(entry["name"]) is type(entry["key"]) is str
        assert bytes.fromhex(entry["name_hex"]).hex() == entry["name_hex"]
        assert entry["codes"] == sorted(set(entry["codes"]))
        assert all(type(entry[k]) is int for k in fields - {"name", "key", "name_hex", "sha256", "codes"})
        assert entry["checked_bytes"] <= settings["entry_bytes"]
        assert entry["checked_bytes"] >= 0 or entry["sha256"] == ""
        assert [r["code"] for r in results["errors"] if r["entry"] == index] == entry["codes"]
    for error in results["errors"]:
        assert error.keys() == {"entry", "offset", "code"} and type(error["entry"]) is type(error["offset"]) is int
        assert isinstance(error["code"], str) and -1 <= error["entry"] < len(results["entries"])
    files = {
        "source.zip": source,
        "archive.json": encoded,
        "entries.json": canonical(results["entries"]),
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "results": results, "archive_sha256": digest(encoded)}
        ),
        "report.txt": (json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(),
        "inspect.json": canonical(
            {"version": 1, "mode": "inspect", "input": "source.zip", "output": "inspected", "limits": settings}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    if imported:
        assert canonical(imported) == encoded
    return archive


def check_valid(source: bytes, results: dict) -> None:
    assert results["errors"] == []
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        items = archive.infolist()
        assert len(items) == len(results["entries"])
        total = 0
        for info, observed in zip(items, results["entries"], strict=True):
            raw = archive.read(info)
            assert observed["name"] == info.filename
            assert observed["compressed"] == info.compress_size and observed["expanded"] == info.file_size
            assert observed["crc"] == observed["computed_crc"] == info.CRC == binascii.crc32(raw)
            assert observed["sha256"] == hashlib.sha256(raw).hexdigest() and observed["checked_bytes"] == len(raw)
            assert observed["local_offset"] == info.header_offset
            total += len(raw)
        assert results["summary"]["checked_bytes"] == results["summary"]["budget_used"] == total
        assert results["summary"]["verified_payloads"] == len(items)
    return  # noqa: PLR1711
