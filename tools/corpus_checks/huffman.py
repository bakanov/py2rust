"""Independent tree construction, string bitstreams, malformed containers and binary publication checks."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import hashlib
import itertools
import json
import random
import selectors
import struct
import subprocess
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from pathlib import Path

from .common import Application
from .csv_json import canonical

MAGIC = b"PYHF068!"


def sample() -> bytes:
    return b"BANANA BANDANA\n" * 256 + bytes(range(256))


def widths_for(data: bytes) -> dict:
    # Sorted weighted leaf-depth maps, independent of the application's heap/node arrays.
    forest = [(count, symbol, {symbol: 0}) for symbol, count in Counter(data).items()]
    while len(forest) > 1:
        forest.sort(key=lambda row: row[:2])
        a, b = forest[:2]
        forest = forest[2:]
        merged = {symbol: depth + 1 for tree in [a[2], b[2]] for symbol, depth in tree.items()}
        forest.append((a[0] + b[0], min(a[1], b[1]), merged))
    return {symbol: max(1, depth) for symbol, depth in forest[0][2].items()} if forest else {}


def strings_for(widths: dict) -> dict:
    if not widths:
        return {}
    assert all(0 <= s <= 255 and 1 <= w <= 32 for s, w in widths.items())
    if len(widths) == 1:
        assert list(widths.values()) == [1]
    else:
        assert sum(Fraction(1, 2**w) for w in widths.values()) == 1
    ordered = sorted(widths, key=lambda s: (widths[s], s))
    result = {ordered[0]: "0" * widths[ordered[0]]}
    for previous, symbol in itertools.pairwise(ordered):
        value = int(result[previous], 2) + 1
        result[symbol] = format(value, "0" + str(widths[previous]) + "b") + "0" * (widths[symbol] - widths[previous])
    assert all(len(result[s]) == widths[s] for s in widths)
    assert not any(b.startswith(a) for x, a in result.items() for y, b in result.items() if x != y)
    return result


def signed(prefix: bytes) -> bytes:
    return prefix + hashlib.sha256(prefix).digest()


def assemble(size: int, bits: int, entries: list, payload: bytes, digest: bytes, count: int | None = None) -> bytes:
    table = bytes(itertools.chain.from_iterable(entries))
    return signed(
        MAGIC + struct.pack(">IIH", size, bits, len(entries) if count is None else count) + digest + table + payload
    )


def reference_encode(data: bytes, widths: dict | None = None) -> bytes:
    widths = widths_for(data) if widths is None else widths
    spellings = strings_for(widths)
    bits = "".join(spellings[symbol] for symbol in data)
    padded = bits + "0" * (-len(bits) % 8)
    payload = bytes(int(padded[i : i + 8], 2) for i in range(0, len(padded), 8))
    return assemble(len(data), len(bits), sorted(widths.items()), payload, hashlib.sha256(data).digest())


def inspect(raw: bytes) -> tuple[int, int, dict, bytes, bytes]:
    assert len(raw) >= 82 and raw[:8] == MAGIC and hashlib.sha256(raw[:-32]).digest() == raw[-32:]
    size, bits, count = struct.unpack(">IIH", raw[8:18])
    assert size <= 1048576 and count <= min(256, size) and size <= bits <= size * 32
    assert len(raw) == 82 + 2 * count + (bits + 7) // 8
    entries = list(zip(raw[50 : 50 + 2 * count : 2], raw[51 : 50 + 2 * count : 2], strict=True))
    assert entries == sorted(set(entries)) and len({s for s, _ in entries}) == count
    widths = dict(entries)
    strings_for(widths)
    assert bool(size) == bool(widths)
    payload = raw[50 + 2 * count : -32]
    if bits % 8:
        assert payload[-1] & ((1 << (8 - bits % 8)) - 1) == 0
    return size, bits, widths, payload, raw[18:50]


def reference_decode(raw: bytes) -> bytes:
    size, bits, widths, payload, digest = inspect(raw)
    spellings = strings_for(widths)
    tree = {}
    for symbol, spelling in spellings.items():
        node = tree
        for bit in spelling:
            node = node.setdefault(bit, {})
        node["symbol"] = symbol
    stream = "".join(format(byte, "08b") for byte in payload)[:bits]
    output = bytearray()
    node = tree
    for bit in stream:
        assert bit in node
        node = node[bit]
        if "symbol" in node:
            output.append(node["symbol"])
            node = tree
    assert node is tree and len(output) == size and set(output) == set(widths)
    assert hashlib.sha256(output).digest() == digest
    return bytes(output)


@cache
def optimum(weights: tuple[int, ...]) -> int:
    if len(weights) <= 1:
        return 0
    # Enumerate every possible merge tree for small alphabets, not just the greedy choice.
    return min(
        weights[a]
        + weights[b]
        + optimum(tuple(sorted([w for i, w in enumerate(weights) if i not in [a, b]] + [weights[a] + weights[b]])))
        for a, b in itertools.combinations(range(len(weights)), 2)
    )


def report_for(operation: str, original: bytes, raw: bytes) -> dict:
    _, bits, widths, payload, _ = inspect(raw)
    spellings = strings_for(widths)
    counts = Counter(original)
    return {
        "version": 1,
        "operation": operation,
        "original_bytes": len(original),
        "container_bytes": len(raw),
        "payload_bits": bits,
        "payload_bytes": len(payload),
        "padding_bits": len(payload) * 8 - bits,
        "overhead_bytes": 82 + 2 * len(widths),
        "saved_bytes": len(original) - len(raw),
        "container_ratio_ppm": len(raw) * 1000000 // len(original) if original else None,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "container_sha256": hashlib.sha256(raw).hexdigest(),
        "symbols": len(widths),
        "maximum_code_length": max(widths.values(), default=0),
        "codebook": [
            {"symbol": symbol, "frequency": counts[symbol], "length": widths[symbol], "bits": spellings[symbol]}
            for symbol in sorted(widths)
        ],
    }


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "huffman-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "HUFFMAN_CONFIG": str(self.path),
            "HUFFMAN_MODE": mode,
            "HUFFMAN_FAIL": "",
            "HUFFMAN_PAUSE": "",
            "HUFFMAN_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, data: bytes, operation: str = "compress", **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"operation": operation, "input": "input.bin", "output": "huffman-result", **changes})
    (work / "input.bin").write_bytes(data)
    fix.save()
    return fix


def outputs(fix: Fixture, report: dict, content: bytes) -> dict:
    filename = "archive.phf" if fix.config["operation"] == "compress" else "decoded.bin"
    expected = {
        filename: content,
        "report.json": (canonical(report) + "\n").encode(),
        "codebook.json": (json.dumps(report["codebook"], ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(),
    }
    manifest = {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in expected.items()
        },
    }
    expected["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert actual == expected
    return actual


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    paths = [fix.path, fix.work / fix.config["input"]]
    unchanged = [path.read_bytes() for path in paths]
    source = unchanged[1]
    operation = fix.config["operation"]
    raw = reference_encode(source) if operation == "compress" else source
    original = source if operation == "compress" else reference_decode(raw)
    result = app.run(fix.work, fix.settings(mode), timeout=240)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert report == report_for(operation, original, raw), (fix.work, report)
    assert result.stdout == canonical(report) + "\n"
    assert unchanged == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report, raw if operation == "compress" else original)
        if operation == "compress":
            assert reference_decode((fix.output / "archive.phf").read_bytes()) == original
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".huffman-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=60)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".huffman-*"))
    return


def roundtrip(app: Application, directory: Path, name: str, data: bytes) -> dict:
    first = fixture(directory, name + "-encode", data)
    report = success(app, first)
    second = fixture(directory, name + "-decode", b"", "decompress", input=str(first.output / "archive.phf"))
    decoded = success(app, second)
    assert {**report, "operation": "decompress"} == decoded
    assert (second.output / "decoded.bin").read_bytes() == data
    return report


def scenarios(app: Application, directory: Path) -> dict:
    reports = []
    for length in range(5):
        for symbols in itertools.product([0, 127, 255], repeat=length):
            reports.append(roundtrip(app, directory, "sequence-" + str(len(reports)), bytes(symbols)))
    sequences = len(reports)
    for counts in itertools.product(range(5), repeat=3):
        data = b"".join(bytes([symbol]) * count for symbol, count in zip([1, 128, 254], counts, strict=True))
        report = roundtrip(app, directory, "histogram-" + str(len(reports)), data)
        weights = tuple(sorted(count for count in counts if count))
        assert report["payload_bits"] == (optimum(weights) if len(weights) > 1 else len(data))
        reports.append(report)
    print(app.engine + " Huffman: exhaustive byte sequences and optimal tiny histograms passed", flush=True)
    cases = [
        sample(),
        bytes(range(256)),
        bytes(range(255, -1, -1)),
        b"\x00",
        b"\xff" * 17,
        "Unicode: 🙂 Straße cafe\u0301\n".encode(),
    ]
    cases += [bytes([129]) * length for length in [7, 8, 9, 15, 16, 255, 256, 257]]
    randomizer = random.Random(68068)
    for i in range(40):
        alphabet = list(range(256)) if i % 2 else [0, 10, 127, 128, 255]
        cases.append(bytes(randomizer.choices(alphabet, k=randomizer.randint(0, 4096))))
    for i, data in enumerate(cases):
        reports.append(roundtrip(app, directory, "case-" + str(i), data))
    external = [
        (b"\x01" * 100 + b"\x00\x02", {0: 1, 1: 2, 2: 2}),
        (bytes(range(33)), {**{i: i + 1 for i in range(31)}, 31: 32, 32: 32}),
        (bytes(range(256)), dict.fromkeys(range(256), 8)),
    ]
    for i, (data, widths) in enumerate(external):
        raw = reference_encode(data, widths)
        fix = fixture(directory, "external-" + str(i), raw, "decompress")
        report = success(app, fix)
        assert (fix.output / "decoded.bin").read_bytes() == data
        reports.append(report)
    assert external[0][0] and len(reference_encode(*external[0])) > len(reference_encode(external[0][0]))
    return {
        "exhaustive_sequences": sequences,
        "exhaustive_histograms": 125,
        "other_roundtrips": len(cases),
        "generated_binary_files": 40,
        "external_codebooks": 3,
        "reports_sha256": hashlib.sha256(canonical(reports).encode()).hexdigest(),
    }


def malformed(app: Application, directory: Path) -> dict:
    golden = reference_encode(b"\x00\x01\x02\x02")
    for i in range(len(golden)):
        failure(app, fixture(directory, "cut-" + str(i), golden[:i], "decompress"))
        changed = bytearray(golden)
        changed[i] ^= 1
        failure(app, fixture(directory, "flip-" + str(i), bytes(changed), "decompress"))
    cases = [(golden + b"\x00", "length mismatch"), (golden + golden, "length mismatch")]
    for name, entries, expected in [
        ("zero", [(0, 0), (1, 2), (2, 1)], "invalid codebook"),
        ("above", [(0, 33), (1, 2), (2, 1)], "invalid codebook"),
        ("byte", [(0, 255), (1, 2), (2, 1)], "invalid codebook"),
        ("duplicate", [(0, 2), (0, 2), (2, 1)], "strictly increasing"),
        ("unsorted", [(2, 1), (0, 2), (1, 2)], "strictly increasing"),
        ("oversubscribed", [(0, 1), (1, 1), (2, 1)], "oversubscribed"),
        ("incomplete", [(0, 2), (1, 2), (2, 2)], "incomplete"),
    ]:
        raw = assemble(4, 6, entries, b"\x00", hashlib.sha256(b"\x00\x01\x02\x02").digest())
        failure(app, fixture(directory, "book-" + name, raw, "decompress"), expected)
    empty_digest = hashlib.sha256(b"").digest()
    cases += [
        (assemble(0, 0, [], b"", b"\x00" * 32), "decoded checksum"),
        (assemble(0, 0, [(0, 1)], b"", empty_digest), "symbol count"),
        (assemble(1, 1, [], b"\x00", empty_digest), "missing codebook"),
        (assemble(257, 257, [], b"", empty_digest, count=257), "symbol count"),
        (assemble(1, 1, [(0, 1), (1, 1)], b"\x00", empty_digest), "symbol count"),
        (assemble(1048577, 1048577, [(0, 1)], b"", empty_digest), "declared output"),
        (assemble(4, 3, [(0, 1)], b"\x00", empty_digest), "bit count"),
        (assemble(4, 129, [(0, 1)], b"\x00" * 17, empty_digest), "bit count"),
        (assemble(2, 2, [(0, 1), (1, 1)], b"\x00", hashlib.sha256(b"\x00\x00").digest()), "unused codebook"),
        (assemble(3, 6, [(0, 1), (1, 1)], b"\x54", empty_digest), "exceeds declared length"),
        (assemble(4, 5, [(0, 1), (1, 2), (2, 2)], b"\x58", empty_digest), "decoded length mismatch"),
        (assemble(3, 4, [(0, 1), (1, 2), (2, 2)], b"\x50", empty_digest), "unfinished payload"),
        (assemble(1, 1, [(0, 1)], b"\x80", empty_digest), "invalid payload code"),
        (assemble(1, 1, [(0, 1)], b"\x01", empty_digest), "padding bits"),
        (assemble(1, 2, [(0, 2)], b"\x00", empty_digest), "single-symbol code"),
        (assemble(1, 32, [(0, 32)], b"\x00" * 4, empty_digest), "single-symbol code"),
        (assemble(1, 1, [(0, 1)], b"\x00", empty_digest), "decoded checksum"),
    ]
    for i, (raw, message) in enumerate(cases):
        failure(app, fixture(directory, "semantic-" + str(i), raw, "decompress"), message)
    return {
        "every_byte_truncation": len(golden),
        "every_byte_corruption": len(golden),
        "resigned_codebooks": 7,
        "other_malformed_containers": len(cases),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    count = 0
    for key in ["input", "output"]:
        for i, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{i}", sample())
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
    for i, value in enumerate(["", "encode", "DECOMPRESS", None, True, 1, [], {}]):
        fix = fixture(directory, "operation-" + str(i), sample())
        fix.path.write_text(json.dumps({**fix.config, "operation": value}))
        failure(app, fix)
        count += 1
    for key in ["input", "operation", "output"]:
        fix = fixture(directory, "missing-" + key, sample())
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", sample())
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", sample()), "invalid Huffman mode", HUFFMAN_MODE="bad")
    count += 2
    for i, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
        fix = fixture(directory, "raw-" + str(i), sample())
        fix.path.write_bytes(raw)
        failure(app, fix)
        count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    for name, data in [("maximum-single", b"\x00" * 1048576), ("maximum-uniform", bytes(range(256)) * 4096)]:
        report = roundtrip(app, directory, name, data)
        assert report["original_bytes"] == 1048576
    failure(app, fixture(directory, "original-above", b"\x00" * 1048577), "byte limit")
    weights = [1, 1]
    while len(weights) < 28:
        weights.append(weights[-1] + weights[-2])
    skewed = b"".join(bytes([i]) * weight for i, weight in enumerate(weights))
    report = roundtrip(app, directory, "fibonacci-depth", skewed)
    assert report["maximum_code_length"] == 27 and len(skewed) == 832039
    fix = fixture(directory, "config-bytes", sample())
    raw = fix.path.read_bytes()
    fix.path.write_bytes(raw + b" " * (65536 - len(raw)))
    success(app, fix, "preview")
    fix.path.write_bytes(raw + b" " * (65537 - len(raw)))
    failure(app, fix, "byte limit")
    fix.path.write_bytes(raw)
    fix = fixture(directory, "container-read-exact", b"\x00" * 4194898, "decompress")
    failure(app, fix, "container magic")
    (fix.work / "input.bin").write_bytes(b"\x00" * 4194899)
    failure(app, fix, "byte limit")
    return {
        "original_bytes": 1048576,
        "container_read_bytes": 4194898,
        "config_bytes": 65536,
        "symbols": 256,
        "accepted_external_code_length": 32,
        "generated_code_depth": 27,
        "skewed_input_bytes": 832039,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(HUFFMAN_PAUSE="ready", HUFFMAN_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    count = 0
    for operation in ["compress", "decompress"]:
        raw = sample() if operation == "compress" else reference_encode(sample())
        content = reference_encode(sample()) if operation == "compress" else sample()
        filename = "archive.phf" if operation == "compress" else "decoded.bin"
        points = ["validated", "stage", filename, "report.json", "codebook.json", "manifest.json", "ready", "published"]
        for point in points:
            fix = fixture(directory / operation, "fault-" + point, raw, operation)
            reference = success(app, fix, "preview")
            result = app.run(fix.work, fix.settings(HUFFMAN_FAIL=point))
            assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
            assert not list(fix.work.glob(".huffman-*"))
            if point == "published":
                outputs(fix, reference, content)
            else:
                assert not fix.output.exists()
                success(app, fix)
        for name in ["input", "config", "destination"]:
            fix = fixture(directory / operation, "changed-" + name, raw, operation)
            process = paused(app, fix)
            try:
                if name == "destination":
                    fix.output.mkdir()
                    (fix.output / "keep").write_bytes(b"another writer")
                else:
                    path = fix.path if name == "config" else fix.work / fix.config[name]
                    with path.open("ab") as stream:
                        stream.write(b" ")
                (fix.work / "continue").touch()
                output, error = process.communicate(timeout=20)
                assert process.returncode == 2 and error and not output
                assert not list(fix.work.glob(".huffman-*"))
                if name == "destination":
                    assert list(fix.output.iterdir()) == [fix.output / "keep"]
                    assert (fix.output / "keep").read_bytes() == b"another writer"
                else:
                    assert "input changed before publication" in error and not fix.output.exists()
            finally:
                stop(process)
        fix = fixture(directory / operation, "killed", raw, operation)
        reference = success(app, fix, "preview")
        process = paused(app, fix)
        stop(process)
        assert not fix.output.exists()
        abandoned = list(fix.work.glob(".huffman-*"))
        assert len(abandoned) == 1
        old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 0 and not result.stderr
        outputs(fix, reference, content)
        assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
        count += len(points) + 4
    return count


def paths(app: Application, directory: Path) -> int:
    for operation in ["compress", "decompress"]:
        raw = sample() if operation == "compress" else reference_encode(sample())
        for name in ["file", "directory", "symlink", "dangling", "input.bin", "huffman-job.json"]:
            fix = fixture(directory / operation, "destination-" + name, raw, operation)
            if name == "file":
                fix.output.write_bytes(b"preserve")
            elif name == "directory":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"preserve")
            elif name in ["symlink", "dangling"]:
                fix.output.symlink_to(fix.work / ("input.bin" if name == "symlink" else "missing"))
            else:
                fix.config["output"] = name
                fix.save()
            failure(app, fix, "output directory already exists")
        for name in ["input.bin", "huffman-job.json"]:
            fix = fixture(directory / operation, "symlink-" + name, raw, operation)
            path = fix.work / name
            path.rename(fix.work / "original")
            path.symlink_to(fix.work / "original")
            original = (fix.work / "original").read_bytes()
            failure(app, fix, "regular file")
            assert path.is_symlink() and (fix.work / "original").read_bytes() == original
        fix = fixture(directory / operation, "readonly", raw, operation)
        parent = fix.work / "readonly"
        parent.mkdir()
        fix.config["output"] = "readonly/result"
        fix.save()
        parent.chmod(0o500)
        try:
            failure(app, fix)
            assert not list(parent.iterdir())
        finally:
            parent.chmod(0o700)
    return 18


def check(app: Application, directory: Path) -> dict:
    cases = scenarios(app, directory / "scenarios")
    print(app.engine + " Huffman: exact bytes, round trips and external codebooks passed", flush=True)
    damaged = malformed(app, directory / "malformed")
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " Huffman: corruption, validation, limits and publication checks passed", flush=True)
    return {
        **cases,
        "malformed_containers": damaged,
        "invalid_inputs": invalid,
        "limits": bounds,
        "publication_cases": faults,
        "path_cases": path_cases,
    }
