"""Resume directory creation and pending moves across Python/native journal writers."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.download_organizer import apply, fixture, preview

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(planner: Application, recovery: Application, work: Path) -> dict:
    fix = fixture(work, "shared", minimal=False)
    envelope = preview(planner, fix)
    result = planner.run(fix.directory, fix.settings("apply", ORGANIZE_STOP="mkdir:1"))
    assert result.returncode == 75, result.stderr
    result = recovery.run(fix.directory, fix.settings("apply", ORGANIZE_STOP="renamed:0"))
    assert result.returncode == 75, result.stderr
    apply(planner, fix)
    apply(recovery, fix)
    return {
        "planner": planner.engine,
        "recovery": recovery.engine,
        "unrecorded_directory_recovered": True,
        "pending_move_recovered": True,
        "files": len(envelope["plan"]["rows"]),
        "targets": [row["target"] for row in envelope["plan"]["rows"]],
        "hashes": [row["signature"]["sha256"] for row in envelope["plan"]["rows"]],
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "039")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "039/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"039": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "download-organizer"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "039/corpus_039")], "rust"),
    }
    observations = []
    for planner in apps.values():
        for recovery in apps.values():
            work = directory / (planner.engine + "-" + recovery.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(planner, recovery, work))
            print(planner.engine + " planner / " + recovery.engine + " recovery: passed", flush=True)
    assert len({tuple(row["targets"]) for row in observations}) == 1
    assert len({tuple(row["hashes"]) for row in observations}) == 1
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
