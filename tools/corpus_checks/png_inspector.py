"""Complete PNG application acceptance: independent bytes, diagnostics, replay and publication."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import struct
import subprocess
import zlib
from pathlib import Path

from .common import Application
from .png_fixture import (
    SIGNATURE,
    canonical,
    chunk,
    digest,
    frames,
    header,
    image,
    inspect_html,
    inspect_results,
    minimal,
    rich_metadata,
    rich_parts,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: bytes | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "inspect", "input": "source.png", "output": "output"}
    save(root / "png-job.json", config)
    (root / "source.png").write_bytes(image(rich_parts()) if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = (root / config["input"]).read_bytes()
    source = bytes.fromhex(json.loads(imported)["source_hex"]) if config["mode"] == "verify" else imported
    directory = root / config["output"]
    raw = (directory / "archive.json").read_bytes()
    archive = json.loads(raw)
    assert archive.keys() == {"version", "source_hex", "results"}
    assert type(archive["version"]) is int and archive["version"] == 1
    assert archive["source_hex"] == source.hex() and raw == canonical(archive)
    results = archive["results"]
    inspect_results(source, results)
    html = (directory / "report.html").read_bytes()
    inspect_html(html, results)
    files = {
        "image.png": source,
        "archive.json": raw,
        "chunks.json": canonical(results["chunks"]),
        "report.html": html,
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "results": results, "archive_sha256": digest(raw)}
        ),
        "inspect.json": canonical({"version": 1, "mode": "inspect", "input": "image.png", "output": "inspected"}),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    if config["mode"] == "verify":
        assert canonical(json.loads(imported)) == raw
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "png-job.json", codes: list | None = None) -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"PNG_CONFIG": str(root / selected)}, timeout=180)
    assert result.returncode in {0, 1} and not result.stderr, (root, result)
    archive = inspect(root, config)
    errors = archive["results"]["errors"]
    assert result.returncode == int(bool(errors))
    assert result.stdout == canonical(archive["results"]["summary"]).decode()
    if codes is not None:
        assert [row["code"] for row in errors] == codes, (root, errors, codes)
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=120)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".png-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: bytes, stem: str, codes: list | None = None) -> dict:
    original = files_at(root)
    config = json.loads((root / "inspect.json").read_bytes())
    config.update(input=stem + ".png", output=stem)
    (root / config["input"]).write_bytes(source)
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json", codes)
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root), codes=[])
    rows = archive["results"]["chunks"]
    assert {i: r["metadata"] for i, r in enumerate(rows)} == rich_metadata()
    assert archive["results"]["header"] == rich_metadata()[0]
    assert archive["results"]["unchecked"] == ["image_data_decompression", "pixel_values", "vpAg"]
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "inspect.json") == archive
    cases = [
        (b"tEXt", b"x\0", {"keyword": "x", "text": ""}),
        (b"tEXt", b"\xa1" * 79 + b"\0\x80\xff", {"keyword": "¡" * 79, "text": "\x80ÿ"}),
        (
            b"zTXt",
            b"Comment\0\0" + zlib.compress(b"hello"),
            {"keyword": "Comment", "compressed_bytes": 13, "decoded": False},
        ),
        (b"iCCP", b"Profile\0\0not inflated", {"keyword": "Profile", "compressed_bytes": 12, "decoded": False}),
        (
            b"iTXt",
            b"Key\0\1\0en\0Name\0opaque",
            {"keyword": "Key", "language": "en", "translated": "Name", "compressed_bytes": 6, "decoded": False},
        ),
        (b"iTXt", b"Key\0\0\xff\0\0", {"keyword": "Key", "language": "", "translated": "", "text": ""}),
        (b"tRNS", b"\xff\xff", {"samples": [65535]}),
        (
            b"tIME",
            struct.pack(">HBBBBB", 2000, 2, 29, 0, 0, 0),
            {"year": 2000, "month": 2, "day": 29, "hour": 0, "minute": 0, "second": 0},
        ),
        (b"pHYs", struct.pack(">IIB", 0, 2147483647, 0), {"x": 0, "y": 2147483647, "unit": 0}),
        (b"gAMA", struct.pack(">I", 2147483647), {"gamma_times_100000": 2147483647}),
    ]
    for index, (name, payload, expected) in enumerate(cases):
        work = root / str(index)
        basic = minimal()
        found = run(app, work, fixture(work, image(basic[:1] + [(name, payload)] + basic[1:])), codes=[])
        assert found["results"]["chunks"][1]["metadata"] == expected
    # Alpha/RGB transparency and duplicate text keywords are independent of indexed palettes.
    basic = minimal()
    basic[0] = (b"IHDR", header(1, 1, 8, 2))
    extra = [(b"tRNS", struct.pack(">HHH", 255, 256, 65535)), (b"tEXt", b"x\0one"), (b"tEXt", b"x\0two")]
    work = root / "rgb"
    found = run(app, work, fixture(work, image(basic[:1] + extra + basic[1:])), codes=[])
    assert found["results"]["chunks"][1]["metadata"] == {"samples": [255, 256, 65535]}
    # A deliberately invalid deflate stream is recorded as unchecked, never falsely advertised as decoded.
    work = root / "opaque-image"
    basic[1] = (b"IDAT", b"not a deflate stream")
    run(app, work, fixture(work, image(basic)), codes=[])
    return {
        "metadata_cases": len(cases) + 2,
        "rich_chunks": len(rows),
        "latin1_utf8_html_escaping": True,
        "opaque_compressed_payloads_explicit": True,
        "actual_replay_and_inspection_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(111)
    hashes = []
    count = 0
    for color, depths in {0: [1, 2, 4, 8, 16], 2: [8, 16], 3: [1, 2, 4, 8], 4: [8, 16], 6: [8, 16]}.items():
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
        for depth in depths:
            for width in [1, 13]:
                height = 3
                row_bytes = (width * channels * depth + 7) // 8
                pixels = b"".join(b"\0" + rng.randbytes(row_bytes) for _ in range(height))
                compressed = zlib.compress(pixels)
                assert zlib.decompress(compressed) == pixels
                before = [(b"IHDR", header(width, height, depth, color))]
                if color == 3:
                    before.append((b"PLTE", rng.randbytes(3 * (1 << depth))))
                parts = before + [(b"IDAT", compressed), (b"IEND", b"")]
                work = root / str(count)
                archive = run(app, work, fixture(work, image(parts)), codes=[])
                expected = {
                    "width": width,
                    "height": height,
                    "bit_depth": depth,
                    "color_type": color,
                    "compression": 0,
                    "filter": 0,
                    "interlace": 0,
                }
                assert archive["results"]["header"] == expected
                split = [(b"IDAT", b"")] + [(b"IDAT", compressed[i : i + 3]) for i in range(0, len(compressed), 3)]
                changed = edit_export(app, work / "output", image(before + split + [(b"IEND", b"")]), "rechunk", [])
                assert changed["results"]["header"] == expected
                assert changed["results"]["summary"]["idat_bytes"] == len(compressed)
                assert consume(app, work / "output/rechunk", "replay.json") == changed
                hashes.extend([digest(canonical(archive)), digest(canonical(changed))])
                count += 1
    work = root / "interlaced"
    parts = minimal()
    parts[0] = (b"IHDR", header(2147483647, 2147483647, 16, 6, 1))
    run(app, work, fixture(work, image(parts)), codes=[])
    return {
        "seed": 111,
        "color_depth_combinations": 15,
        "generated_images": count,
        "rechunked_images": count,
        "idat_streams_independently_inflated": count,
        "maximum_dimensions_and_interlace_header": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def malformed(app: Application, root: Path) -> dict:
    basic = minimal()
    cases = [
        (b"not PNG", ["signature"]),
        (image([basic[1], basic[0], basic[2]]), ["header_first"]),
        (image([basic[0], basic[0], *basic[1:]]), ["duplicate_chunk"]),
        (image([basic[0], (b"IDAT", b""), basic[2]]), ["empty_image_data"]),
        (image(basic[:-1]), ["missing_required_chunk"]),
        (image(basic) + b"tail", ["trailing_data"]),
        (image(basic) + chunk(b"IEND"), ["trailing_data"]),
        (image([basic[0], (b"IDAT", b"a"), (b"tEXt", b"x\0y"), (b"IDAT", b"b"), basic[2]]), ["nonconsecutive_idat"]),
        (image([basic[0], (b"ABCD", b""), *basic[1:]]), ["unknown_critical"]),
        (image([basic[0], (b"abca", b""), *basic[1:]]), ["chunk_type"]),
        (image([basic[0], (b"a\xffAa", b""), *basic[1:]]), ["chunk_type"]),
        (image([basic[0], basic[1], (b"gAMA", struct.pack(">I", 1)), basic[2]]), ["chunk_order"]),
        (image([(b"IHDR", header()), *basic[1:]]), ["missing_palette"]),
        (
            image([(b"IHDR", header()), (b"tRNS", b"\xff"), (b"PLTE", b"abc"), *basic[1:]]),
            ["metadata", "palette_order"],
        ),
        (SIGNATURE + struct.pack(">I", 0x80000000) + b"tEXt", ["chunk_length", "missing_required_chunk"]),
    ]
    bad_crc = bytearray(image(basic))
    bad_crc[29] ^= 1
    cases.append((bytes(bad_crc), ["crc"]))
    for index, (raw, codes) in enumerate(cases):
        work = root / ("structure-" + str(index))
        archive = run(app, work, fixture(work, raw), codes=codes)
        assert consume(app, work / "output", "replay.json") == archive
    metadata_cases = [
        (b"IHDR", b"", "IHDR length"),
        (b"IHDR", header(0), "image dimensions"),
        (b"IHDR", header(depth=16, color=3), "color and bit depth combination"),
        (b"IHDR", header(interlace=2), "header methods"),
        (b"PLTE", b"ab", "palette length"),
        (b"PLTE", b"abc", "palette forbidden for grayscale"),
        (b"tRNS", b"a", "transparent sample length"),
        (b"gAMA", b"\0" * 4, "gamma value"),
        (b"sRGB", b"\4", "rendering intent"),
        (b"pHYs", struct.pack(">IIB", 1, 1, 2), "physical dimensions"),
        (b"pHYs", struct.pack(">IIB", 0xFFFFFFFF, 1, 1), "physical density range"),
        (b"tIME", b"", "timestamp length"),
        (b"tIME", struct.pack(">HBBBBB", 1900, 2, 29, 0, 0, 0), "calendar date"),
        (b"tIME", struct.pack(">HBBBBB", 2024, 0, 1, 0, 0, 0), "calendar date"),
        (b"tIME", struct.pack(">HBBBBB", 2024, 1, 1, 24, 0, 0), "timestamp clock"),
        (b"tEXt", b"missing", "missing keyword separator"),
        (b"tEXt", b"\0body", "keyword length"),
        (b"tEXt", b"x" * 80 + b"\0", "keyword length"),
        (b"tEXt", b" x\0y", "keyword spacing"),
        (b"tEXt", b"x \0y", "keyword spacing"),
        (b"tEXt", b"x  y\0z", "keyword spacing"),
        (b"tEXt", b"\x80\0y", "keyword character"),
        (b"tEXt", b"x\0y\0", "null in text"),
        (b"zTXt", b"x\0\1body", "compression method"),
        (b"iCCP", b"x\0", "compression method"),
        (b"iTXt", b"x\0\2\0", "international text flags"),
        (b"iTXt", b"x\0\1\1", "compression method"),
        (b"iTXt", b"x\0\0\0en", "missing language separator"),
        (b"iTXt", b"x\0\0\0\xff\0\0", "non-ASCII language tag"),
        (b"iTXt", b"x\0\0\0en\0name", "missing translated keyword separator"),
        (b"iTXt", b"x\0\0\0en\0\xff\0body", "invalid UTF-8 metadata"),
        (b"iTXt", b"x\0\0\0en\0name\0\xff", "invalid UTF-8 metadata"),
        (b"iTXt", b"x\0\0\0en\0name\0a\0", "null in international text"),
        (b"IEND", b"x", "IEND length"),
    ]
    for index, (name, body, detail) in enumerate(metadata_cases):
        parts = minimal()
        if name == b"IHDR":
            parts[0] = (name, body)
        elif name == b"IEND":
            parts[-1] = (name, body)
        else:
            parts.insert(1, (name, body))
        work = root / ("metadata-" + str(index))
        archive = run(app, work, fixture(work, image(parts)), codes=["metadata"])
        assert archive["results"]["errors"][0]["detail"] == detail
    # Every proper prefix must stop at the last complete known chunk, preserving its exact byte inventory.
    raw = image(minimal())
    known, _ = frames(raw)
    for size in range(len(raw)):
        work = root / ("prefix-" + str(size))
        if size < 8:
            codes = ["signature"]
            stop = 0
        else:
            complete = [row for row in known if row["offset"] + row["length"] + 12 <= size]
            stop = complete[-1]["offset"] + complete[-1]["length"] + 12 if complete else 8
            codes = [] if stop == size else ["truncated_header" if size - stop < 8 else "chunk_length"]
            codes.append("missing_required_chunk")
        archive = run(app, work, fixture(work, raw[:size]), codes=codes)
        assert archive["results"]["summary"]["scanned_bytes"] == stop
    return {
        "structural_mutations_replayed": len(cases),
        "metadata_diagnostics": len(metadata_cases),
        "all_proper_prefixes": len(raw),
        "exact_codes_offsets_crc_and_payload_hashes": True,
    }


def invalid(app: Application, root: Path) -> dict:
    configs = []
    base = {"version": 1, "mode": "inspect", "input": "source.png", "output": "output"}
    for key, values in [
        ("version", [None, True, 1.0, 0, 2, "1"]),
        ("mode", [None, True, 0, "", "decode"]),
        ("input", [None, 1, "", "missing", "bad\0path"]),
        ("output", [None, 1, "", "source.png", "missing/parent/output", "bad\0path"]),
    ]:
        configs.extend(dict(base, **{key: value}) for value in values)
    configs.extend({key: value for key, value in base.items() if key != omitted} for omitted in base)
    configs.append(dict(base, extra=1))
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "png-job.json", config)
        reject(app, work)
    broken = [
        b"",
        b"{}{}",
        b"[] trailing",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e9999}',
        b"\xff",
        b'{"x":"\\ud800"}',
    ]
    for slot in ["request", "archive"]:
        for index, raw in enumerate(broken):
            work = root / (slot + "-json-" + str(index))
            config = fixture(work)
            name = "png-job.json"
            if slot == "archive":
                name = "archive.json"
                config.update(mode="verify", input=name)
                save(work / "png-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "baseline"
    archive = run(app, work, fixture(work), codes=[])
    changes = [
        (("version",), 1.0),
        (("version",), True),
        (("source_hex",), None),
        (("source_hex",), archive["source_hex"].upper()),
        (("source_hex",), " " + archive["source_hex"]),
        (("source_hex",), archive["source_hex"][:-1]),
        (("source_hex",), "zz"),
        (("source_hex",), "00" + archive["source_hex"][2:]),
        (("results", "summary", "bytes"), float(archive["results"]["summary"]["bytes"])),
        (("results", "summary", "errors"), False),
        (("results", "summary", "crc_errors"), 1),
        (("results", "header", "width"), 4),
        (("results", "chunks", 0, "crc_ok"), 1),
        (("results", "chunks", 0, "offset"), 9),
        (("results", "chunks", 0, "data_sha256"), "0" * 64),
        (("results", "chunks", 6, "metadata", "text"), "edited"),
        (("results", "errors"), [{"offset": 0, "code": "fake", "detail": "x"}]),
        (("results", "unchecked"), []),
        (("results",), None),
    ]
    altered = []
    for path, value in changes:
        changed = copy.deepcopy(archive)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        altered.append(changed)
    altered.extend({key: value for key, value in archive.items() if key != omitted} for omitted in archive)
    altered.append(dict(archive, extra=0))
    for index, changed in enumerate(altered):
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "png-job.json", config)
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests": len(configs),
        "malformed_json_per_input": len(broken),
        "tampered_archives": len(altered),
        "strict_cached_types_and_canonical_hex": True,
    }


def limits(app: Application, root: Path) -> dict:
    basic = minimal()
    # Keep each boundary orthogonal: size limit, chunk count and decoded metadata allowance.
    maximum = 16777216
    padding = maximum - len(image(basic)) - 12
    raw = image([basic[0], (b"vpAg", b"x" * padding), *basic[1:]])
    assert len(raw) == maximum
    work = root / "maximum-bytes"
    archive = run(app, work, fixture(work, raw), codes=[])
    assert consume(app, work / "output", "replay.json") == archive
    work = root / "over-bytes"
    fixture(work, raw + b"x")
    reject(app, work, "input byte limit")
    del raw, archive
    for count in [4096, 4097]:
        work = root / ("chunks-" + str(count))
        raw = image([basic[0], *[(b"vpAg", b"")] * (count - 3), *basic[1:]])
        config = fixture(work, raw)
        if count == 4096:
            archive = run(app, work, config, codes=[])
            assert len(archive["results"]["chunks"]) == count
        else:
            reject(app, work, "chunk count limit")
    text = b"K\0" + b"x" * (65536 - 13 - 2)
    work = root / "metadata-budget"
    config = fixture(work, image([basic[0], (b"tEXt", text), (b"tEXt", b"invalid skipped"), *basic[1:]]))
    found = run(app, work, config, codes=[])["results"]
    assert len(found["chunks"][1]["metadata"]["text"]) == len(text) - 2
    assert found["chunks"][2]["metadata"] == {"decoded": False} and "tEXt" in found["unchecked"]
    work = root / "exact-request"
    config = fixture(work)
    path = work / "png-job.json"
    path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config, codes=[])
    work = root / "over-request"
    fixture(work)
    path = work / "png-job.json"
    path.write_bytes(path.read_bytes().ljust(65537, b" "))
    reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "png-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(67108864 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config, codes=[])
    work = root / "over-hex"
    config = fixture(work)
    config.update(mode="verify", input="archive.json")
    save(work / "png-job.json", config)
    save(work / "archive.json", dict(archive, source_hex="00" * (16777216 + 1)))
    reject(app, work, "source byte limit")
    return {
        "source_bytes": maximum,
        "archive_bytes": 67108864,
        "request_bytes": 65536,
        "chunk_count": 4096,
        "decoded_metadata_bytes": 65536,
        "maximum_source_replayed": True,
        "every_limit_exceeded_separately": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = image(rich_parts())
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"PNG_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".png-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "source", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"PNG_PAUSE": stage, "PNG_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 10)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            if mutation.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9 and (work / "output").exists() == (stage == "published")
                assert len(list(work.glob(".png-*"))) == (1 if stage == "staged" else 0)
                if stage == "published":
                    inspect(work, config)
                config["output"] = "retry"
                save(work / "retry.json", config)
                run(app, work, config, selected="retry.json")
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = "png-job.json" if mutation == "request" else "source.png"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".png-*"))
                if mutation == "competitor":
                    assert (work / "output/keep").read_text() == "original"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()
    return {
        "caught_faults": 2,
        "hard_kills": 2,
        "input_output_races": 3,
        "retry_after_hard_kill": True,
        "complete_or_absent_final_bundle": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["png-job.json", "source.png"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work)
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work)
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "png-job.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr and not result.stdout
            if kind == "file":
                assert output.read_text() == "keep"
            elif kind == "directory":
                assert not list(output.iterdir())
            elif kind == "symlink":
                assert output.is_symlink()
            else:
                assert not output.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated),
        ("malformed", malformed),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " PNG inspector " + name + ": passed", flush=True)
    return observations
