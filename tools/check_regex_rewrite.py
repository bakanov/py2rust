"""Use actual rewrite backups across all Python/Rust apply, restore and reapply combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.regex_rewrite import (
    digest,
    files,
    fixture,
    invoke,
    oracle,
    save,
    snapshot,
    verify_backup,
    verify_restored,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, restorer: Application, rewriter: Application, directory: Path) -> dict:
    hashes = []
    for interrupted in [False, True]:
        case = fixture(directory / ("partial" if interrupted else "complete"))
        expected, rewritten = oracle(case)
        if interrupted:
            invoke(writer, case, "apply", False, REWRITE_FAIL="1")
        else:
            assert invoke(writer, case, "apply") == expected
            assert files(case) == rewritten
        verify_backup(case, expected, rewritten)
        assert invoke(restorer, case, "restore") == expected
        verify_restored(case)
        previous = case.backup
        before = snapshot(previous)
        case.config["backup"] = "second-backup"
        save(case)
        assert invoke(rewriter, case, "preview") == expected
        assert invoke(rewriter, case, "apply") == expected
        assert files(case) == rewritten
        verify_backup(case, expected, rewritten)
        assert snapshot(previous) == before
        hashes.append(digest(b"".join(files(case).values())))
    assert hashes[0] == hashes[1]
    return {
        "writer": writer.engine,
        "restorer": restorer.engine,
        "rewriter": rewriter.engine,
        "actual_backups_consumed": True,
        "complete_and_interrupted_batches_restored": True,
        "original_metadata_restored": True,
        "prior_backups_unchanged": True,
        "rewritten_sha256": hashes[0],
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "078")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "078/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"078": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "regex-rewrite"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "078/corpus_078")], "rust"),
    ]
    observations = []
    for writer in apps:
        for restorer in apps:
            for rewriter in apps:
                name = f"{writer.engine}-{restorer.engine}-{rewriter.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, restorer, rewriter, work))
                print(name + " complete/interrupted rewrite, restore and reapply: passed", flush=True)
    assert len({row["rewritten_sha256"] for row in observations}) == 1
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
