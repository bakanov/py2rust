"""Exchange actual source snapshots and edits through eight check/apply/recheck engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.header_fixture import cases
from corpus_checks.source_headers import consume, fixture, run, snapshot

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], target: Path) -> None:
    target.mkdir(parents=True)
    for name, data in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return  # noqa: PLR1711


def exercise(writer: Application, applier: Application, reader: Application, root: Path) -> dict:
    expected = cases()
    first = root / "first"
    checked = run(writer, first, fixture(first, expected), expected)
    original = snapshot(first / "inspection")
    second = root / "second"
    restore(original, second)
    applied, output = consume(applier, second, "apply.json", expected)
    assert applied["summary"]["violations"] == checked["summary"]["violations"]
    assert applied["summary"]["remaining"] == 1
    patched = snapshot(output)
    third = root / "third"
    restore(patched, third)
    corrected = {name: (row[3], row[1], row[2] if row[4] else [], row[3], row[4]) for name, row in expected.items()}
    rechecked, final_output = consume(reader, third, "recheck.json", corrected)
    assert rechecked["summary"]["remaining"] == 1 and rechecked["summary"]["changed_files"] == 0
    assert rechecked["groups"] == {"header_in_preamble": [{"file": "manual.py", "line": 1}]}
    assert snapshot(first / "inspection") == original and snapshot(output) == patched
    for name, data in original.items():
        assert (second / name).read_bytes() == data
    for name, data in patched.items():
        assert (third / name).read_bytes() == data
    assert all((output / "files" / name).read_bytes() == row[3] for name, row in expected.items())
    # Replay the original request with the third engine; every exported byte must match.
    fourth = root / "replay"
    restore(original, fourth)
    repeated, replay_output = consume(reader, fourth, "replay.json", expected)
    assert repeated == checked and snapshot(replay_output) == original
    return {
        "writer": writer.engine,
        "applier": applier.engine,
        "reader": reader.engine,
        "actual_source_and_patch_exports_consumed": True,
        "all_expected_corrected_bytes_match": True,
        "rechecked_edits_idempotent": True,
        "manual_conflict_preserved": True,
        "plan_sha256": hashlib.sha256(original["patches.json"]).hexdigest(),
        "recheck_sha256": hashlib.sha256((final_output / "report.json").read_bytes()).hexdigest(),
    }


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "097")
    current = fingerprint(program)
    result = json.loads((BUILD / "097/result.json").read_text())
    assert result["status"] == "verified" and result["fingerprint"] == current
    directory = BUILD / "source-headers"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"097": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "097/corpus_097")], "rust"),
    ]
    observations = []
    for writer in apps:
        for applier in apps:
            for reader in apps:
                name = f"{writer.engine}-{applier.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, applier, reader, work))
                print(name + " source/patch/recheck exchange: passed", flush=True)
    assert len({row["plan_sha256"] for row in observations}) == 1
    assert len({row["recheck_sha256"] for row in observations}) == 1
    assert fingerprint(program) == current
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"097": current},
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
