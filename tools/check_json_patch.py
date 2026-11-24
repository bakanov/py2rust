"""Generate, apply and undo complete JSON patch projects across eight engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical
from corpus_checks.json_patch import digest, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, applier: Application, reverser: Application, work: Path) -> dict:
    before = {
        "profile": {"name": "Ada", "roles": ["reader", "guest", "retired"]},
        "a/b": {"~1": None},
        "": {"\0": "old"},
        "number": 1,
        "zero": 0.0,
        "gone": [True],
    }
    after = {
        "profile": {"name": "Ada 世界", "roles": ["editor"]},
        "a/b": {"~1": [1, 2]},
        "": {"\0": "new"},
        "number": 1.0,
        "zero": -0.0,
        "new": {"notes": "😀\n"},
    }
    generated = fixture(work, "diff", before, after)
    run(writer, generated)
    patch_bytes = (generated.output / "patch.json").read_bytes()
    patch = json.loads(patch_bytes)
    applied = fixture(work, "apply", before, patch, "apply")
    run(applier, applied)
    result_bytes = (applied.output / "result.json").read_bytes()
    assert result_bytes == canonical(after).encode()
    inverse_bytes = (applied.output / "undo.json").read_bytes()
    reverted = fixture(work, "undo", json.loads(result_bytes), json.loads(inverse_bytes), "apply")
    run(reverser, reverted)
    assert (reverted.output / "result.json").read_bytes() == canonical(before).encode()
    assert (reverted.output / "undo.json").read_bytes() == patch_bytes
    return {
        "writer": writer.engine,
        "applier": applier.engine,
        "reverser": reverser.engine,
        "changes": len(patch["changes"]),
        "base_sha256": digest(before),
        "target_sha256": digest(after),
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
        "undo_sha256": hashlib.sha256(inverse_bytes).hexdigest(),
        "exact_roundtrip": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "045")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "045/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "verify the current corpus first"
    fingerprints = {"045": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "json-patch"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "045/corpus_045")], "rust"),
    }
    observations = []
    for writer in apps.values():
        for applier in apps.values():
            for reverser in apps.values():
                name = writer.engine + "-" + applier.engine + "-" + reverser.engine
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, applier, reverser, work))
                print(name + " diff/apply/undo: passed", flush=True)
    for key in ["patch_sha256", "undo_sha256"]:
        assert len({row[key] for row in observations}) == 1
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
