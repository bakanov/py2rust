"""Independent outage trace, network-failure isolation and checkpoint assertions."""

import contextlib
import copy
import http.server
import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def endpoints() -> Iterator[tuple[str, str, dict, list]]:
    controls = {"switch": 200}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            calls.append(self.path)
            code = 200
            body = b"healthy"
            if self.path == "/switch":
                code = controls["switch"]
            elif self.path == "/custom":
                code = 404
            elif self.path == "/huge":
                body = b"x" * 4096
            elif self.path == "/slow":
                time.sleep(0.15)
            elif self.path == "/redirect":
                code = 302
            self.send_response(code)
            self.send_header("Content-Length", str(len(body)))
            if code == 302:
                self.send_header("Location", "/unexpected-follow")
            self.end_headers()
            with contextlib.suppress(OSError):
                self.wfile.write(body)
            return  # noqa: PLR1711 - explicit return required by repository guidelines

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    reserved = socket.socket()
    reserved.bind(("127.0.0.1", 0))  # Bound but not listening: a deterministic refusal.
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", f"http://127.0.0.1:{reserved.getsockname()[1]}/", controls, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        reserved.close()
    return


def without_latency(report: dict) -> dict:
    result = copy.deepcopy(report)
    for endpoint in result["endpoints"]:
        for sample in endpoint["samples"]:
            assert isinstance(sample["latency_ms"], (int, float))
            assert 0 <= sample.pop("latency_ms") < 10000
    return result


