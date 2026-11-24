"""Resume actual ring snapshots across all Python/Rust writer, updater and reader combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.ring_recorder import command, fixture, ingest, interval, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    initial = [ingest(index // 3, index / 8) for index in range(10)]
    middle = [ingest(3, 42.0), command("ADVANCE", time_ms=13), ingest(13, -1e9), command("INSPECT")]
    final = [
        ingest(13, 1e-9),
        ingest(13, 1e9),
        interval("SUMMARY", 13, 13),
        command("ADVANCE", time_ms=23),
        interval("EXPORT", 0, 23),
        command("ADVANCE", time_ms=24),
        command("INSPECT"),
    ]
    first = fixture(directory, "first", initial, capacity=4, window_ms=10)
    success(writer, first)
    first_bytes = (first.output / "state.json").read_bytes()
    second = fixture(directory, "second", middle, state=str(first.output / "state.json"), capacity=4, window_ms=10)
    success(updater, second)
    second_bytes = (second.output / "state.json").read_bytes()
    third = fixture(directory, "third", final, state=str(second.output / "state.json"), capacity=4, window_ms=10)
    observed = success(reader, third)
    assert observed[1][2]["summary"]["sum"] == 1e-9
    assert observed[1][3]["expired"] == 1 and len(observed[1][4]["samples"]) == 3
    assert observed[1][5]["expired"] == 3 and observed[0]["state"]["samples"] == []
    whole = fixture(directory, "whole", initial + middle + final, capacity=4, window_ms=10)
    expected = success(reader, whole)
    assert observed[0] == expected[0]
    for name in ["state.json", "window.jsonl"]:
        assert (third.output / name).read_bytes() == (whole.output / name).read_bytes()
    events = b"".join((fix.output / "events.jsonl").read_bytes() for fix in [first, second, third])
    assert events == (whole.output / "events.jsonl").read_bytes()
    assert (first.output / "state.json").read_bytes() == first_bytes
    assert (second.output / "state.json").read_bytes() == second_bytes
    resumed = fixture(
        directory,
        "resumed",
        [ingest(24, 0.1), interval("EXPORT", 24, 24)],
        state=str(third.output / "state.json"),
        capacity=4,
        window_ms=10,
    )
    after = success(writer, resumed)
    assert len(after[0]["state"]["samples"]) == 1 and after[0]["state"]["samples"][0]["value"] == 0.1
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(events).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "058")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "058/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"058": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "ring-recorder"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "058/corpus_058")], "rust"),
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
                print(name + " ring save/resume/export: passed", flush=True)
    for field in ["state_sha256", "events_sha256"]:
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
