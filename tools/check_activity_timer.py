"""Resume HTTP activity journals through all Python/Rust writer/restarter combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.activity_timer import Reference, canonical, fixture, running, step
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    fix, reference = fixture(directory / "shared"), Reference()
    snapshots = []
    with running(writer, fix, reference) as server:
        step(fix, reference, server, 1000000, 10000, "start", "focus", "Work 世界")
        step(fix, reference, server, 1000500, 10500, "start", "meeting", "Work 世界")
        step(fix, reference, server, 1001000, 11000, "pause", "focus")
    snapshots.append(hashlib.sha256(fix.store.read_bytes()).hexdigest())
    fix.clock(1002000, 0)
    with running(replayer, fix, reference) as server:
        step(fix, reference, server, 1002000, 0, "report")
        step(fix, reference, server, 1002500, 500, "resume", "focus")
        step(fix, reference, server, 1003000, 1000, "stop", "meeting")
        step(fix, reference, server, 900000, 1500, "pause", "focus")
    snapshots.append(hashlib.sha256(fix.store.read_bytes()).hexdigest())
    fix.clock(900000, 0)
    with running(reader, fix, reference) as server:
        step(fix, reference, server, 900000, 0, "get", "focus")
        step(fix, reference, server, 900000, 0, "resume", "meeting")
        step(fix, reference, server, 1003600, 100, "stop", "focus")
        step(fix, reference, server, 1003600, 100, "start", "review", "Review")
        result = step(fix, reference, server, 1003700, 200, "export")
    snapshots.append(hashlib.sha256(fix.store.read_bytes()).hexdigest())
    assert reference.view("focus")["completed_ms"] == 2000
    assert reference.view("meeting")["completed_ms"] == 2500
    assert reference.report()["completed_ms"] == 4500 and reference.report()["elapsed_ms"] == 4600
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_saved_journal_consumed": True,
        "clock_rebase_and_pause_preserved": True,
        "snapshot_sha256": snapshots,
        "report_sha256": hashlib.sha256(canonical(result).encode()).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "083")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "083/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"083": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "activity-timer"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "083/corpus_083")], "rust"),
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
                print(name + " HTTP activity continuation: passed", flush=True)
    assert len({(tuple(row["snapshot_sha256"]), row["report_sha256"]) for row in observations}) == 1
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
