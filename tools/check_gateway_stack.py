"""Run a batcher through the circuit gateway into the mock API in all eight engine combinations."""

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


def check(upstream: Application, gateway: Application, batcher: Application, directory: Path) -> dict:
    directory.mkdir(parents=True)
    mock_config = directory / "upstream.json"
    mock_config.write_bytes((CORPUS / "019_circuit_gateway/upstream-api.json").read_bytes())
    clock = directory / "clock.json"
    clock.write_text("1000")
    gateway_config = directory / "gateway.json"
    gateway_state = directory / "gateway-state.json"
    with upstream.server(
        directory,
        {
            "MOCK_CONFIG": str(mock_config),
            "MOCK_STATE": str(directory / "mock-state.json"),
            "MOCK_PORT": "0",
        },
    ) as remote:
        policy = json.loads((CORPUS / "019_circuit_gateway/gateway.json").read_text())
        for route in policy["routes"]:
            route["url"] = remote.url + "/upstream/" + route["id"]
        gateway_config.write_text(json.dumps(policy))
        with gateway.server(
            directory,
            {
                "GATEWAY_CONFIG": str(gateway_config),
                "GATEWAY_STATE": str(gateway_state),
                "GATEWAY_CLOCK": str(clock),
                "GATEWAY_PORT": "0",
            },
        ) as proxy:
            batch_config = directory / "batch.json"
            batch_state = directory / "batch-state.json"
            requests = directory / "requests.json"
            batch_config.write_text(json.dumps({"base_url": proxy.url + "/", "backoff": 1}))
            requests.write_text(
                json.dumps(
                    [
                        {"id": "catalog-a", "url": "catalog"},
                        {"id": "catalog-b", "url": "catalog"},
                        {"id": "notes", "url": "notes"},
                    ]
                )
            )
            settings = {
                "BATCH_CONFIG": str(batch_config),
                "BATCH_STATE": str(batch_state),
                "BATCH_IMPORT": str(requests),
            }

            def run(now: float) -> dict:
                clock.write_text(str(now))
                result = batcher.run(directory, {**settings, "BATCH_NOW": str(now)})
                assert result.returncode == 0, result.stderr
                return json.loads(Path(str(batch_state) + ".report.json").read_text())

            first = run(1000)
            assert first["counts"] == {"complete": 1, "pending": 2, "failed": 0, "inflight": 0}
            circuit = proxy.request("GET", "/_gateway/state").json()["circuits"][0]
            assert circuit["phase"] == "open" and circuit["retry_at"] == 1003 and circuit["failed_calls"] == 2
            paused = run(1001)
            assert paused["not_before"] == 1003 and paused["counts"]["complete"] == 1
            assert len(remote.request("GET", "/_mock/transcript").json()) == 3
            assert run(1002.999)["counts"]["complete"] == 1
            assert len(remote.request("GET", "/_mock/transcript").json()) == 3
            final = run(1003)
            assert final["counts"] == {"complete": 3, "pending": 0, "failed": 0, "inflight": 0}
            assert [entry["attempts"] for entry in final["jobs"]] == [3, 2, 1]
            assert [entry["result"] for entry in final["jobs"]] == [
                {"items": ["paper", "pen"]},
                {"items": ["paper", "pen"]},
                {"notes": ["Saved ideas"]},
            ]
            assert run(1004)["jobs"] == final["jobs"]
            records = proxy.request("GET", "/_gateway/state").json()["circuits"]
            circuit = records[0]
            assert circuit["phase"] == "closed" and circuit["calls"] == 4 and circuit["rejected"] == 1
            assert [event["after"] for event in circuit["history"]] == ["open", "half_open", "closed"]
            assert records[1]["phase"] == "closed" and records[1]["calls"] == 1
            transcript = remote.request("GET", "/_mock/transcript").json()
            assert [entry["path"] for entry in transcript] == [
                "/upstream/catalog",
                "/upstream/catalog",
                "/upstream/notes",
                "/upstream/catalog",
                "/upstream/catalog",
            ]
    return {
        "upstream": upstream.engine,
        "gateway": gateway.engine,
        "batcher": batcher.engine,
        "completed": 3,
        "attempts": [3, 2, 1],
        "transitions": ["open", "half_open", "closed"],
        "upstream_requests": 5,
        "rejected_while_open": 1,
    }


def main() -> int:
    programs = {item["id"]: item for item in json.loads((CORPUS / "catalog.json").read_text())["programs"]}
    fingerprints = {}
    for identifier in ["006", "018", "019"]:
        result = json.loads((BUILD / identifier / "result.json").read_text())
        current = fingerprint(programs[identifier])
        assert result["status"] == "verified" and result["fingerprint"] == current, "run current corpus checks first"
        fingerprints[identifier] = current
    directory = BUILD / "gateway-stack"
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result_path.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash}, indent=2)
        + "\n"
    )
    observations = []
    for server_engine in ["python", "rust"]:
        for gateway_engine in ["python", "rust"]:
            for client_engine in ["python", "rust"]:
                name = server_engine + "-" + gateway_engine + "-" + client_engine
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(
                    check(
                        application("006", server_engine, programs),
                        application("019", gateway_engine, programs),
                        application("018", client_engine, programs),
                        work,
                    )
                )
                print(name + " upstream/gateway/batcher: passed", flush=True)
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
