"""Run seven complete HTTP client applications against the mock API.

All four Python/Rust server/client combinations use current verified builds.
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


def check(
    server_app: Application,
    monitor: Application,
    harvester: Application,
    downloader: Application,
    auditor: Application,
    watcher: Application,
    batcher: Application,
    load_probe: Application,
    directory: Path,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    mock_config = directory / "routes.json"
    routes = json.loads((CORPUS / "012_json_harvester/pages-api.json").read_text())
    routes["routes"].extend(json.loads((CORPUS / "013_resumable_download/download-api.json").read_text())["routes"])
    routes["routes"].extend(json.loads((CORPUS / "016_link_auditor/site-api.json").read_text())["routes"])
    watched = json.loads((CORPUS / "017_change_watcher/snapshots-api.json").read_text())
    routes["states"].extend("watch-" + value for value in watched["states"])
    for route in watched["routes"]:
        route["id"] = "watch-" + route["id"]
        route["when"] = routes["initial"] if route["when"] == watched["initial"] else "watch-" + route["when"]
        if "next" in route:
            route["next"] = "watch-" + route["next"]
    routes["routes"].extend(watched["routes"])
    batches = json.loads((CORPUS / "018_quota_batcher/quota-api.json").read_text())
    routes["states"].extend("batch-" + value for value in batches["states"])
    for route in batches["routes"]:
        route["id"] = "batch-" + route["id"]
        if "when" in route:
            route["when"] = "watch-changed" if route["when"] == batches["initial"] else "batch-" + route["when"]
        if "next" in route:
            route["next"] = "batch-" + route["next"]
    routes["routes"].extend(batches["routes"])
    routes["routes"].extend(json.loads((CORPUS / "020_load_probe/probe-api.json").read_text())["routes"])
    mock_config.write_text(json.dumps(routes))
    health_config = directory / "health-config.json"
    health_state = directory / "health.json"
    harvest_config = directory / "harvest-config.json"
    harvest_state = directory / "harvest.json"
    with server_app.server(
        directory, {"MOCK_CONFIG": str(mock_config), "MOCK_STATE": str(directory / "mock.json"), "MOCK_PORT": "0"}
    ) as server:
        # The mock API reloads its validated route configuration per request.
        routes["routes"][0]["body"]["next"] = server.url + "/pages/2"
        mock_config.write_text(json.dumps(routes))
        health_config.write_text(
            json.dumps(
                {
                    "endpoints": [
                        {"id": "reachable", "url": server.url + "/_mock/state"},
                        {"id": "missing", "url": server.url + "/absent"},
                    ],
                    "failure_threshold": 2,
                }
            )
        )
        health_settings = {"HEALTH_CONFIG": str(health_config), "HEALTH_STATE": str(health_state), "HEALTH_NOW": "1000"}
        assert monitor.run(directory, health_settings).returncode == 1
        health = json.loads(Path(str(health_state) + ".report.json").read_text())
        assert [item["state"] for item in health["endpoints"]] == ["up", "unknown"]
        assert monitor.run(directory, dict(health_settings, HEALTH_NOW="1020")).returncode == 1
        health = json.loads(Path(str(health_state) + ".report.json").read_text())
        assert [item["state"] for item in health["endpoints"]] == ["up", "down"]
        assert health["endpoints"][1]["opened"] == 1000 and health["endpoints"][1]["down_seconds"] == 20
        harvest_config.write_text(json.dumps({"start": server.url + "/pages/1"}))
        harvest_settings = {
            "HARVEST_CONFIG": str(harvest_config),
            "HARVEST_STATE": str(harvest_state),
            "HARVEST_STOP": "after_checkpoint",
        }
        interrupted = harvester.run(directory, harvest_settings)
        assert interrupted.returncode == 75, interrupted.stderr
        assert len(json.loads(harvest_state.read_text())["pages"]) == 1
        resumed = harvester.run(directory, dict(harvest_settings, HARVEST_STOP=""))
        assert resumed.returncode == 0, resumed.stderr
        report = json.loads(Path(str(harvest_state) + ".report.json").read_text())
        assert report["complete"] and report["pages"] == 2 and report["count"] == 3 and report["duplicates"] == 1
        assert report["records"] == [
            {"id": "one", "text": "Hello, 世界"},
            {"id": "two", "tags": ["notes"]},
            {"id": "three", "active": True},
        ]
        assert harvester.run(directory, dict(harvest_settings, HARVEST_STOP="")).returncode == 0
        download_config = directory / "download.json"
        downloaded = directory / "artifact.txt"
        policy = json.loads((CORPUS / "013_resumable_download/download.json").read_text())
        policy.update(url=server.url + "/artifact.txt", target=str(downloaded))
        download_config.write_text(json.dumps(policy))
        download_settings = {"DOWNLOAD_CONFIG": str(download_config), "DOWNLOAD_STOP": "after_publish"}
        interrupted = downloader.run(directory, download_settings)
        assert interrupted.returncode == 75, interrupted.stderr
        assert downloaded.read_bytes() == b"abc" and downloaded.samefile(Path(str(downloaded) + ".part"))
        resumed = downloader.run(directory, dict(download_settings, DOWNLOAD_STOP=""))
        assert resumed.returncode == 0, resumed.stderr
        assert downloaded.read_bytes() == b"abc" and not Path(str(downloaded) + ".part").exists()
        assert json.loads(Path(str(downloaded) + ".download.json").read_text())["phase"] == "published"
        audit_config = directory / "audit.json"
        audit_report = directory / "audit-report.json"
        audit_config.write_text(json.dumps({"start": server.url + "/"}))
        audited = auditor.run(directory, {"AUDIT_CONFIG": str(audit_config), "AUDIT_REPORT": str(audit_report)})
        assert audited.returncode == 1, audited.stderr
        audit = json.loads(audit_report.read_text())
        assert audit["summary"] == {
            "pages": 3,
            "links": 4,
            "broken_pages": 1,
            "broken_links": 1,
            "complete": True,
            "outcomes": {"queued": 2, "duplicate": 1, "external": 1},
        }
        watch_config = directory / "watch.json"
        watch_state = directory / "watch-state.json"
        watch_config.write_text(
            json.dumps({"url": server.url + "/snapshot", "ignore": ["/observed_at"], "interval_ms": 1})
        )
        watch_settings = {
            "WATCH_CONFIG": str(watch_config),
            "WATCH_STATE": str(watch_state),
            "WATCH_ROUNDS": "4",
            "WATCH_NOW": "2024-03-01T00:00:00Z",
        }
        changed = watcher.run(directory, watch_settings)
        assert changed.returncode == 0, changed.stderr
        watch = json.loads(watch_state.read_text())
        assert watch["checks"] == 4 and watch["next_id"] == 2 and len(watch["history"]) == 1
        assert watch["history"][0]["changes"] == [
            {"op": "add", "path": "/profile/roles/1", "before": None, "after": "writer"}
        ]
        assert "observed_at" not in watch["snapshot"]
        assert watcher.run(directory, dict(watch_settings, WATCH_ROUNDS="1")).returncode == 0
        assert json.loads(watch_state.read_text())["next_id"] == 2
        batch_config = directory / "batch-config.json"
        batch_state = directory / "batch-state.json"
        batch_jobs = directory / "requests.json"
        batch_config.write_text(json.dumps({"base_url": server.url + "/api/"}))
        batch_jobs.write_bytes((CORPUS / "018_quota_batcher/requests.json").read_bytes())
        batch_settings = {
            "BATCH_CONFIG": str(batch_config),
            "BATCH_STATE": str(batch_state),
            "BATCH_IMPORT": str(batch_jobs),
            "BATCH_NOW": "1000",
        }
        paused = batcher.run(directory, batch_settings)
        assert paused.returncode == 0, paused.stderr
        batch = json.loads(batch_state.read_text())
        assert batch["quota"]["not_before"] == 1003 and batch["jobs"][0]["state"] == "complete"
        assert batcher.run(directory, dict(batch_settings, BATCH_NOW="1002.999")).returncode == 0
        resumed = batcher.run(directory, dict(batch_settings, BATCH_NOW="1003"))
        assert resumed.returncode == 0, resumed.stderr
        batch = json.loads(batch_state.read_text())
        assert [item["state"] for item in batch["jobs"]] == ["complete"] * 3
        assert [item["attempts"] for item in batch["jobs"]] == [1, 2, 1]
        assert [item["result"] for item in batch["jobs"]] == [
            {"name": "Alice", "roles": ["reader"]},
            {"projects": ["Paper Plane", "Python to Rust"]},
            {"unread": 4},
        ]
        assert batcher.run(directory, dict(batch_settings, BATCH_NOW="1004")).returncode == 0
        load_config = directory / "load.json"
        load_report = directory / "load-report.json"
        load_policy = json.loads((CORPUS / "020_load_probe/load.json").read_text())
        for target in load_policy["targets"]:
            target["url"] = target["url"].replace("http://127.0.0.1:8786", server.url)
        load_config.write_text(json.dumps(load_policy))
        probed = load_probe.run(
            directory,
            {"LOAD_CONFIG": str(load_config), "LOAD_REPORT": str(load_report), "LOAD_CANCEL": "", "LOAD_CA": ""},
        )
        assert probed.returncode == 1, probed.stderr
        load = json.loads(load_report.read_text())
        assert load["phase"] == "finished" and load["status"] == "failed"
        assert len(load["samples"]) == 14 and load["overall"]["attempted"] == 14
        assert load["overall"]["counts"] == {"ok": 11, "http_error": 3, "transport_error": 0, "cancelled": 0, "late": 0}
        assert load["overall"]["statuses"] == {"200": 8, "201": 3, "503": 3}
        transcript = server.request("GET", "/_mock/transcript").json()
        assert [item["path"] for item in transcript if item["path"].startswith("/pages/")] == ["/pages/1", "/pages/2"]
        assert [item["path"] for item in transcript if item["path"] == "/artifact.txt"] == ["/artifact.txt"]
        assert [item["path"] for item in transcript if item["path"] == "/snapshot"] == ["/snapshot"] * 5
        assert [item["path"] for item in transcript if item["path"].startswith("/api/")] == [
            "/api/profile",
            "/api/projects",
            "/api/projects",
            "/api/notifications",
        ]
        assert sorted(item["path"] for item in transcript if item["path"].startswith("/load/")) == (
            ["/load/busy"] * 3 + ["/load/create"] * 3 + ["/load/ready"] * 8
        )
    return {
        "server": server_app.engine,
        "clients": monitor.engine,
        "health": ["up", "down"],
        "open_outage_seconds": 20,
        "pages_requested": ["/pages/1", "/pages/2"],
        "records": report["records"],
        "download": {"bytes": 3, "sha256": policy["sha256"], "recovered_publication": True},
        "audit": audit["summary"],
        "watcher": {"events": 1, "changes": watch["history"][0]["changes"]},
        "batcher": {"complete": 3, "attempts": [1, 2, 1], "retry_deadline": 1003},
        "load_probe": {"planned": 14, "attempted": 14, "counts": load["overall"]["counts"]},
    }


def main() -> int:
    programs = {item["id"]: item for item in json.loads((CORPUS / "catalog.json").read_text())["programs"]}
    fingerprints = {}
    for identifier in ["006", "011", "012", "013", "016", "017", "018", "020"]:
        result = json.loads((BUILD / identifier / "result.json").read_text())
        current = fingerprint(programs[identifier])
        assert result["status"] == "verified" and result["fingerprint"] == current, "run current corpus checks first"
        fingerprints[identifier] = current
    directory = BUILD / "http-clients"
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
                check(
                    application("006", server_engine, programs),
                    application("011", client_engine, programs),
                    application("012", client_engine, programs),
                    application("013", client_engine, programs),
                    application("016", client_engine, programs),
                    application("017", client_engine, programs),
                    application("018", client_engine, programs),
                    application("020", client_engine, programs),
                    work,
                )
            )
            print(
                server_engine + " mock API / " + client_engine + " seven HTTP clients: passed",
                flush=True,
            )
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
