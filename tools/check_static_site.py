"""Rebuild and edit actual exported Markdown across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.static_site import (
    fixture,
    sample,
    sample_expected,
    source_files,
    success,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first, sample_expected())
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, site=str(first.output / "site.json"))
    assert success(updater, second, sample_expected()) == original
    third = fixture(directory, "third", {}, site=str(second.output / "site.json"))
    assert success(reader, third, sample_expected()) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    inputs = {row["id"]: path.read_bytes() for row, path in source_files(third)}
    inputs["guide"] += b"\n## Setup\nAn **updated** _note_.\n"
    edited = fixture(directory, "edited", inputs)
    changed = success(updater, edited)
    assert changed["pages"][1]["headings"][-1] == {"level": 2, "text": "Setup", "id": "setup-3"}
    assert b"<strong>updated</strong> <em>note</em>" in (edited.output / "guide.html").read_bytes()
    final = fixture(directory, "final", {}, site=str(edited.output / "site.json"))
    assert success(reader, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "html_sha256": hashlib.sha256(files["guide.html"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "guide.html").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "new_heading_and_formatting": True,
        "preserved_source_bytes": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "072")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "072/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"072": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "static-site"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "072/corpus_072")], "rust"),
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
                    name + " static-site exported Markdown, edited formatting and duplicate headings: passed",
                    flush=True,
                )
    for field in ["html_sha256", "edited_sha256"]:
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
