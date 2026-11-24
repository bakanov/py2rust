"""Consume actual generated and resolved scheduler bundles across three runtime processes."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.scheduler_simulator import Fixture, fixture, generated, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path, resolved: bool = False) -> Fixture:
    directory.mkdir(parents=True)
    filename = "resolved-job.json" if resolved else "scheduler-job.json"
    shutil.copyfile(previous.output / filename, directory / filename)
    return Fixture(directory, json.loads((directory / filename).read_bytes()), filename)


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory / "first", workers=4, capacity=6, generated=generated(88444, 160))
    original, files = run(writer, first)
    second = consume(first, directory / "second")
    repeated, exported = run(replayer, second)
    assert repeated == original and exported == files
    third = consume(second, directory / "third", resolved=True)
    explicit, resolved = run(reader, third)
    assert dict(explicit, generator=original["generator"]) == original
    assert explicit["generator"] == {"algorithm": "none", "seed": 0, "state": 0, "draws": 0}
    for filename in ["jobs.json", "trace.jsonl", "resolved-job.json"]:
        assert resolved[filename] == files[filename]
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_generated_and_resolved_configs_consumed": True,
        "generated_bundle_byte_identical": True,
        "resolved_explicit_trace_identical": True,
        "original_bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
        "resolved_bundle_sha256": hashlib.sha256(b"".join(resolved[name] for name in sorted(resolved))).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "088")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "088/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"088": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "scheduler-simulator"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "088/corpus_088")], "rust"),
    ]
    observations = []
    for writer in apps:
        for replayer in apps:
            for reader in apps:
                name = f"{writer.engine}-{replayer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, replayer, reader, work))
                print(name + " scheduler replay: passed", flush=True)
    assert len({(row["original_bundle_sha256"], row["resolved_bundle_sha256"]) for row in observations}) == 1
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
