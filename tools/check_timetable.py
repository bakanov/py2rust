"""Reuse exported timetables and replan changed transfer times and services across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.timetable import connection, fixture, jobs, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample(), jobs())
    original = success(writer, first)
    assert original["counts"] == {"requests": 5, "found": 3, "unreachable": 2}
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(
        directory,
        "second",
        {},
        [],
        timetable=str(first.output / "timetable.json"),
        requests=str(first.output / "requests.json"),
    )
    assert success(updater, second) == original
    third = fixture(
        directory,
        "third",
        {},
        [],
        timetable=str(second.output / "timetable.json"),
        requests=str(second.output / "requests.json"),
    )
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    value = json.loads((third.output / "timetable.json").read_bytes())
    rows = json.loads((third.output / "requests.json").read_bytes())
    next(station for station in value["stations"] if station["id"] == "B")["transfer_seconds"] = 0
    value["connections"].append(
        connection("island-ferry", "D", "Island", "2026-10-13T01:10:00Z", "2026-10-13T01:20:00Z")
    )
    edited = fixture(directory, "edited", value, rows)
    changed = success(updater, edited)
    assert changed["counts"] == {"requests": 5, "found": 4, "unreachable": 1}
    assert changed["journeys"][0]["arrival"] == "2026-10-13T01:00:00.000000+00:00"
    assert [leg["id"] for leg in changed["journeys"][0]["legs"]] == ["ab", "bc-missed", "cd-missed"]
    assert changed["journeys"][3]["arrival"] == "2026-10-13T01:20:00.000000+00:00"
    final = fixture(
        directory,
        "final",
        {},
        [],
        timetable=str(edited.output / "timetable.json"),
        requests=str(edited.output / "requests.json"),
    )
    assert success(reader, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "journeys_sha256": hashlib.sha256(files["journeys.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "journeys.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "transfer_and_service_edits": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "069")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "069/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"069": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "timetable"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "069/corpus_069")], "rust"),
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
                print(name + " timetable exports, transfer edits, new services and replanning: passed", flush=True)
    for field in ["journeys_sha256", "edited_sha256"]:
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
