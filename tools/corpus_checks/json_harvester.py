"""A mutable page API checks atomic page acceptance, bounded resume and rejections."""

import contextlib
import copy
import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def page_api() -> Iterator[tuple[str, dict, list]]:
    replies = {}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            calls.append(self.path)
            assert self.headers.get("Accept") == "application/json"
            answer = replies.get(self.path, {"status": 404, "page": {"error": "unknown page"}})
            if answer.get("disconnect"):
                self.close_connection = True
                return
            data = answer.get("raw", json.dumps(answer.get("page"), ensure_ascii=False).encode())
            self.send_response(answer.get("status", 200))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "application/json")
            if "location" in answer:
                self.send_header("Location", answer["location"])
            self.end_headers()
            with contextlib.suppress(OSError):
                self.wfile.write(data)
            return

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", replies, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def check(application: Application, directory: Path) -> dict:
    config = directory / "harvest.json"
    state = directory / "state.json"
    report_path = Path(str(state) + ".report.json")
    settings = {"HARVEST_CONFIG": str(config), "HARVEST_STATE": str(state), "HARVEST_STEPS": "1"}
    observations = {}
    with page_api() as (base, replies, calls), page_api() as (foreign, _foreign_replies, foreign_calls):
        alpha = {"id": "alpha", "title": "Привет 世界", "values": [True, None, {"text": "a\nb"}]}
        beta = {"id": "β", "score": 1}
        gamma = {"id": "gamma", "active": False}
        delta = {"id": "delta", "tags": []}
        replies.update(
            {
                "/p1": {"page": {"items": [alpha, beta, alpha], "next": base + "/p2"}},
                "/p2": {"page": {"items": [{**beta, "score": 1.0}, gamma], "next": base + "/p3"}},
                "/p3": {"page": {"items": [], "next": base + "/p4"}},
                "/p4": {"page": {"items": [delta, alpha], "next": None}},
            }
        )
        policy = {
            "start": base + "/p1",
            "max_pages": 6,
            "max_records": 10,
            "page_size": 5,
            "max_body": 8192,
            "timeout_ms": 1000,
        }
        config.write_text(json.dumps(policy))

        def run(extra: dict | None = None, code: int = 0) -> dict:
            result = application.run(directory, dict(settings, **(extra or {})))
            assert result.returncode == code, result.stderr
            report = json.loads(report_path.read_text())
            assert json.loads(result.stdout) == {key: report[key] for key in ["complete", "pages", "count"]}
            return report

        initial = run({"HARVEST_MODE": "inspect"})
        assert initial["count"] == initial["pages"] == 0 and not state.exists() and calls == []
        first = run()
        assert first["records"] == [alpha, beta] and first["pages"] == 1 and first["duplicates"] == 1
        assert first["next"] == base + "/p2" and not first["complete"] and first["fetched_this_run"] == 1
        assert calls == ["/p1"]
        checkpoint = state.read_bytes()
        correct_second = copy.deepcopy(replies["/p2"])
        bad_pages = [
            {"items": [gamma, {"id": "β", "score": True}], "next": base + "/p3"},
            {"items": [gamma, {"id": "gamma", "active": True}], "next": base + "/p3"},
            {"items": [gamma], "next": base + "/p1"},
            {"items": [gamma], "next": base + "/p2"},
            {"items": [gamma], "next": foreign + "/should-not-fetch"},
            {"items": [gamma], "next": "/p3"},
            {"items": [gamma], "next": base + "/%bad%escape"},
            {"items": [gamma]},
            {"items": {}, "next": None},
            {"items": [{"id": 1}], "next": None},
            {"items": [{"id": "bad\nidentifier"}], "next": None},
            {"items": [gamma], "next": None, "extra": True},
        ]
        for invalid in bad_pages:
            replies["/p2"] = {"page": invalid}
            rejected = run(code=1)
            assert rejected["error"] == {"kind": "page", "url": base + "/p2", "status": 200}
            assert rejected["records"] == [alpha, beta] and rejected["pages"] == 1
            assert state.read_bytes() == checkpoint
        for invalid, kind, status in [
            ({"status": 503}, "http", 503),
            ({"status": 302, "location": base + "/unexpected-follow"}, "http", 302),
            ({"disconnect": True}, "transport", 0),
            ({"raw": b"x" * 8193}, "transport", 0),
            ({"raw": b"\xff"}, "transport", 0),
            ({"raw": b"{broken"}, "page", 200),
        ]:
            replies["/p2"] = invalid
            rejected = run(code=1)
            assert rejected["error"] == {"kind": kind, "url": base + "/p2", "status": status}
            assert state.read_bytes() == checkpoint
        assert not foreign_calls and "/unexpected-follow" not in calls
        replies["/p2"] = correct_second
        before_calls = len(calls)
        final = run({"HARVEST_STEPS": "100"})
        assert calls[before_calls:] == ["/p2", "/p3", "/p4"]
        assert final == {
            "complete": True,
            "next": None,
            "error": None,
            "pages": 4,
            "records": [alpha, beta, gamma, delta],
            "count": 4,
            "duplicates": 3,
            "fetched_this_run": 3,
        }
        observations["complete"] = final
        complete_state = state.read_bytes()
        before_calls = len(calls)
        repeated = run()
        assert repeated["fetched_this_run"] == 0 and state.read_bytes() == complete_state and len(calls) == before_calls
        assert repeated["records"] == final["records"]
        old_report = report_path.read_bytes()
        for changed in [
            {**policy, "start": base + "/p2"},
            {**policy, "max_records": 11},
            {**policy, "max_pages": True},
            {**policy, "start": "http://user@localhost/"},
            {**policy, "start": "http://localhost:99999/"},
            {**policy, "unexpected": 1},
        ]:
            config.write_text(json.dumps(changed))
            assert application.run(directory, settings).returncode != 0
            assert (
                state.read_bytes() == complete_state
                and report_path.read_bytes() == old_report
                and len(calls) == before_calls
            )
        config.write_text(json.dumps(policy))
        for damage in ["duplicate", "counts", "cursor", "chain", "policy"]:
            corrupt = json.loads(complete_state)
            if damage == "duplicate":
                corrupt["records"][1] = corrupt["records"][0]
            elif damage == "counts":
                corrupt["pages"][0]["added"] = 1
            elif damage == "cursor":
                corrupt["next"] = base + "/p1"
            elif damage == "chain":
                corrupt["pages"][1]["url"] = base + "/p1"
            else:
                corrupt["policy"]["max_pages"] = 7
            state.write_text(json.dumps(corrupt))
            before = state.read_bytes()
            assert application.run(directory, settings).returncode != 0
            assert (
                state.read_bytes() == before and report_path.read_bytes() == old_report and len(calls) == before_calls
            )
        state.write_bytes(complete_state)
        report_path.unlink()
        report_path.symlink_to(state)
        assert application.run(directory, settings).returncode != 0
        assert state.read_bytes() == complete_state and len(calls) == before_calls
        report_path.unlink()

        crash_calls = {}
        for boundary in ["before_checkpoint", "after_checkpoint"]:
            interrupted = directory / (boundary + ".json")
            crash_settings = dict(settings, HARVEST_STATE=str(interrupted), HARVEST_STOP=boundary)
            assert application.run(directory, crash_settings).returncode == 75
            expected_pages = 0 if boundary == "before_checkpoint" else 1
            assert len(json.loads(interrupted.read_text())["pages"]) == expected_pages
            before_calls = len(calls)
            result = application.run(directory, dict(crash_settings, HARVEST_STOP="", HARVEST_STEPS="100"))
            assert result.returncode == 0, result.stderr
            expected_calls = ["/p1", "/p2", "/p3", "/p4"] if expected_pages == 0 else ["/p2", "/p3", "/p4"]
            assert calls[before_calls:] == expected_calls
            assert json.loads(interrupted.read_text())["records"] == [alpha, beta, gamma, delta]
            crash_calls[boundary] = expected_calls
        observations["interruptions"] = crash_calls

        for name, patch, expected_pages, expected_records, kind, expected_calls in [
            ("pages", {"max_pages": 1}, 1, 2, "page_budget", ["/p1"]),
            ("records", {"max_records": 2}, 1, 2, "page", ["/p1", "/p2"]),
            ("page-size", {"page_size": 2}, 0, 0, "page", ["/p1"]),
        ]:
            config.write_text(json.dumps({**policy, **patch}))
            limited = directory / ("limited-" + name + ".json")
            before_calls = len(calls)
            result = application.run(directory, dict(settings, HARVEST_STATE=str(limited), HARVEST_STEPS="100"))
            assert result.returncode == 1, result.stderr
            limited_report = json.loads(Path(str(limited) + ".report.json").read_text())
            assert limited_report["error"]["kind"] == kind
            assert limited_report["pages"] == expected_pages and limited_report["count"] == expected_records
            assert calls[before_calls:] == expected_calls
        observations["invalid_pages_rejected"] = len(bad_pages)
        observations["network_failures_rejected"] = 6
        observations["capacity_checks"] = 3
    return observations
