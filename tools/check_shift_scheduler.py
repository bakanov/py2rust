"""Re-solve actual staffing exports across Python/Rust, including limits and changed availability."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.shift_scheduler import fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    value = sample()
    for person in value["workers"]:
        person["availability"] = [{"start": 60, "end": 10080}, {"start": 0, "end": 60}]
        person["skills"] = ["support", "support"]
    first = fixture(directory, "first", value)
    original = success(writer, first)
    assert original["status"] == "optimal" and original["score"] == 7
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, problem=str(first.output / "problem.json"))
    assert success(updater, second) == original
    third = fixture(directory, "third", {}, problem=str(second.output / "problem.json"))
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    limited_value = json.loads((third.output / "problem.json").read_bytes())
    limited_value["budget"] = 1
    limited = fixture(directory, "limited", limited_value)
    incomplete = success(reader, limited)
    assert incomplete["status"] == "search_limit" and incomplete["schedule"] == []
    expanded_value = json.loads((limited.output / "problem.json").read_bytes())
    expanded_value["budget"] = 100000
    expanded = fixture(directory, "expanded", expanded_value)
    assert success(writer, expanded) == original
    assert files == {path.name: path.read_bytes() for path in expanded.output.iterdir()}
    changed_value = json.loads((expanded.output / "problem.json").read_bytes())
    next(person for person in changed_value["workers"] if person["id"] == "Chen")["availability"] = []
    changed = fixture(directory, "changed", changed_value)
    final = success(updater, changed)
    assert final["status"] == "optimal" and final["score"] == 12
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "schedule_sha256": hashlib.sha256(files["schedule.json"]).hexdigest(),
        "limited_sha256": hashlib.sha256((limited.output / "schedule.json").read_bytes()).hexdigest(),
        "changed_sha256": hashlib.sha256((changed.output / "schedule.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "063")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "063/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"063": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "shift-scheduler"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "063/corpus_063")], "rust"),
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
                print(name + " staffing export/budget/replanning: passed", flush=True)
    for field in ["schedule_sha256", "limited_sha256", "changed_sha256"]:
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
