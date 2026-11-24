"""Resume real interrupted checkpoints across Python/Rust and changing batch sizes."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.batch_worker import (
    fixture,
    invoke,
    kill,
    paused,
    sample_rows,
    snapshot,
    state,
    verify,
)
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    rows = [dict(sample_rows()[index % 5], id=f"job_{index}") for index in range(13)]
    first = fixture(directory / "first", rows, batch=3)
    kill(paused(writer, first, "staged:6"))
    assert state(first)["completed"] == 3
    assert json.loads((first.output / "control.tmp").read_bytes())["value"]["completed"] == 6
    original = snapshot(first.output)
    second = fixture(directory / "second", rows, batch=4)
    shutil.copyfile(first.source, second.source)
    shutil.copytree(first.output, second.output)
    result = invoke(replayer, second, BATCH_LIMIT="1")
    assert result[-1]["status"] == "paused" and result[-1]["completed"] == 7
    verify(second, 7)
    intermediate = snapshot(second.output)
    third = fixture(directory / "third", rows, batch=2)
    shutil.copyfile(second.source, third.source)
    shutil.copytree(second.output, third.output)
    invoke(reader, third)
    verify(third)
    before = snapshot(third.output)
    assert len(invoke(reader, third)) == 1
    assert snapshot(third.output) == before
    assert snapshot(first.output) == original and snapshot(second.output) == intermediate
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_checkpoint_files_consumed": True,
        "actual_kill_with_uncommitted_staging": True,
        "durable_prefixes": [3, 7, 13],
        "batch_sizes": [3, 4, 2],
        "final_report_sha256": hashlib.sha256((third.output / "report.json").read_bytes()).hexdigest(),
        "final_state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "090")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "090/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"090": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "batch-worker"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "090/corpus_090")], "rust"),
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
                print(name + " checkpoint resume: passed", flush=True)
    assert len({(row["final_report_sha256"], row["final_state_sha256"]) for row in observations}) == 1
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
