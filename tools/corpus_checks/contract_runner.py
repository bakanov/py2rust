"""A deliberately faulty server supplies independently specified contract failures."""

import contextlib
import copy
import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def faulty_server() -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/disconnect":
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            status = 200
            body = b'{"name":"Alice","items":[{"id":7}],"nullable":null,"active":true}'
            if self.path == "/wrong-status":
                status = 503
                body = b'{"reason":"unavailable"}'
            elif self.path == "/broken-json":
                body = b"{broken"
            elif self.path == "/wrong-values":
                body = b'{"name":"Bob","active":1}'
            elif self.path == "/huge":
                body = b"x" * 4096
            elif self.path == "/echo":
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        do_POST = do_GET

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def check(app: Application, directory: Path) -> dict:
    snapshots = directory / "snapshots"
    snapshots.mkdir()
    document = {"name": "Alice", "items": [{"id": 7}], "nullable": None, "active": True}
    (snapshots / "profile.json").write_text(json.dumps(document))
    (snapshots / "changed.json").write_text('{"name":"not Alice"}')
    (snapshots / "invalid.json").write_text("broken snapshot")
    cases = [
        {
            "name": "valid profile",
            "path": "/ok",
            "status": 200,
            "snapshot": "profile.json",
            "fields": [
                {"path": "items.0.id", "value": 7.0},
                {"path": "nullable", "value": None},
                {"path": "absent", "exists": False},
                {"path": "items.9.id", "exists": False},
            ],
        },
        {"name": "bad status", "path": "/wrong-status", "status": 200},
        {
            "name": "bad fields",
            "path": "/wrong-values",
            "status": 200,
            "fields": [
                {"path": "name", "value": "Alice"},
                {"path": "items", "value": []},
                {"path": "active", "value": True},
            ],
        },
        {"name": "bad JSON", "path": "/broken-json", "status": 200, "fields": [{"path": "$", "value": {}}]},
        {"name": "missing snapshot", "path": "/ok", "status": 200, "snapshot": "missing.json"},
        {"name": "changed snapshot", "path": "/ok", "status": 200, "snapshot": "changed.json"},
        {"name": "unreadable snapshot", "path": "/ok", "status": 200, "snapshot": "invalid.json"},
        {"name": "disconnect", "path": "/disconnect", "status": 200},
        {"name": "body limit", "path": "/huge", "status": 200},
        {
            "name": "continue after errors",
            "method": "POST",
            "path": "/echo",
            "status": 200,
            "body": {"message": "世界"},
            "fields": [{"path": "message", "value": "世界"}],
        },
    ]
    with faulty_server() as url:
        configuration = {"base_url": url, "timeout_ms": 500, "max_body": 1024, "cases": cases}
        config_path = directory / "contracts.json"
        report_path = directory / "report.json"
        config_path.write_text(json.dumps(configuration))
        settings = {
            "CONTRACT_CONFIG": str(config_path),
            "CONTRACT_REPORT": str(report_path),
            "CONTRACT_SNAPSHOTS": str(snapshots),
        }
        result = app.run(directory, settings)
        assert result.returncode == 1, result.stderr + result.stdout
        report = json.loads(report_path.read_text())
        assert json.loads(result.stdout) == report
        assert report["summary"] == {"total": 10, "passed": 2, "failed": 8, "mismatches": 10}, report
        assert [item["name"] for item in report["results"]] == [item["name"] for item in cases]
        checks = [[failure["check"] for failure in item["failures"]] for item in report["results"]]
        assert checks == [
            [],
            ["status"],
            ["value", "presence", "value"],
            ["json"],
            ["snapshot"],
            ["snapshot"],
            ["snapshot"],
            ["transport"],
            ["transport"],
            [],
        ]
        assert not (snapshots / "missing.json").exists()
        # Updates are explicit, and a failed status cannot overwrite an accepted baseline.
        previous = (snapshots / "changed.json").read_bytes()
        configuration["update_snapshots"] = True
        configuration["cases"] = [cases[0], dict(cases[1], snapshot="changed.json")]
        config_path.write_text(json.dumps(configuration))
        assert app.run(directory, settings).returncode == 1
        assert (snapshots / "changed.json").read_bytes() == previous
        configuration["cases"] = [dict(cases[0], snapshot="new.json")]
        config_path.write_text(json.dumps(configuration))
        assert app.run(directory, settings).returncode == 0
        assert json.loads((snapshots / "new.json").read_text()) == document
        configuration["update_snapshots"] = False
        config_path.write_text(json.dumps(configuration))
        assert app.run(directory, settings).returncode == 0
        before = report_path.read_bytes()
        for invalid in [dict(cases[0], snapshot="../escape.json"), dict(cases[0], path="//external/path")]:
            configuration["cases"] = [invalid]
            config_path.write_text(json.dumps(configuration))
            assert app.run(directory, settings).returncode != 0
            assert report_path.read_bytes() == before
        duplicate = copy.deepcopy(cases[0])
        configuration["cases"] = [cases[0], duplicate]
        config_path.write_text(json.dumps(configuration))
        assert app.run(directory, settings).returncode != 0
    return {
        "summary": report["summary"],
        "named_results": report["results"],
        "snapshot_update_guard": True,
        "success_exit": 0,
        "failure_exit": 1,
        "invalid_configuration_preserves_report": True,
    }
