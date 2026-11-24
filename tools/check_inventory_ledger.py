"""Exchange inventory snapshots, continuation requests and committed-crash retries in eight engine combinations."""

import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.inventory_fixture import apply_model, canonical, digest, event
from corpus_checks.inventory_ledger import (
    consume,
    files_at,
    fixture,
    paused,
    run,
    save,
    stop,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], directory: Path) -> None:
    directory.mkdir(parents=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return  # noqa: PLR1711


def exercise(writer: Application, follower: Application, verifier: Application, root: Path) -> dict:
    first = root / "writer"
    ledger, _ = run(writer, first, fixture(first))
    original = files_at(first / "output")
    second = root / "follower"
    restore(original, second)
    continued, report = consume(follower, second, "continue.json", ledger)
    assert continued == ledger and not report["changed_store"]
    more = [
        event("new_receipt", "receive", {"bolt": 9, "nut": 7}),
        event("new_reserve", "reserve", {"bolt": 6, "nut": 4}, "newOrder"),
        event("new_partial", "release", {"bolt": 2}, "newOrder"),
        ledger["events"][1]["event"],
    ]
    next_request = json.loads(original["continue.json"])
    next_request.update(output="advanced", operations=more)
    save(second / "next.json", next_request)
    advanced, report = run(follower, second, next_request, ledger, "next.json")
    assert report["summary"] == {"accepted": 3, "duplicate": 1, "rejected": 0}
    assert advanced["events"][: ledger["revision"]] == ledger["events"]
    advanced_files = files_at(second / "advanced")
    third = root / "verifier"
    restore(advanced_files, third)
    replayed, report = consume(verifier, third, "replay.json", advanced)
    assert replayed == advanced and not report["changed_store"]
    same, _ = consume(verifier, third, "continue.json", advanced)
    assert same == advanced
    assert files_at(first / "output") == original
    assert files_at(second / "advanced") == advanced_files
    assert (first / "inventory.json").read_bytes() == original["ledger.json"]
    # Kill one engine after the whole batch commit, then recover with another.
    crash = root / "crash"
    retry = fixture(crash, more, ledger)
    process, _ = paused(writer, crash, "committed")
    try:
        process.kill()
        process.communicate(timeout=5)
        assert process.returncode == -9
    finally:
        stop(process)
    expected, _ = apply_model(ledger, more)
    assert expected == advanced and (crash / "inventory.json").read_bytes() == canonical(advanced)
    assert not (crash / "output").exists()
    recovered, report = run(follower, crash, retry, advanced)
    assert recovered == advanced and report["summary"] == {"accepted": 0, "duplicate": 4, "rejected": 0}
    verified, _ = consume(verifier, crash / "output", "replay.json", advanced)
    assert verified == advanced
    return {
        "writer": writer.engine,
        "follower": follower.engine,
        "verifier": verifier.engine,
        "actual_snapshots_and_requests_consumed": True,
        "history_prefix_preserved": True,
        "snapshot_continuation_forks_original": True,
        "mixed_engine_crash_recovery": True,
        "committed_retry_does_not_duplicate_history": True,
        "initial_ledger_sha256": digest(original["ledger.json"]),
        "advanced_ledger_sha256": digest(advanced_files["ledger.json"]),
        "advanced_revision": advanced["revision"],
    }


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "102")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "102/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "inventory-ledger"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"102": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "102/corpus_102")], "rust"),
    ]
    observations = []
    for writer in apps:
        for follower in apps:
            for verifier in apps:
                name = f"{writer.engine}-{follower.engine}-{verifier.engine}"
                root = directory / name
                if root.exists():
                    shutil.rmtree(root)
                observations.append(exercise(writer, follower, verifier, root))
                print(name + " inventory ledger exchange: passed", flush=True)
    for key in ["initial_ledger_sha256", "advanced_ledger_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"102": current},
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
