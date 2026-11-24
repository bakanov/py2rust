"""Replay actual exported source through every Python/Rust producer/replayer combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.automation_language import Fixture, fixture, run
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path) -> Fixture:
    directory.mkdir(parents=True)
    config = json.loads((previous.output / "job.json").read_text())
    config["program"] = str(previous.output / config["program"])
    config["output"] = "output"
    (directory / "job.json").write_text(json.dumps(config))
    return Fixture(directory, previous.source, previous.budget)


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    hashes = []
    for code in [0, 1]:
        source = "# 世界\r\nlet total = 0\r\nrepeat 4 { let n = total + 1; set total = total + n; emit total }\r\n"
        first = fixture(directory / str(code) / "first", source, 100 if code == 0 else 7)
        original, files = run(writer, first, code)
        second = consume(first, directory / str(code) / "second")
        transformed, exported = run(replayer, second, code)
        third = consume(second, directory / str(code) / "third")
        final, rebuilt = run(reader, third, code)
        assert original == transformed == final and files == exported == rebuilt
        assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
        assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
        hashes.append(hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_exported_source_consumed": True,
        "success_and_budget_error_replayed": True,
        "previous_bundles_unchanged": True,
        "bundle_sha256": hashes,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "079")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "079/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"079": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "automation-language"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "079/corpus_079")], "rust"),
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
                print(name + " successful/error program replay: passed", flush=True)
    assert len({tuple(row["bundle_sha256"]) for row in observations}) == 1
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
