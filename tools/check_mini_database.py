"""Share actual journals/snapshots across Python/Rust writers, compactors and recovery readers."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical
from corpus_checks.mini_database import disk_state, fixture, kill, paused, put, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(
        directory,
        "first",
        [
            put("a", {"title": "世界", "data": [True, None, 1.25]}),
            put("b", 2),
            {"op": "DELETE", "key": "missing"},
            {"op": "COMPACT"},
            put("c", 3),
        ],
        database="../database",
    )
    responses = success(writer, first)
    second = fixture(
        directory,
        "second",
        [{"op": "GET", "key": "a"}, {"op": "DELETE", "key": "b"}, put("a", "replaced"), {"op": "COMPACT"}, put("d", 4)],
        database=str(first.database.resolve()),
    )
    middle = success(updater, second)
    assert middle[0]["sequence"] == 4 and middle[0]["replayed"] == 1
    responses += middle
    second.trace([put("unfinished", "discard this incomplete commit")])
    process, acknowledged = paused(updater, second, "commit-part:8")
    assert len(acknowledged) == 1 and acknowledged[0]["sequence"] == 7
    kill(process)
    before = disk_state(second)
    assert before[0] == 7 and before[-1]["trimmed_bytes"] > 0
    third = fixture(
        directory,
        "third",
        [
            {"op": "GET", "key": "unfinished"},
            {"op": "DUMP"},
            put("after", "recovered"),
            {"op": "COMPACT"},
            {"op": "DELETE", "key": "c"},
            {"op": "DUMP"},
        ],
        database=str(first.database.resolve()),
    )
    final = success(reader, third)
    assert final[0]["trimmed_bytes"] == before[-1]["trimmed_bytes"] and final[0]["sequence"] == 7
    assert not final[1]["found"]
    assert final[-1]["values"] == {"a": "replaced", "d": 4, "after": "recovered"}
    responses += final
    first.trace([{"op": "DUMP"}, {"op": "INFO"}])
    reopened = success(writer, first)
    assert reopened[0]["sequence"] == 9 and reopened[0]["replayed"] == 1
    assert reopened[1]["values"] == final[-1]["values"]
    responses += reopened
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "state_sha256": hashlib.sha256((third.database / "state.json").read_bytes()).hexdigest(),
        "journal_sha256": hashlib.sha256((third.database / "journal.bin").read_bytes()).hexdigest(),
        "responses_sha256": hashlib.sha256(canonical(responses).encode()).hexdigest(),
        "actual_database_directory": True,
        "killed_partial_commit_recovered": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "060")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "060/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"060": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "mini-database"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "060/corpus_060")], "rust"),
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
                print(name + " journal/compaction/recovery: passed", flush=True)
    for field in ["state_sha256", "journal_sha256", "responses_sha256"]:
        assert len({row[field] for row in observations}) == 1
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
