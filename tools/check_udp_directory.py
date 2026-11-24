"""Exercise complete UDP directory servers and retrying clients across both engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.udp_directory import client_server, lost_acknowledgement

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "025")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "025/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"025": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "udp-directory"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    path.write_text(json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash}))
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "025/corpus_025")], "rust"),
    }
    observations = []
    for server in apps.values():
        for client in apps.values():
            work = directory / (server.engine + "-" + client.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(
                {
                    "server": server.engine,
                    "client": client.engine,
                    "batch": client_server(server, client, work / "batch"),
                    "lost_ack": lost_acknowledgement(server, client, work / "lost-ack"),
                }
            )
            print(server.engine + " UDP directory / " + client.engine + " retrying client: passed", flush=True)
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
