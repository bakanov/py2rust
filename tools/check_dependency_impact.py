"""Reuse actual graph exports and audit dependency edits across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.dependency_impact import fixture, jobs, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample(), jobs())
    original = success(writer, first)
    assert original["structure"]["counts"] == {"modules": 8, "edges": 8, "groups": 7, "cyclic_groups": 2}
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(
        directory,
        "second",
        {},
        [],
        graph=str(first.output / "graph.json"),
        requests=str(first.output / "requests.json"),
    )
    assert success(updater, second) == original
    third = fixture(
        directory,
        "third",
        {},
        [],
        graph=str(second.output / "graph.json"),
        requests=str(second.output / "requests.json"),
    )
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    value = json.loads((third.output / "graph.json").read_bytes())
    rows = json.loads((third.output / "requests.json").read_bytes())
    value["modules"].append("worker")
    value["edges"] = [
        e for e in value["edges"] if (e["module"], e["depends_on"]) not in [("auth", "models"), ("tools", "tools")]
    ]
    value["edges"] += [{"module": "worker", "depends_on": "app"}, {"module": "unused", "depends_on": "db"}]
    edited = fixture(directory, "edited", value, rows)
    changed = success(updater, edited)
    assert changed["structure"]["counts"] == {"modules": 9, "edges": 8, "groups": 9, "cyclic_groups": 0}
    assert changed["impacts"][0]["unaffected"] == ["auth", "tools"]
    assert changed["impacts"][0]["affected"] == ["api", "app", "cache", "db", "models", "unused", "worker"]
    final = fixture(
        directory,
        "final",
        {},
        [],
        graph=str(edited.output / "graph.json"),
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
        "impact_sha256": hashlib.sha256(files["impact.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "impact.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "split_cycles_and_new_dependents": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "066")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "066/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"066": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "dependency-impact"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "066/corpus_066")], "rust"),
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
                print(name + " graph exports, cycle splits and new dependent impacts: passed", flush=True)
    for field in ["impact_sha256", "edited_sha256"]:
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
