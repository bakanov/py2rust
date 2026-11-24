"""Verify durable TCP transfer interoperability in all four sender/receiver combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.tcp_transfer import exercise_pair

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "029")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "029/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"029": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "tcp-transfer"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    path.write_text(json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash}))
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "029/corpus_029")], "rust"),
    }
    observations = []
    for receiver in apps.values():
        for sender in apps.values():
            work = directory / (receiver.engine + "-" + sender.engine)
            if work.exists():
                shutil.rmtree(work)
            work.mkdir()
            observations.append(
                {"receiver": receiver.engine, "sender": sender.engine, **exercise_pair(receiver, sender, work)}
            )
            print(receiver.engine + " receiver / " + sender.engine + " sender: passed", flush=True)
    path.write_text(
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
