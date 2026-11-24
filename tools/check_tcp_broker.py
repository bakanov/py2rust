"""Exercise the complete framed broker and its native client in all four engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def check(server_app: Application, client_app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True)
    config = directory / "config.json"
    policy = json.loads((CORPUS / "021_tcp_broker/broker.json").read_text())
    policy["connection_frames"] = 2
    config.write_text(json.dumps(policy))
    state = directory / "state.json"
    batch = directory / "requests.json"
    output = directory / "responses.json"
    batch.write_bytes((CORPUS / "021_tcp_broker/requests.json").read_bytes())
    settings = {
        "BROKER_CONFIG": str(config),
        "BROKER_STATE": str(state),
        "BROKER_PORT": "0",
        "BROKER_MODE": "serve",
        "BROKER_SHUTDOWN": "",
        "BROKER_STOP": "",
    }
    with server_app.server(directory, settings) as server:
        client_settings = dict(
            settings,
            BROKER_MODE="client",
            BROKER_HOST="127.0.0.1",
            BROKER_PORT=str(server.port),
            BROKER_REQUESTS=str(batch),
            BROKER_REPORT=str(output),
        )
        completed = client_app.run(directory, client_settings)
        assert completed.returncode == 0, completed.stderr
        report = json.loads(output.read_text())
        assert report["phase"] == "finished" and report["errors"] == 0 and len(report["responses"]) == 5
        replies = report["responses"]
        assert replies[0] == {"ok": True, "id": "note-1", "sequence": 1, "state": "pending", "duplicate": False}
        assert [job["id"] for job in replies[1]["jobs"]] == ["note-1"]
        assert replies[2] == dict(replies[0], state="done")
        assert replies[3]["job"]["state"] == "done"
        assert replies[4] == {"ok": True, "accepted": 1, "done": 1, "pending": 0, "next_sequence": 2, "capacity": 1000}
        before = state.read_bytes()
        repeated = client_app.run(directory, client_settings)
        assert repeated.returncode == 0, repeated.stderr
        replay = json.loads(output.read_text())["responses"]
        assert replay[0] == dict(replies[0], state="done", duplicate=True)
        assert replay[1]["jobs"] == [] and replay[2] == dict(replies[2], duplicate=True)
        assert replay[3:] == replies[3:] and state.read_bytes() == before
    return {
        "server": server_app.engine,
        "client": client_app.engine,
        "commands": 5,
        "connection_frames": 2,
        "accepted": 1,
        "done": 1,
        "replay_unchanged": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "021")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "021/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"021": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "tcp-broker"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "result.json"
    path.write_text(json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash}))
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "021/corpus_021")], "rust"),
    }
    observations = []
    for server in apps.values():
        for client in apps.values():
            work = directory / (server.engine + "-" + client.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(check(server, client, work))
            print(server.engine + " broker / " + client.engine + " batch client: passed", flush=True)
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
