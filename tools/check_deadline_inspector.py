"""Replay actual exported deadline inputs across Python/Rust producer and inspector processes."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.deadline_inspector import Fixture, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path, advance: bool = False) -> Fixture:
    directory.mkdir(parents=True)
    config = json.loads((previous.output / "deadline-job.json").read_bytes())
    config["output"] = "output"
    if advance:
        config["observed_at"] = "2024-03-01T05:00:00.000001+05:00"
    for name in ["jobs.json", "events.json"]:
        shutil.copyfile(previous.output / name, directory / name)
    (directory / "job.json").write_text(json.dumps(config))
    return Fixture(
        directory,
        config,
        json.loads((directory / "jobs.json").read_bytes()),
        json.loads((directory / "events.json").read_bytes()),
    )


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory / "first")
    original, files = run(writer, first)
    second = consume(first, directory / "second")
    transformed, exported = run(replayer, second)
    assert original == transformed and files == exported
    third = consume(second, directory / "third", advance=True)
    advanced, later = run(reader, third)
    assert advanced["counts"] == {"on_time": 4, "late": 2, "missing": 2, "pending": 0}
    assert advanced["future_events"] == 0 and advanced["duplicate_events"] == 2
    assert advanced["jobs"][-1]["lateness_us"] == 1
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_exported_jobs_and_events_consumed": True,
        "same_observation_identical_bundle": True,
        "future_event_activated_at_exact_microsecond": True,
        "original_bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
        "advanced_bundle_sha256": hashlib.sha256(b"".join(later[name] for name in sorted(later))).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "085")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "085/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"085": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "deadline-inspector"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "085/corpus_085")], "rust"),
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
                print(name + " exported deadline replay: passed", flush=True)
    assert len({(row["original_bundle_sha256"], row["advanced_bundle_sha256"]) for row in observations}) == 1
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
