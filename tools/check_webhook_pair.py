"""Exercise inbox/outbox crash recovery across the Python/native engine matrix.

Run tools/corpus.py 002 015 first. Reusing only current, verified builds prevents
this integration check from accidentally exercising old executables.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def application(identifier: str, engine: str, programs: dict) -> Application:
    if engine == "python":
        return Application([sys.executable, "-u", str(CORPUS / programs[identifier]["path"] / "main.py")], engine)
    return Application([str(BUILD / identifier / ("corpus_" + identifier))], engine)


def check(inbox: Application, outbox: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    inbox_state = directory / "inbox.json"
    outbox_state = directory / "outbox.json"
    jobs = directory / "jobs.json"
    server_settings = {"INBOX_STATE": str(inbox_state), "INBOX_NOW": "1000", "INBOX_PORT": "0"}
    client_settings = {
        "OUTBOX_STATE": str(outbox_state),
        "OUTBOX_IMPORT": str(jobs),
        "OUTBOX_NOW": "1000",
        "OUTBOX_REPORT": str(directory / "report.json"),
        "OUTBOX_STOP": "after_send",
    }
    event = {
        "id": "pair-1",
        "type": "note.created",
        "source": "desktop",
        "occurred_at": "2026-10-06T00:00:00Z",
        "data": {"text": "Заметка 😀", "format": ["bold", "italic"]},
    }
    with inbox.server(directory, server_settings) as server:
        jobs.write_text(json.dumps([{"id": event["id"], "url": server.url + "/events", "payload": event}]))
        interrupted = outbox.run(directory, client_settings)
        assert interrupted.returncode == 75, interrupted.stderr
        assert server.request("GET", "/stats").json()["count"] == 1
        entry = json.loads(outbox_state.read_text())["jobs"][0]
        assert entry["state"] == "pending" and entry["attempts"] == 0
        inbox_before = inbox_state.read_bytes()
        client_settings["OUTBOX_STOP"] = ""
        replay = outbox.run(directory, client_settings)
        assert replay.returncode == 0, replay.stderr
        entry = json.loads(outbox_state.read_text())["jobs"][0]
        assert entry["state"] == "delivered" and entry["last_status"] == 200 and entry["attempts"] == 1
        assert inbox_state.read_bytes() == inbox_before
        receipt = server.request("GET", "/receipts/pair-1").json()
        assert receipt["receipt"] == 1 and receipt["event"]["data"] == event["data"]
    # Restart both processes. Inspect never imports or sends; the old receiver
    # URL in the persisted job need not remain reachable after the restart.
    client_settings["OUTBOX_MODE"] = "inspect"
    assert outbox.run(directory, client_settings).returncode == 0
    with inbox.server(directory, server_settings) as server:
        assert server.request("GET", "/receipts/pair-1").json() == receipt
        assert server.request("GET", "/stats").json()["count"] == 1
    return {"inbox": inbox.engine, "outbox": outbox.engine, "deliveries": 2, "stored_events": 1, "receipt": receipt}


def main() -> int:
    programs = {item["id"]: item for item in json.loads((CORPUS / "catalog.json").read_text())["programs"]}
    fingerprints = {}
    for identifier in ["002", "015"]:
        result = json.loads((BUILD / identifier / "result.json").read_text())
        current = fingerprint(programs[identifier])
        assert result["status"] == "verified" and result["fingerprint"] == current, "run current corpus checks first"
        fingerprints[identifier] = current
    directory = BUILD / "webhook-pair"
    directory.mkdir(parents=True, exist_ok=True)
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result_path = directory / "result.json"
    result_path.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash}, indent=2)
        + "\n"
    )
    observations = []
    for server_engine in ["python", "rust"]:
        for client_engine in ["python", "rust"]:
            work = directory / (server_engine + "-" + client_engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(
                check(application("002", server_engine, programs), application("015", client_engine, programs), work)
            )
            print(server_engine + " inbox / " + client_engine + " outbox: passed", flush=True)
    result_path.write_text(
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
