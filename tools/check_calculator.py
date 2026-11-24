"""Replay, update and reload actual saved calculator sessions across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.calculator import fixture, sample, success
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", *sample())
    original = success(writer, first)
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    replay = fixture(
        directory,
        "replay",
        {},
        b"",
        state=str(first.output / "initial-state.json"),
    )
    replay.config["script"] = str(first.output / "script.txt")
    replay.save()
    assert success(updater, replay) == original
    assert files == {path.name: path.read_bytes() for path in replay.output.iterdir()}
    changes = b"quantity = quantity + 1\ntotal = price * quantity\nbad = 1 / 0\nsplit = total / quantity\n"
    changed = fixture(directory, "changed", {}, changes, state=str(replay.output / "state.json"))
    report = success(updater, changed)
    assert report["errors"] == 1 and report["variables"] == {
        "quantity": 5,
        "price": 12.5,
        "total": 62.5,
        "split": 12.5,
        "adjusted": -26.0,
    }
    loaded = fixture(directory, "loaded", {}, b"total\nquantity\nsplit\n", state=str(changed.output / "state.json"))
    read = success(reader, loaded)
    assert read["errors"] == 0 and read["variables"] == report["variables"]
    assert [row["value"] for row in read["records"]] == [62.5, 5, 12.5]
    final = fixture(
        directory,
        "final",
        {},
        b"",
        state=str(changed.output / "initial-state.json"),
    )
    final.config["script"] = str(changed.output / "script.txt")
    final.save()
    assert success(reader, final) == report
    assert {path.name: path.read_bytes() for path in final.output.iterdir()} == {
        path.name: path.read_bytes() for path in changed.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "initial_state_sha256": hashlib.sha256(files["state.json"]).hexdigest(),
        "updated_state_sha256": hashlib.sha256((changed.output / "state.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "failed_assignment_preserved_session": True,
        "replayed_bundles_identical": True,
        "earlier_bundles_unchanged": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "074")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "074/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"074": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "calculator"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "074/corpus_074")], "rust"),
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
                print(name + " calculator replay, saved-session update and recovery: passed", flush=True)
    for field in ["initial_state_sha256", "updated_state_sha256"]:
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