def check(application: Application, directory: Path) -> dict:
    config = directory / "endpoints.json"
    state = directory / "health.json"
    report_file = Path(str(state) + ".report.json")
    text_file = Path(str(state) + ".report.txt")
    settings = {"HEALTH_CONFIG": str(config), "HEALTH_STATE": str(state), "HEALTH_NOW": "1000"}
    observations = {}
    with endpoints() as (base, unreachable, controls, calls):
        policy = {
            "endpoints": [
                {"id": "offline-first", "url": unreachable},
                {"id": "switch", "url": base + "/switch"},
                {"id": "custom", "url": base + "/custom", "statuses": [404]},
                {"id": "body-limit", "url": base + "/huge"},
                {"id": "timeout", "url": base + "/slow"},
                {"id": "redirect", "url": base + "/redirect"},
                {"id": "healthy-last", "url": base + "/ok"},
            ],
            "failure_threshold": 2,
            "recovery_threshold": 2,
            "retain": 4,
            "timeout_ms": 50,
            "max_body": 512,
        }
        config.write_text(json.dumps(policy))

        def step(now: int, code: int, expected: str) -> dict:
            controls["switch"] = code
            result = application.run(directory, dict(settings, HEALTH_NOW=str(now)))
            assert result.returncode == 1, result.stderr
            report = json.loads(report_file.read_text())
            assert json.loads(result.stdout) == {"healthy": report["healthy"], "unhealthy": report["unhealthy"]}
            assert [item["id"] for item in report["endpoints"]] == [item["id"] for item in policy["endpoints"]]
            assert report["endpoints"][1]["state"] == expected
            assert report["endpoints"][-1]["state"] == "up", "an earlier failure stopped later checks"
            assert report["endpoints"][2]["state"] == "up", "configured success statuses were ignored"
            for index in [0, 3, 4]:
                assert report["endpoints"][index]["samples"][-1]["kind"] == "transport"
            assert report["endpoints"][5]["samples"][-1]["status"] == 302
            assert report["endpoints"][4]["samples"][-1]["latency_ms"] >= 20
            assert "/unexpected-follow" not in calls
            without_latency(report)  # Validate measured timing before omitting it from parity.
            return report

        first = step(1000, 200, "up")
        assert first["healthy"] == 3
        assert first["endpoints"][0]["state"] == "unknown"
        step(1010, 503, "degraded")
        down = step(1020, 503, "down")
        assert down["endpoints"][1]["opened"] == 1010 and down["endpoints"][1]["down_seconds"] == 10
        step(1030, 200, "recovering")
        step(1040, 503, "down")
        step(1050, 200, "recovering")
        final = step(1060, 200, "up")
        switched = final["endpoints"][1]
        assert switched["checks"] == 7 and switched["failures"] == 3
        assert switched["outages"] == [{"start": 1010, "end": 1060, "seconds": 50}]
        assert switched["opened"] is None and switched["down_seconds"] == 50
        assert [sample["at"] for sample in switched["samples"]] == [1030, 1040, 1050, 1060]
        assert "switch: up" in text_file.read_text() and "latency_ms=" in text_file.read_text()
        observations["trace"] = without_latency(final)
        backwards = step(900, 200, "up")
        assert backwards["at"] == 1060 and backwards["endpoints"][1]["down_seconds"] == 50
        before = state.read_bytes()
        before_calls = len(calls)
        inspected = application.run(directory, dict(settings, HEALTH_MODE="inspect", HEALTH_NOW="9999"))
        assert inspected.returncode == 1
        assert state.read_bytes() == before and len(calls) == before_calls
        assert json.loads(report_file.read_text()) == backwards

        old_report = report_file.read_bytes()
        for invalid in [
            {**policy, "failure_threshold": 0},
            {**policy, "retain": True},
            {**policy, "endpoints": [policy["endpoints"][0]] * 2},
            {**policy, "endpoints": [{"id": "bad", "url": "http://user@localhost/"}]},
            {**policy, "endpoints": [{"id": "bad", "url": "http://localhost/%GG"}]},
            {**policy, "endpoints": [{"id": "bad", "url": "http://127.01.0.1/"}]},
            {**policy, "endpoints": [{"id": "bad", "url": base + "/ok", "statuses": [True]}]},
            {**policy, "failure_threshold": 3},  # Valid configuration, incompatible stored policy.
        ]:
            config.write_text(json.dumps(invalid))
            assert application.run(directory, settings).returncode != 0
            assert (
                state.read_bytes() == before and report_file.read_bytes() == old_report and len(calls) == before_calls
            )
        config.write_text(json.dumps(policy))
        for damage in ["counter", "sample", "outage", "policy"]:
            corrupted = json.loads(before)
            if damage == "counter":
                corrupted["records"][0]["failures"] = -1
            elif damage == "sample":
                corrupted["records"][0]["samples"][-1]["ok"] = True
            elif damage == "outage":
                corrupted["records"][1]["outages"][0]["seconds"] = 49
            else:
                corrupted["policy"]["retain"] = 5
            state.write_text(json.dumps(corrupted))
            damaged = state.read_bytes()
            assert application.run(directory, settings).returncode != 0
            assert (
                state.read_bytes() == damaged and report_file.read_bytes() == old_report and len(calls) == before_calls
            )
        state.write_bytes(before)
        report_file.unlink()
        report_file.symlink_to(state)
        assert application.run(directory, settings).returncode != 0
        assert state.read_bytes() == before and len(calls) == before_calls
        report_file.unlink()

        # A saved partial round remains inspectable after an injected interruption.
        partial = directory / "partial.json"
        stopped = application.run(directory, dict(settings, HEALTH_STATE=str(partial), HEALTH_STOP="switch"))
        assert stopped.returncode == 75
        assert [record["checks"] for record in json.loads(partial.read_text())["records"]] == [1, 1, 0, 0, 0, 0, 0]
        before_calls = len(calls)
        assert (
            application.run(directory, dict(settings, HEALTH_STATE=str(partial), HEALTH_MODE="inspect")).returncode == 1
        )
        assert len(calls) == before_calls
        observations["partial_checkpoint"] = [1, 1, 0, 0, 0, 0, 0]

        # Three completed outages with a two-entry history retain lifetime duration.
        compact = directory / "compact.json"
        policy = {
            "endpoints": [{"id": "switch", "url": base + "/switch"}],
            "failure_threshold": 1,
            "recovery_threshold": 1,
            "retain": 2,
        }
        config.write_text(json.dumps(policy))
        for now, code in [(100, 503), (110, 200), (120, 503), (135, 200), (140, 503), (160, 200)]:
            controls["switch"] = code
            result = application.run(directory, dict(settings, HEALTH_STATE=str(compact), HEALTH_NOW=str(now)))
            assert result.returncode == (0 if code == 200 else 1), result.stderr
        compact_report = json.loads(Path(str(compact) + ".report.json").read_text())
        item = compact_report["endpoints"][0]
        assert item["down_seconds"] == 45 and item["checks"] == 6 and item["failures"] == 3
        assert item["outages"] == [{"start": 120, "end": 135, "seconds": 15}, {"start": 140, "end": 160, "seconds": 20}]
        assert len(item["samples"]) == 2
        observations["retention"] = without_latency(compact_report)
        scheduled = application.run(
            directory, dict(settings, HEALTH_STATE=str(compact), HEALTH_NOW="170", HEALTH_ROUNDS="2")
        )
        assert scheduled.returncode == 0, scheduled.stderr
        assert json.loads(compact.read_text())["records"][0]["checks"] == 8
        observations["scheduled_checks"] = 8
    return observations
