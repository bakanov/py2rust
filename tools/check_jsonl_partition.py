"""Repartition actual saved shard files across every Python/Rust writer-reader pair."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical
from corpus_checks.jsonl_partition import data, fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, reader: Application, directory: Path) -> dict:
    rows = [*sample(), sample()[0], sample()[0]]
    original = fixture(directory, "writer", data(rows, "\r\n", False))
    manifest = success(writer, original)
    observed = []
    total = 0
    before = {path.name: path.read_bytes() for path in original.output.iterdir()}
    for number, shard in enumerate(manifest["shards"]):
        source = original.output / shard["file"]
        repeated = fixture(directory, f"reader-{number}", b"", input=str(source))
        result = success(reader, repeated)
        assert len(result["shards"]) == 1
        restored = result["shards"][0]
        for field in ["file", "date", "topic", "rows", "bytes", "sha256"]:
            assert restored[field] == shard[field]
        assert (repeated.output / restored["file"]).read_bytes() == source.read_bytes()
        assert result["input_sha256"] == shard["sha256"]
        total += result["rows"]
        observed.append({"file": restored["file"], "rows": restored["rows"], "sha256": restored["sha256"]})
    assert total == len(rows)
    assert {path.name: path.read_bytes() for path in original.output.iterdir()} == before
    return {
        "writer": writer.engine,
        "reader": reader.engine,
        "records": total,
        "shards": len(observed),
        "shards_sha256": hashlib.sha256(canonical(observed).encode()).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "050")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "050/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"050": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "jsonl-partition"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "050/corpus_050")], "rust"),
    ]
    observations = []
    for writer in apps:
        for reader in apps:
            name = writer.engine + "-" + reader.engine
            work = directory / name
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(writer, reader, work))
            print(name + " partition/repartition: passed", flush=True)
    assert len({row["shards_sha256"] for row in observations}) == 1
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
