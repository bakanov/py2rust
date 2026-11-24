"""Rebuild actual exported source bundles across all Python/Rust engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.source_outline import Fixture, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def consume(previous: Fixture, directory: Path, label: str) -> Fixture:
    config = json.loads((previous.output / "project.json").read_text())
    for item in config["modules"]:
        item["source"] = str(previous.output / item["source"])
    output = directory / label
    config["output"] = str(output)
    path = directory / (label + ".json")
    path.write_text(json.dumps(config))
    return Fixture(directory, path, output, previous.sources, previous.packages)


def exercise(writer: Application, transformer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first")
    original, files = run(writer, first)
    second = consume(first, directory, "second")
    transformed, exported = run(transformer, second)
    third = consume(second, directory, "third")
    final, rebuilt = run(reader, third)
    assert original == transformed == final and files == exported == rebuilt
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "transformer": transformer.engine,
        "reader": reader.engine,
        "actual_exported_source_files": True,
        "package_identity_preserved": True,
        "all_links_resolve": True,
        "previous_bundles_unchanged": True,
        "bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "077")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "077/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"077": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "source-outline"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "077/corpus_077")], "rust"),
    ]
    observations = []
    for writer in apps:
        for transformer in apps:
            for reader in apps:
                name = f"{writer.engine}-{transformer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, transformer, reader, work))
                print(name + " portable source bundle and cross-linked rebuild: passed", flush=True)
    assert len({row["bundle_sha256"] for row in observations}) == 1
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
