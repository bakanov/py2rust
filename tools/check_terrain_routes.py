"""Replan actual terrain exports and edit exported costs/maps across Python and Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.terrain_routes import Fixture, fixture, jobs, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exported(directory: Path, name: str, source: Path) -> Fixture:
    fix = fixture(directory, name, "", {}, [])
    fix.config.update(
        {
            key: str(source / filename)
            for key, filename in [("grid", "grid.txt"), ("terrain", "terrain.json"), ("requests", "requests.json")]
        }
    )
    fix.save()
    return fix


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample(), {".": 1, "~": 5}, jobs())
    original = success(writer, first)
    assert original["counts"] == {"found": 3, "unreachable": 1, "blocked": 1}
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = exported(directory, "second", first.output)
    assert success(updater, second) == original
    third = exported(directory, "third", second.output)
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    exported_grid = (third.output / "grid.txt").read_text().splitlines()
    exported_costs = json.loads((third.output / "terrain.json").read_bytes())["costs"]
    exported_requests = json.loads((third.output / "requests.json").read_bytes())
    exported_costs["~"] = 0
    # Open the blocked start and join the formerly disconnected lower component.
    exported_grid[1] = "." * len(exported_grid[1])
    exported_grid[6] = "." + exported_grid[6][1:]
    edited = fixture(directory, "edited", "\n".join(exported_grid) + "\n", exported_costs, exported_requests)
    changed = success(updater, edited)
    assert changed["counts"] == {"found": 5, "unreachable": 0, "blocked": 0}
    assert changed["routes"][1]["cost"] < original["routes"][1]["cost"]
    final = exported(directory, "final", edited.output)
    assert success(reader, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "routes_sha256": hashlib.sha256(files["routes.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "routes.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "edited_exported_grid_and_costs": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "065")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "065/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"065": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "terrain-routes"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "065/corpus_065")], "rust"),
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
                print(name + " terrain exports, map/cost edits and replanning: passed", flush=True)
    for field in ["routes_sha256", "edited_sha256"]:
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
