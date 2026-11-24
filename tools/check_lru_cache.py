"""Resume actual ordered cache snapshots in every Python/Rust writer/updater/reader combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.lru_cache import command, fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    trace = sample()
    trace.insert(2, command("GET", "b"))
    first = fixture(directory, "first", trace[:2])
    initial = success(writer, first)
    first_bytes = (first.output / "state.json").read_bytes()
    second = fixture(
        directory, "second", trace[2:14], initial[0]["state"]["capacity"], state=str(first.output / "state.json")
    )
    middle = success(updater, second)
    assert middle[1][0]["hit"] and middle[1][0]["value"] is None
    assert middle[0]["state"]["capacity"] == 0
    middle_bytes = (second.output / "state.json").read_bytes()
    third = fixture(
        directory, "third", trace[14:], middle[0]["state"]["capacity"], state=str(second.output / "state.json")
    )
    result = success(reader, third)
    whole = fixture(directory, "whole", trace)
    expected = success(reader, whole)
    assert result[0] == expected[0]
    assert (third.output / "state.json").read_bytes() == (whole.output / "state.json").read_bytes()
    events = b"".join((fix.output / "events.jsonl").read_bytes() for fix in [first, second, third])
    assert events == (whole.output / "events.jsonl").read_bytes()
    assert (first.output / "state.json").read_bytes() == first_bytes
    assert (second.output / "state.json").read_bytes() == middle_bytes
    # A miss/hit after restoration must continue cumulative counters and preserve null-versus-missing semantics.
    fourth = fixture(
        directory,
        "inspect",
        [command("GET", "x"), command("GET", "absent"), command("INSPECT")],
        result[0]["state"]["capacity"],
        state=str(third.output / "state.json"),
    )
    observed = success(writer, fourth)
    assert observed[0]["state"]["stats"]["steps"] == len(trace) + 3
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "steps": len(trace),
        "state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(events).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "051")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "051/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"051": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "lru-cache"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "051/corpus_051")], "rust"),
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
                print(name + " cache save/resume/read: passed", flush=True)
    assert (
        len({row["state_sha256"] for row in observations}) == len({row["events_sha256"] for row in observations}) == 1
    )
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
