"""Independent delivery schedule and durable-state assertions."""

import contextlib
import copy
import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def receiver() -> Iterator[tuple[str, list, dict]]:
    calls: list = []
    seen: dict = {}
    sequences = {
        "retry": [(503, ""), (429, "5"), (201, "")],
        "disconnect": [(0, ""), (201, "")],
        "permanent": [(400, "")],
        "exhaust": [(503, "")] * 3,
        "redirect": [(302, "")],
        "instant": [(204, "")],
        "date": [(429, "Wed, 21 Oct 2030 07:28:00 GMT"), (201, "")],
        "capped": [(429, "99999999"), (201, "")],
    }

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            identifier = self.headers.get("Idempotency-Key")
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.headers["Content-Type"] == "application/json"
            assert self.headers["X-Trace"] == "trace-1"
            calls.append({"id": identifier, "payload": body})
            count = sum(item["id"] == identifier for item in calls)
            if identifier == "crash":
                seen.setdefault(identifier, body)
                assert seen[identifier] == body
                code, delay = (201 if count == 1 else 200), ""
            else:
                code, delay = sequences[identifier][count - 1]
            if code == 0:
                self.close_connection = True
                return
            self.send_response(code)
            self.send_header("Content-Length", "0")
            if delay:
                self.send_header("Retry-After", delay)
            if code == 302:
                self.send_header("Location", "/unexpected")
            self.end_headers()
            return

        def log_message(self, *args) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/events", calls, seen
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return


def check(app: Application, directory: Path) -> dict:
    state = directory / "queue.json"
    report_path = directory / "report.json"
    incoming = directory / "input.json"
    settings = {
        "OUTBOX_STATE": str(state),
        "OUTBOX_REPORT": str(report_path),
        "OUTBOX_IMPORT": str(incoming),
        "OUTBOX_NOW": "1000",
        "OUTBOX_ATTEMPTS": "3",
        "OUTBOX_DELAY": "2",
    }
    with receiver() as (url, calls, seen):
        jobs = [
            {"id": name, "url": url, "payload": {"event": name, "text": "Привет 😀"}, "headers": {"X-Trace": "trace-1"}}
            for name in ["retry", "disconnect", "permanent", "exhaust", "redirect", "instant", "date", "capped"]
        ]
        incoming.write_text(json.dumps(jobs))

        def step(now: int, counts: dict, exit_code: int = 1) -> dict:
            settings["OUTBOX_NOW"] = str(now)
            result = app.run(directory, settings)
            assert result.returncode == exit_code, result.stderr
            report = json.loads(report_path.read_text())
            assert report["counts"] == counts
            return report

        first = step(1000, {"pending": 5, "delivered": 1, "dead": 2})
        assert [item["id"] for item in first["dead"]] == ["permanent", "redirect"]
        assert [item["next_attempt"] for item in first["pending"]] == [1002, 1002, 1002, 1002, 4600]
        snapshot = state.read_bytes()
        step(1001, first["counts"])
        assert state.read_bytes() == snapshot and len(calls) == 8
        second = step(1002, {"pending": 3, "delivered": 3, "dead": 2})
        assert [(item["id"], item["next_attempt"]) for item in second["pending"]] == [
            ("retry", 1007),
            ("exhaust", 1006),
            ("capped", 4600),
        ]
        third = step(1006, {"pending": 2, "delivered": 3, "dead": 3})
        assert next(item for item in third["dead"] if item["id"] == "exhaust")["attempts"] == 3
        step(1007, {"pending": 1, "delivered": 4, "dead": 3})
        final = step(4600, {"pending": 0, "delivered": 5, "dead": 3})
        assert len(calls) == 15
        assert all(call["payload"]["event"] == call["id"] for call in calls)
        snapshot = state.read_bytes()
        step(4601, final["counts"])
        assert len(calls) == 15 and state.read_bytes() == snapshot
        # A later invalid member must not persist an earlier, valid new member.
        new = copy.deepcopy(jobs[0])
        new["id"] = "new"
        invalid = copy.deepcopy(jobs[0])
        invalid["payload"]["text"] = "different"
        incoming.write_text(json.dumps([new, invalid]))
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == snapshot and len(calls) == 15
        malformed = [
            {**jobs[0], "url": "http://user:password@localhost/"},
            {**jobs[0], "url": "http://localhost:99999/"},
            {**jobs[0], "payload": []},
            {**jobs[0], "headers": {"Host": "override"}},
            {**jobs[0], "headers": {"X": "1", "x": "2"}},
            {**jobs[0], "headers": {"X": "bad\nvalue"}},
            {**jobs[0], "extra": 1},
        ]
        for bad in malformed:
            incoming.write_text(json.dumps([bad]))
            assert app.run(directory, settings).returncode != 0
            assert state.read_bytes() == snapshot and len(calls) == 15
        settings["OUTBOX_MODE"] = "inspect"
        step(4602, final["counts"])
        assert len(calls) == 15 and state.read_bytes() == snapshot
        alias = directory / "queue-alias.json"
        alias.symlink_to(state)
        for output in [state, alias, incoming]:
            before = output.read_bytes()
            assert app.run(directory, dict(settings, OUTBOX_REPORT=str(output))).returncode != 0
            assert output.read_bytes() == before
        corrupt = json.loads(snapshot)
        corrupt["jobs"][0]["attempts"] = -1
        state.write_text(json.dumps(corrupt))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
        state.write_bytes(snapshot)
        # Simulate process loss after the peer accepted a delivery but before our
        # local checkpoint. A stable key allows the peer to store one event.
        crash_state = directory / "crash-state.json"
        crash_job = {**jobs[0], "id": "crash", "payload": {"value": "durable"}}
        incoming.write_text(json.dumps([crash_job]))
        crash_settings = dict(settings, OUTBOX_STATE=str(crash_state), OUTBOX_MODE="run", OUTBOX_STOP="after_send")
        assert app.run(directory, crash_settings).returncode == 75
        persisted = json.loads(crash_state.read_text())["jobs"][0]
        assert persisted["attempts"] == 0 and persisted["state"] == "pending"
        crash_settings["OUTBOX_STOP"] = ""
        result = app.run(directory, crash_settings)
        assert result.returncode == 0, result.stderr
        assert json.loads(crash_state.read_text())["jobs"][0]["state"] == "delivered"
        assert len([call for call in calls if call["id"] == "crash"]) == 2
        assert seen == {"crash": {"value": "durable"}}
        return {"report": final, "calls": calls, "invalid_imports": len(malformed) + 1, "crash_recovered": True}
