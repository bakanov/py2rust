"""Resume actual log cursors and partial JSONL appends across Python/Rust processes."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.log_router import (
    canonical,
    fixture,
    inspect,
    records,
    run,
    saved,
    snapshot,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    fix = fixture(directory)
    first = b"INFO started\nDEBUG filtered\n"
    extra = "ERROR pin 世界 after restart\n".encode()
    fix.append("alpha", first)
    run(writer, fix)
    inspect(fix, records("alpha", first))
    fix.append("alpha", extra)
    run(writer, fix, 2, ROUTER_FAULT="partial-1")
    plan = saved(fix.output / "pending.json")
    partial = (fix.output / "general.0.jsonl").read_bytes()
    assert (
        plan["before"]["files"]["general.0.jsonl"]["bytes"]
        < len(partial)
        < plan["after"]["files"]["general.0.jsonl"]["bytes"]
    )
    run(replayer, fix)
    expected = records("alpha", first + extra)
    inspect(fix, expected)
    tail = b"WARNING old inode tail\n"
    fix.append("alpha", tail)
    fix.input("alpha").rename(directory / "alpha.log.1")
    fresh = b"INFO replacement\nCRITICAL pin followup\n"
    fix.input("alpha").write_bytes(fresh)
    run(replayer, fix)
    expected += records("alpha", tail, 4, offset=len(first + extra))
    inspect(fix, expected)
    run(reader, fix)
    expected += records("alpha", fresh, 5, 1)
    state = inspect(fix, expected)
    before = snapshot(fix.output)
    run(reader, fix)
    assert before == snapshot(fix.output)
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_partial_append_recovered": True,
        "actual_saved_cursor_consumed": True,
        "records_sha256": hashlib.sha256(canonical(expected).encode()).hexdigest(),
        "output_metadata_sha256": hashlib.sha256(canonical(state["files"]).encode()).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "084")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "084/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"084": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "log-router"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "084/corpus_084")], "rust"),
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
                print(name + " partial-append recovery and input rotation: passed", flush=True)
    assert len({(row["records_sha256"], row["output_metadata_sha256"]) for row in observations}) == 1
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
