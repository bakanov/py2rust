"""Replay actual exported TZif bytes through every Python/Rust producer and consumer combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.timezone_converter import Fixture, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path, revise: bool = False) -> Fixture:
    directory.mkdir(parents=True)
    config = json.loads((previous.output / "timezone-job.json").read_bytes())
    config["output"] = "output"
    if revise:
        config["targets"].reverse()
        for item in config["appointments"]:
            item["ambiguity"] = "later"
            item["gap"] = "shift_backward"
    shutil.copyfile(previous.output / "zones.json", directory / "zones.json")
    result = Fixture(directory, config)
    result.write()
    return result


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory / "first")
    original, files = run(writer, first)
    shutil.rmtree(first.root / "tzdata")
    second = consume(first, directory / "second")
    transformed, exported = run(replayer, second)
    assert original == transformed and files == exported
    third = consume(second, directory / "third", revise=True)
    revised, later = run(reader, third)
    assert revised["counts"] == {"converted": 36, "rejected": 0, "invalid": 1}
    assert revised["tzif_sha256"] == original["tzif_sha256"]
    assert revised["appointments"][2]["selected"]["utc"] == "2024-11-03T06:30:00.123456+00:00"
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_exported_tzif_consumed": True,
        "original_timezone_directory_removed": True,
        "same_inputs_identical_bundle": True,
        "revised_selection_and_target_order": True,
        "original_bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
        "revised_bundle_sha256": hashlib.sha256(b"".join(later[name] for name in sorted(later))).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "086")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "086/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"086": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "timezone-converter"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "086/corpus_086")], "rust"),
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
                print(name + " portable timezone replay: passed", flush=True)
    assert len({(row["original_bundle_sha256"], row["revised_bundle_sha256"]) for row in observations}) == 1
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
