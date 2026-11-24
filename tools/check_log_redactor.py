"""Replay actual sanitized JSONL across runtimes without exporting secret-bearing rules."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.log_redactor import SECRET, canonical, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory / "first")
    initial, files = run(writer, first)
    second = fixture(directory / "second", raw=files["redacted.jsonl"])
    # Read the published file itself; the producing process is already gone.
    shutil.copyfile(first.output / "redacted.jsonl", second.source)
    second.data = second.source.read_bytes()
    repeated, exported = run(replayer, second)
    assert repeated["matches"] == repeated["changed_records"] == 0
    assert exported["redacted.jsonl"] == files["redacted.jsonl"]
    third = fixture(directory / "third", raw=exported["redacted.jsonl"])
    shutil.copyfile(second.output / "redacted.jsonl", third.source)
    with third.source.open("ab") as stream:
        stream.write((canonical({"message": SECRET, "new": True}) + "\n").encode())
    third.data = third.source.read_bytes()
    changed, later = run(reader, third)
    assert changed["records"] == initial["records"] + 1
    assert changed["changed_records"] == 1 and changed["matches"] == 1
    assert (
        later["redacted.jsonl"]
        == files["redacted.jsonl"] + (canonical({"message": "[TOKEN]", "new": True}) + "\n").encode()
    )
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert exported == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_sanitized_files_consumed": True,
        "rerun_idempotent_for_fixture_rules": True,
        "new_sensitive_record_redacted": True,
        "raw_inputs_and_rules_not_exported": True,
        "initial_bundle_sha256": hashlib.sha256(b"".join(files[name] for name in sorted(files))).hexdigest(),
        "final_bundle_sha256": hashlib.sha256(b"".join(later[name] for name in sorted(later))).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "089")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "089/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"089": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "log-redactor"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "089/corpus_089")], "rust"),
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
                print(name + " sanitized-log replay: passed", flush=True)
    assert len({(row["initial_bundle_sha256"], row["final_bundle_sha256"]) for row in observations}) == 1
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
