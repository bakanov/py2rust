"""Resume committed JSONL prefixes and uncommitted quarantine tails across engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.jsonl_transform import complete, fixture, hashed

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, recovery: Application, work: Path) -> dict:
    fix = fixture(work, "shared")
    for app, point in [(writer, "after_sync:1"), (recovery, "checkpoint:2")]:
        result = app.run(fix.work, fix.settings(JSONL_FAIL=point))
        assert result.returncode != 0 and "injected failure: " + point in result.stderr, result.stderr
    state = complete(writer, fix)
    complete(recovery, fix)
    spill = fixture(work, "spilled")
    result = writer.run(spill.work, spill.settings(JSONL_FAIL="spill:4"))
    assert result.returncode != 0 and "injected failure: spill:4" in result.stderr, result.stderr
    complete(recovery, spill)
    hashes = {name: hashed(fix.root / name) for name in ["accepted.jsonl", "quarantine.bin", "rejected.jsonl"]}
    assert hashes == {name: hashed(spill.root / name) for name in hashes}
    return {
        "writer": writer.engine,
        "recovery": recovery.engine,
        "hashes": hashes,
        "lines": state["lines"],
        "accepted": state["accepted"],
        "filtered": state["filtered"],
        "rejected": state["rejected"],
        "uncommitted_tails_recovered": True,
        "partial_oversized_line_recovered": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "043")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "043/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"043": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "jsonl-transform"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "043/corpus_043")], "rust"),
    }
    observations = []
    for writer in apps.values():
        for recovery in apps.values():
            work = directory / (writer.engine + "-" + recovery.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(writer, recovery, work))
            print(writer.engine + " writer / " + recovery.engine + " recovery: passed", flush=True)
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
