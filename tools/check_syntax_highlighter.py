"""Replay exported source through all Python/Rust producer/replayer combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.syntax_highlighter import Fixture, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path) -> Fixture:
    directory.mkdir(parents=True)
    config = json.loads((previous.output / "highlight-job.json").read_text())
    for entry in config["files"]:
        entry["source"] = str(previous.output / entry["source"])
    config["output"] = "output"
    (directory / "job.json").write_text(json.dumps(config))
    return Fixture(directory, previous.sources, previous.expected, previous.theme)


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    hashes = []
    for theme in ["light", "dark"]:
        first = fixture(directory / theme / "first", theme)
        original, files = run(writer, first)
        second = consume(first, directory / theme / "second")
        transformed, exported = run(replayer, second)
        third = consume(second, directory / theme / "third")
        final, rebuilt = run(reader, third)
        assert original == transformed == final and files == exported == rebuilt
        assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
        assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
        hashes.append(hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_exported_source_consumed": True,
        "both_themes_and_diagnostic_pages_replayed": True,
        "previous_bundles_unchanged": True,
        "bundle_sha256": hashes,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "080")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "080/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"080": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "syntax-highlighter"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "080/corpus_080")], "rust"),
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
                print(name + " themed source replay: passed", flush=True)
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
