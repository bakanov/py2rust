"""Reuse exported Sudoku batches, apply solution witnesses and change budgets across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.sudoku import fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first)
    assert original["counts"] == {"unique": 2, "multiple": 1, "invalid": 1, "search_limit": 1, "unsatisfiable": 1}
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, boards=str(first.output / "boards.json"))
    assert success(updater, second) == original
    third = fixture(directory, "third", {}, boards=str(second.output / "boards.json"))
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    value = json.loads((third.output / "boards.json").read_bytes())
    by_id = {row["id"]: row for row in value["boards"]}
    results = {row["id"]: row for row in original["results"]}
    by_id["multiple"]["rows"] = results["multiple"]["solutions"][0]
    by_id["invalid"]["rows"] = results["unique"]["solutions"][0]
    by_id["limited"]["budget"] = 1000
    edited = fixture(directory, "edited", value)
    changed = success(updater, edited)
    assert changed["counts"] == {"unique": 4, "multiple": 1, "invalid": 0, "search_limit": 0, "unsatisfiable": 1}
    final = fixture(directory, "final", {}, boards=str(edited.output / "boards.json"))
    assert success(reader, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "results_sha256": hashlib.sha256(files["results.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "results.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "solution_and_budget_edits": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "070")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "070/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"070": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "sudoku"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "070/corpus_070")], "rust"),
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
                print(
                    name + " sudoku exports, solution witnesses, budget edits and repeated solving: passed", flush=True
                )
    for field in ["results_sha256", "edited_sha256"]:
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
