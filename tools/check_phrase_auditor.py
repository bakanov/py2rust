"""Reuse actual document exports and vary text and n-gram thresholds across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.phrase_auditor import fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first)
    assert original["analysis"]["counts"]["matches"] == 3
    assert original["analysis"]["counts"]["covered_tokens"] == 21
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, documents=str(first.output / "documents.json"))
    assert success(updater, second) == original
    third = fixture(directory, "third", {}, documents=str(second.output / "documents.json"))
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    shorter = fixture(directory, "shorter", {}, 2, documents=str(third.output / "documents.json"))
    more = success(updater, shorter)
    assert more["analysis"]["counts"]["matches"] == 4 and more["analysis"]["counts"]["covered_tokens"] == 25
    unicode_match = more["analysis"]["matches"][-1]
    assert unicode_match["tokens"] == ["strasse", "café"]
    assert unicode_match["left"]["text"] == "STRASSE Café" and unicode_match["right"]["text"] == "Straße cafe\u0301"
    value = json.loads((shorter.output / "documents.json").read_bytes())
    copied = next(row["text"] for row in value["documents"] if row["id"] == "unrelated")
    next(row for row in value["documents"] if row["id"] == "notes")["text"] += "\n" + copied
    edited = fixture(directory, "edited", value, 2)
    changed = success(reader, edited)
    assert changed["analysis"]["counts"]["matches"] == 5 and changed["analysis"]["counts"]["covered_tokens"] == 35
    final = fixture(directory, "final", {}, 2, documents=str(edited.output / "documents.json"))
    assert success(writer, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "audit_sha256": hashlib.sha256(files["audit.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "audit.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "unicode_excerpt_positions": True,
        "threshold_and_text_changes": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "067")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "067/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"067": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "phrase-auditor"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "067/corpus_067")], "rust"),
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
                print(name + " document exports, Unicode passages, threshold and text edits: passed", flush=True)
    for field in ["audit_sha256", "edited_sha256"]:
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
