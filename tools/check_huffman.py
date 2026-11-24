"""Compress, decode and recompress real exported containers across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.huffman import fixture, reference_encode, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, decoder: Application, reencoder: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first)
    assert original["original_bytes"] == 4096 and original["container_bytes"] == 2122
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", b"", "decompress", input=str(first.output / "archive.phf"))
    assert success(decoder, second) == {**original, "operation": "decompress"}
    assert (second.output / "decoded.bin").read_bytes() == sample()
    third = fixture(directory, "third", b"", input=str(second.output / "decoded.bin"))
    assert success(reencoder, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    external_data = b"\x01" * 100 + b"\x00\x02"
    external = fixture(directory, "external", reference_encode(external_data, {0: 1, 1: 2, 2: 2}), "decompress")
    imported = success(decoder, external)
    optimized = fixture(directory, "optimized", b"", input=str(external.output / "decoded.bin"))
    smaller = success(reencoder, optimized)
    assert smaller["payload_bits"] < imported["payload_bits"]
    final = fixture(directory, "final", b"", "decompress", input=str(optimized.output / "archive.phf"))
    assert success(writer, final) == {**smaller, "operation": "decompress"}
    assert (final.output / "decoded.bin").read_bytes() == external_data
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "decoder": decoder.engine,
        "reencoder": reencoder.engine,
        "archive_sha256": hashlib.sha256(files["archive.phf"]).hexdigest(),
        "optimized_sha256": hashlib.sha256((optimized.output / "archive.phf").read_bytes()).hexdigest(),
        "actual_archive_and_decoded_paths": True,
        "external_nonoptimal_codebook": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "068")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "068/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"068": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "huffman"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "068/corpus_068")], "rust"),
    ]
    observations = []
    for writer in apps:
        for decoder in apps:
            for reencoder in apps:
                name = f"{writer.engine}-{decoder.engine}-{reencoder.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, decoder, reencoder, work))
                print(
                    name + " archive decode, byte-identical recompression and external codebook import: passed",
                    flush=True,
                )
    for field in ["archive_sha256", "optimized_sha256"]:
        assert len({row[field] for row in observations}) == 1
    assert fingerprint(program) == current
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": fingerprints,
                "checker_sha256": checker_hash,
                "observations": observations,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
