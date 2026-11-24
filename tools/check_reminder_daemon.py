"""Resume persistent reminders through all Python/Rust producer/replayer combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.reminder_daemon import canonical, fixture, oracle, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    chunks = [[99, 100, 145], [130, 150, 1000], [1000, 999, 1000, 1000, 1000, 2000]]
    first = fixture(directory / "first")
    initial, first_events = run(writer, first, chunks[0])
    original = first.store.read_bytes()
    second = fixture(directory / "second")
    second.store.write_bytes(original)
    continued, second_events = run(replayer, second, chunks[1], initial)
    intermediate = second.store.read_bytes()
    third = fixture(directory / "third")
    third.store.write_bytes(intermediate)
    final, third_events = run(reader, third, chunks[2], continued)
    expected, all_events = oracle(first.reminders, [tick for chunk in chunks for tick in chunk])
    assert final == expected and first_events + second_events + third_events == all_events
    assert first.store.read_bytes() == original and second.store.read_bytes() == intermediate
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_saved_state_consumed": True,
        "all_policies_and_clock_rollback": True,
        "original_snapshots_unchanged": True,
        "state_sha256": hashlib.sha256(third.store.read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(canonical(all_events)).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "081")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "081/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"081": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "reminder-daemon"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "081/corpus_081")], "rust"),
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
                print(name + " saved reminder continuation: passed", flush=True)
    assert len({(row["state_sha256"], row["events_sha256"]) for row in observations}) == 1
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
