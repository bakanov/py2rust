"""Replan real exports and repack actual rejected item manifests across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical
from corpus_checks.parcel_planner import box, fixture, problem, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first)
    assert original["totals"]["assigned"] == 4 and original["totals"]["rejected"] == 3
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, problem=str(first.output / "problem.json"))
    assert success(updater, second) == original
    third = fixture(directory, "third", {}, problem=str(second.output / "problem.json"))
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    leftovers = [json.loads(line)["item"] for line in (third.output / "rejected.jsonl").read_bytes().splitlines()]
    replenished = fixture(
        directory,
        "replenished",
        problem(leftovers, [box("freight", 30, 100, tare_g=1, cost_cents=300, stock=3, item_limit=5)], 3),
    )
    recovered = success(reader, replenished)
    assert recovered["status"] == "complete" and recovered["totals"]["assigned"] == 3
    assert len(recovered["packages"]) == 3
    combined = [row["id"] for parcel in original["packages"] + recovered["packages"] for row in parcel["items"]]
    assert len(combined) == len(set(combined)) and sorted(combined) == ["a", "b", "c", "d", "e", "f", "g"]
    final = fixture(directory, "final", {}, problem=str(replenished.output / "problem.json"))
    assert success(writer, final) == recovered
    assert {path.name: path.read_bytes() for path in replenished.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "plan_sha256": hashlib.sha256(files["plan.json"]).hexdigest(),
        "replenished_sha256": hashlib.sha256((final.output / "plan.json").read_bytes()).hexdigest(),
        "combined_ids_sha256": hashlib.sha256(canonical(sorted(combined)).encode()).hexdigest(),
        "actual_export_paths": True,
        "actual_rejected_manifests": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "064")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "064/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"064": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "parcel-planner"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "064/corpus_064")], "rust"),
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
                print(name + " package export/replanning/rejected-item recovery: passed", flush=True)
    for field in ["plan_sha256", "replenished_sha256", "combined_ids_sha256"]:
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
