"""Analyze real exported log files across Python/Rust engines, then add requests and widen the time window."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.access_log import fixture, line, sample, success
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample())
    original = success(writer, first)
    assert original["counts"] == {"lines": 6, "valid": 5, "malformed": 1, "selected": 4, "filtered": 1}
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, sources=str(first.output / "sources.json"))
    assert success(updater, second) == original
    third = fixture(directory, "third", {}, sources=str(second.output / "sources.json"))
    assert success(reader, third) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    sources = json.loads((third.output / "sources.json").read_bytes())["files"]
    inputs = {row["name"]: (third.output / row["path"]).read_bytes() for row in sources}
    inputs["front"] += line(timestamp="12/Oct/2026:10:15:00 +0000", target="/notes?updated=1", size="30") + b"\n"
    edited = fixture(directory, "edited", inputs, start=None, end=None)
    changed = success(updater, edited)
    assert changed["counts"] == {"lines": 7, "valid": 6, "malformed": 1, "selected": 6, "filtered": 0}
    assert changed["summary"]["bytes"] == 300 and changed["summary"]["top_paths"][0]["requests"] == 3
    final = fixture(directory, "final", {}, sources=str(edited.output / "sources.json"), start=None, end=None)
    assert success(reader, final) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "report_sha256": hashlib.sha256(files["report.json"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "report.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "new_request_and_window_edits": True,
        "preserved_source_bytes": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "071")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "071/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"071": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "access-log"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "071/corpus_071")], "rust"),
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
                    name + " access-log source exports, new requests, time-window edits and repeated analysis: passed",
                    flush=True,
                )
    for field in ["report_sha256", "edited_sha256"]:
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
