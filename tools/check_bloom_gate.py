"""Persist and resume audited Bloom filters across all Python/Rust writer, updater and reader combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.bloom_gate import command, fixture, success
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    trace = [
        command("INGEST", "first"),
        command("INGEST", "世界"),
        command("CHECK", "missing"),
        command("INGEST", "second"),
        command("INGEST", "first"),
        command("INGEST", "overflow"),
        command("CHECK", "世界"),
        command("CHECK", "absent"),
        {"op": "EXPORT"},
        {"op": "INSPECT"},
    ]
    settings = {"expected": 1, "probability_ppm": 999999, "capacity": 3}
    first = fixture(directory, "first", trace[:2], **settings)
    success(writer, first)
    first_bytes = (first.output / "state.json").read_bytes()
    second = fixture(directory, "second", trace[2:6], state=str(first.output / "state.json"), **settings)
    middle = success(updater, second)
    assert middle[1][0]["false_positive"] and middle[1][1]["decision"] == "accepted"
    assert middle[1][2]["decision"] == "duplicate" and middle[1][3]["decision"] == "refused"
    second_bytes = (second.output / "state.json").read_bytes()
    third = fixture(directory, "third", trace[6:], state=str(second.output / "state.json"), **settings)
    observed = success(reader, third)
    whole = fixture(directory, "whole", trace, **settings)
    expected = success(reader, whole)
    assert observed[0] == expected[0]
    for name in ["state.json", "filter.bin", "keys.json"]:
        assert (third.output / name).read_bytes() == (whole.output / name).read_bytes()
    events = b"".join((fix.output / "events.jsonl").read_bytes() for fix in [first, second, third])
    assert events == (whole.output / "events.jsonl").read_bytes()
    assert (first.output / "state.json").read_bytes() == first_bytes
    assert (second.output / "state.json").read_bytes() == second_bytes
    fourth = fixture(
        directory,
        "resumed",
        [command("CHECK", key) for key in ["first", "世界", "second"]],
        state=str(third.output / "state.json"),
        **settings,
    )
    final = success(writer, fourth)
    assert all(
        event["exact_duplicate"] and event["likely_duplicate"] and not event["false_positive"] for event in final[1]
    )
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
        "bits_sha256": hashlib.sha256((third.output / "filter.bin").read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(events).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "056")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "056/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"056": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "bloom-gate"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "056/corpus_056")], "rust"),
    ]
    observations = []
    for writer in apps:
        for updater in apps:
            for reader in apps:
                name = f"{writer.engine}-{updater.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, updater, reader, work))
                print(name + " Bloom ingestion/save/check: passed", flush=True)
    for field in ["state_sha256", "bits_sha256", "events_sha256"]:
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
