"""Actual HTTP writes and saved snapshots cross every Python/Rust writer/updater/reader combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.ttl_notebook import Reference, fixture, step

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    fix, reference = fixture(directory, "shared", TTL_KEYS="2"), Reference(2)
    with writer.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 1000, "put", key="note/世界", value=None, ttl=10)
        step(fix, reference, server, 1000, "put", key="temporary", value={"text": "old"}, ttl=20)
    first = fix.path.read_bytes()
    with updater.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 1005, "get", key="note/世界")
        step(fix, reference, server, 1005, "put", key="note/世界", value={"new": [False, 1.5]}, ttl=30)
        step(fix, reference, server, 1010, "get", key="note/世界")
        step(fix, reference, server, 1020, "get", key="temporary")
    second = fix.path.read_bytes()
    fix.clock(999)
    with reader.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 999, "get", key="temporary")
        step(fix, reference, server, 999, "list")
        step(fix, reference, server, 999, "put", key="fresh", value=None, ttl=1)
        step(fix, reference, server, 1021, "sweep")
        step(fix, reference, server, 1034.999999, "get", key="note/世界")
        step(fix, reference, server, 1035, "get", key="note/世界")
    third = fix.path.read_bytes()
    fix.clock(0)
    with writer.server(fix.work, fix.settings()) as server:
        step(fix, reference, server, 0, "get", key="note/世界")
        step(fix, reference, server, 0, "sweep")
        step(fix, reference, server, 0, "list")
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "snapshot_sha256": [
            hashlib.sha256(value).hexdigest() for value in [first, second, third, fix.path.read_bytes()]
        ],
        "actual_artifact_paths": True,
        "replacement_deadline": 1035,
        "retained_clock": 1035,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "052")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "052/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"052": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "ttl-notebook"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "052/corpus_052")], "rust"),
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
                print(name + " notebook write/replace/expire: passed", flush=True)
    assert len({tuple(row["snapshot_sha256"]) for row in observations}) == 1
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
