"""Check fixture receipts and interrupted cleanup across Python/native writers."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.fixture_tree import (
    clean,
    construct,
    fixture,
    interrupted,
    invoke,
    receipt,
    reject,
    snapshot,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(creator: Application, cleaner: Application, work: Path) -> dict:
    fix = fixture(work, "shared", existing=True)
    before = construct(creator, fix)
    hashes = {name: row["sha256"] for name, row in receipt(fix)["entries"].items() if row["kind"] == "file"}
    assert invoke(cleaner, fix, "verify")["phase"] == "ready"
    interrupted(cleaner, fix, "cleanup", "removed:0")
    clean(creator, fix, before)
    clean(cleaner, fix, before)
    partial = fixture(work, "partial", existing=True, simple=True)
    before = snapshot(partial.root)
    interrupted(creator, partial, "create", "recorded:1")
    clean(cleaner, partial, before)
    uncertain = fixture(work, "uncertain", simple=True)
    interrupted(creator, uncertain, "create", "written:1")
    reject(cleaner, uncertain, "cleanup", "unrecorded")
    (uncertain.root / "a.txt").unlink()
    clean(cleaner, uncertain, {})
    return {
        "creator": creator.engine,
        "cleaner": cleaner.engine,
        "hashes": hashes,
        "cleanup_resumed": True,
        "partial_creation_cleaned": True,
        "unrecorded_entry_preserved": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "040")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "040/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"040": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "fixture-tree"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "040/corpus_040")], "rust"),
    }
    observations = []
    for creator in apps.values():
        for cleaner in apps.values():
            work = directory / (creator.engine + "-" + cleaner.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(creator, cleaner, work))
            print(creator.engine + " creator / " + cleaner.engine + " cleaner: passed", flush=True)
    assert len({json.dumps(row["hashes"], sort_keys=True) for row in observations}) == 1
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
