"""Replay, edit and reparse actual exported INI files across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.ini_editor import fixture, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", *sample())
    original = success(writer, first)
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    replay = fixture(
        directory, "replay", b"", [], source=str(first.output / "input.ini"), edits=str(first.output / "edits.json")
    )
    assert success(updater, replay) == original
    assert files == {path.name: path.read_bytes() for path in replay.output.iterdir()}
    edits = [
        {"op": "set", "section": "server", "key": "host", "value": "example.test"},
        {"op": "set", "section": "server", "key": "port", "value": "8443"},
        {"op": "delete", "section": "server", "key": "label"},
        {"op": "set", "section": "new", "key": "name", "value": '世界 "notes"'},
        {"op": "set", "section": "", "key": "later", "value": "global added last"},
    ]
    changed = fixture(directory, "changed", b"", edits, source=str(replay.output / "settings.ini"))
    report = success(updater, changed)
    assert report["expanded"]["client.endpoint"] == "http://example.test:8443/"
    assert report["expanded"][".host"] == "localhost" and report["raw"][".later"] == "global added last"
    assert "server.label" not in report["raw"]
    rewritten = (changed.output / "settings.ini").read_bytes()
    assert b'port = "8443" # keep\n' in rewritten
    assert b"# Global fallback\n" in rewritten and b"[server] ; network\n" in rewritten
    final = fixture(directory, "final", b"", [], source=str(changed.output / "settings.ini"))
    assert success(reader, final) == report
    assert (final.output / "settings.ini").read_bytes() == rewritten
    assert (final.output / "values.json").read_bytes() == (changed.output / "values.json").read_bytes()
    repeated = fixture(
        directory,
        "repeated",
        b"",
        [],
        source=str(changed.output / "input.ini"),
        edits=str(changed.output / "edits.json"),
    )
    assert success(reader, repeated) == report
    assert {path.name: path.read_bytes() for path in repeated.output.iterdir()} == {
        path.name: path.read_bytes() for path in changed.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "settings_sha256": hashlib.sha256(files["settings.ini"]).hexdigest(),
        "updated_settings_sha256": hashlib.sha256(rewritten).hexdigest(),
        "actual_export_paths": True,
        "comments_preserved": True,
        "scoped_expansion_updated": True,
        "replayed_bundles_identical": True,
        "earlier_bundles_unchanged": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "075")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "075/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"075": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "ini-editor"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "075/corpus_075")], "rust"),
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
                print(name + " INI edit, comment retention, expansion and replay: passed", flush=True)
    for field in ["settings_sha256", "updated_settings_sha256"]:
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
