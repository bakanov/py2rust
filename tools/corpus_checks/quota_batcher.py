"""Scripted quotas, independently calculated deadlines, and durable-receipt crash tests."""

import contextlib
import copy
import http.server
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def api() -> Iterator[tuple[str, dict, list]]:
    routes = {}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            calls.append((self.path, time.time(), {name.lower(): value for name, value in self.headers.items()}))
            route = routes.get(self.path, {"status": 404})
            if isinstance(route, list):
                route = route.pop(0) if len(route) > 1 else route[0]
            if route.get("disconnect"):
                self.close_connection = True
                return
            body = route.get("raw", json.dumps(route.get("value", {"path": self.path}), ensure_ascii=False).encode())
            status = route.get("status", 200)
            if status == 204:
                body = b""
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(route.get("length", len(body))))
            for name, value in route.get("headers", {}).items():
                self.send_header(name, value)
            self.end_headers()
            time.sleep(route.get("delay", 0))
            with contextlib.suppress(OSError):
                # UTF-8 can straddle transport writes; only complete bytes are decoded.
                if route.get("split"):
                    self.wfile.write(body[:1])
                    self.wfile.flush()
                    time.sleep(0.01)
                    self.wfile.write(body[1:])
                else:
                    self.wfile.write(body)
            return

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", routes, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def check(application: Application, directory: Path) -> dict:
    observations = {}
    epoch = 1700000000.0
    with api() as (url, routes, calls):

        def setup(name: str, requests: list[dict] | None = None, **policy: object) -> tuple[Path, dict]:
            folder = directory / name
            folder.mkdir()
            (folder / "batch.json").write_text(json.dumps({"base_url": url + "/api/", **policy}))
            (folder / "requests.json").write_text(
                json.dumps(
                    requests
                    or [
                        {"id": "first", "url": "/first"},
                        {"id": "second", "url": "/second"},
                    ]
                )
            )
            return folder, {"BATCH_IMPORT": "requests.json", "BATCH_NOW": str(epoch)}

        def report(folder: Path) -> dict:
            return json.loads((folder / "batch-state.json.report.json").read_text())

        def run(folder: Path, settings: dict, at: float = epoch, code: int = 0, **extra: str) -> dict:
            result = application.run(folder, {**settings, "BATCH_NOW": str(at), **extra})
            assert result.returncode == code, (folder.name, result.stdout, result.stderr)
            value = report(folder)
            assert json.loads(result.stdout) == value["counts"]
            for entry in value["jobs"]:
                assert entry["job"]["url"].startswith(url + "/")
            return value

        def paths(start: int = 0) -> list[str]:
            return [item[0] for item in calls[start:]]

        requests = [{"id": name, "url": "/" + name} for name in ["a", "b", "c", "d"]]
        folder, settings = setup("main", requests)
        routes.update(
            {
                "/a": {
                    "value": {"name": "世界😀", "roles": ["reader"]},
                    "split": True,
                    "headers": {"X-RateLimit-Remaining": "01", "X-RateLimit-Reset": str(int(epoch + 10))},
                },
                "/b": [
                    {"status": 429, "headers": {"Retry-After": "0005"}},
                    {
                        "value": [1, 2, None],
                        "headers": {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(epoch + 20))},
                    },
                ],
                "/c": [
                    {"status": 503, "headers": {"Retry-After": "Tue, 14 Nov 2023 22:13:50 GMT"}},
                    {"value": True},
                ],
                "/d": {"status": 204},
            }
        )
        initial = run(folder, settings, BATCH_MODE="inspect")
        assert initial["jobs"] == [] and not (folder / "batch-state.json").exists() and calls == []
        first = run(folder, settings)
        assert first["counts"] == {"complete": 1, "pending": 3, "failed": 0, "inflight": 0}
        assert first["not_before"] == epoch + 5 and paths() == ["/a", "/b"]
        assert first["jobs"][0]["result"] == {"name": "世界😀", "roles": ["reader"]}
        assert first["jobs"][1]["next_at"] == epoch + 5
        assert run(folder, settings, epoch + 4.999)["counts"] == first["counts"] and len(calls) == 2
        second = run(folder, settings, epoch + 5)
        assert second["not_before"] == epoch + 20 and second["counts"]["complete"] == 2 and len(calls) == 3
        assert run(folder, settings, epoch + 19.999)["counts"]["complete"] == 2 and len(calls) == 3
        third = run(folder, settings, epoch + 20)
        assert third["not_before"] == epoch + 30 and paths() == ["/a", "/b", "/b", "/c"]
        assert run(folder, settings, epoch + 29.999)["counts"]["complete"] == 2 and len(calls) == 4
        final = run(folder, settings, epoch + 30)
        assert final["counts"] == {"complete": 4, "pending": 0, "failed": 0, "inflight": 0}
        assert [item["result"] for item in final["jobs"]] == [
            {"name": "世界😀", "roles": ["reader"]},
            [1, 2, None],
            True,
            None,
        ]
        assert [item["attempts"] for item in final["jobs"]] == [1, 2, 2, 1]
        saved = (folder / "batch-state.json").read_bytes()
        run(folder, settings, epoch + 31)
        assert (folder / "batch-state.json").read_bytes() == saved and len(calls) == 6
        observations["quota_resume"] = {
            "paths": paths(),
            "counts": final["counts"],
            "attempts": [1, 2, 2, 1],
            "deadlines": [first["not_before"], second["not_before"], third["not_before"]],
        }
        assert all(item[2].get("accept-encoding") == "identity" for item in calls)
        assert all(item[2].get("accept") == "application/json" for item in calls)

        # Imports are idempotent; a conflict invalidates the entire proposed import.
        (folder / "requests.json").write_text(
            json.dumps([{"id": "new", "url": "/new"}, {"id": "a", "url": "/changed"}])
        )
        invalid = application.run(folder, settings)
        assert invalid.returncode != 0 and (folder / "batch-state.json").read_bytes() == saved and len(calls) == 6
        routes["/new"] = {"value": "added"}
        (folder / "requests.json").write_text(json.dumps(requests + [{"id": "new", "url": "/x/../new#fragment"}]))
        added = run(folder, settings, epoch + 31)
        assert added["counts"]["complete"] == 5 and paths()[6:] == ["/new"]

        # All three HTTP date forms and success responses share the same global gate.
        date_forms = ["Tue, 14 Nov 2023 22:13:30 GMT", "Tuesday, 14-Nov-23 22:13:30 GMT", "Tue Nov 14 22:13:30 2023"]
        for index, value in enumerate(date_forms):
            case, env = setup("date-" + str(index))
            routes.update({"/first": {"headers": {"Retry-After": value}}, "/second": {}})
            start = len(calls)
            paused = run(case, env)
            assert paused["not_before"] == epoch + 10 and paths(start) == ["/first"]
            run(case, env, epoch + 9.999)
            assert paths(start) == ["/first"]
            assert run(case, env, epoch + 10)["counts"]["complete"] == 2 and paths(start) == ["/first", "/second"]
        observations["http_date_forms"] = len(date_forms)

        # The stricter of Retry-After, reset time and configured backoff wins.
        for index, headers in enumerate(
            [
                {"Retry-After": "7", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(epoch + 12))},
                {"Retry-After": "12", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(epoch + 7))},
                {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"},
                {"Retry-After": "Sun, 06 Nov 1994 08:49:37 GMT"},
            ]
        ):
            case, env = setup("combined-" + str(index))
            routes.update({"/first": {"headers": headers}, "/second": {}})
            paused = run(case, env)
            expected = epoch + [12, 12, 2, 0][index]
            assert paused["not_before"] == expected
            assert paused["counts"]["complete"] == (2 if index == 3 else 1)
            assert run(case, env, expected)["counts"]["complete"] == 2

        # Per-request retries let unrelated due work proceed; permanent errors never replay.
        case, env = setup("exhaustion", attempts=3)
        routes.update({"/first": {"status": 500}, "/second": {"value": "done"}})
        start = len(calls)
        one = run(case, env)
        assert paths(start) == ["/first", "/second"] and one["jobs"][0]["next_at"] == epoch + 2
        two = run(case, env, epoch + 2)
        assert two["jobs"][0]["next_at"] == epoch + 6
        assert run(case, env, epoch + 5.99)["jobs"][0]["attempts"] == 2
        exhausted = run(case, env, epoch + 6, code=1)
        assert exhausted["counts"] == {"complete": 1, "failed": 1, "pending": 0, "inflight": 0}
        assert run(case, env, epoch + 100, code=1) == exhausted and len(calls) - start == 4
        observations["exhausted_attempts"] = exhausted["jobs"][0]["attempts"]

        failures = []
        deep = None
        for _ in range(26):
            deep = [deep]
        for index, (route, state, error) in enumerate(
            [
                ({"disconnect": True}, "pending", "transport"),
                ({"status": 408}, "pending", "http"),
                ({"status": 429}, "pending", "http"),
                ({"status": 400}, "failed", "http"),
                ({"status": 302, "headers": {"Location": url + "/unexpected"}}, "failed", "http"),
                ({"raw": b"{broken"}, "failed", "invalid JSON result"),
                ({"raw": b"\xff"}, "failed", "invalid JSON result"),
                ({"raw": b"NaN"}, "failed", "invalid JSON result"),
                ({"value": deep}, "failed", "invalid JSON result"),
                ({"value": list(range(4096))}, "failed", "invalid JSON result"),
                ({"headers": {"Content-Encoding": "gzip"}}, "failed", "invalid JSON result"),
                ({"raw": b'"' + b"x" * 65536 + b'"', "headers": {"Retry-After": "10"}}, "pending", "transport"),
                ({"raw": b"{}", "length": 100, "headers": {"Retry-After": "10"}}, "pending", "transport"),
            ]
        ):
            case, env = setup("failure-" + str(index), [{"id": "first", "url": "/first"}])
            routes["/first"] = route
            value = run(case, env, code=1 if state == "failed" else 0)
            receipt = value["jobs"][0]
            assert receipt["state"] == state and receipt["error"] == error and receipt["result"] is None
            if index >= 11:
                assert value["not_before"] == receipt["next_at"] == epoch + 10
                start = len(calls)
                run(case, env, epoch + 9.9)
                assert len(calls) == start
            failures.append({key: receipt[key] for key in ["state", "error", "status"]})
        assert "/unexpected" not in paths()
        observations["failures"] = failures

        # An invalid quota stops the queue but does not discard an already obtained result.
        invalid_headers = [
            {"Retry-After": "-1"},
            {"Retry-After": "1.2"},
            {"Retry-After": "9" * 64},
            {"Retry-After": "Wed, 14 Nov 2023 22:13:30 GMT"},
            {"Retry-After": ""},
            {"X-RateLimit-Remaining": "0"},
            {"X-RateLimit-Reset": "123"},
            {"X-RateLimit-Remaining": "-1", "X-RateLimit-Reset": "123"},
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1.2"},
        ]
        for index, headers in enumerate(invalid_headers):
            case, env = setup("headers-" + str(index))
            routes.update({"/first": {"value": "retained", "headers": headers}, "/second": {}})
            start = len(calls)
            stopped = run(case, env, code=1)
            assert stopped["blocked"] == "invalid quota headers" and stopped["jobs"][0]["result"] == "retained"
            assert stopped["counts"]["complete"] == 1 and paths(start) == ["/first"]
            assert run(case, env, epoch + 100, code=1) == stopped and paths(start) == ["/first"]
            run(case, env, epoch + 100, BATCH_MODE="recover")
            assert paths(start) == ["/first"]
            assert run(case, env, epoch + 100)["counts"]["complete"] == 2 and paths(start) == ["/first", "/second"]
        observations["invalid_quota_cases"] = len(invalid_headers)

        # Claims survive interruptions. Uncertain requests require explicit recovery.
        crashes = {}
        for point in ["after_claim", "after_response", "after_checkpoint"]:
            case, env = setup("crash-" + point)
            routes.update({"/first": {"value": "first result"}, "/second": {"value": "second result"}})
            start = len(calls)
            interrupted = application.run(case, {**env, "BATCH_STOP": point})
            assert interrupted.returncode == 75, interrupted.stderr
            stored = json.loads((case / "batch-state.json").read_text())
            if point != "after_checkpoint":
                assert stored["jobs"][0]["state"] == "inflight"
                blocked = run(case, env, code=1)
                assert blocked["blocked"] == "unacknowledged request"
                assert paths(start) == ([] if point == "after_claim" else ["/first"])
                recovered = run(case, env, BATCH_MODE="recover")
                assert recovered["jobs"][0]["next_at"] == epoch + 2
                # Recovery never sends; before its deadline only unrelated work is due.
                early = run(case, env, epoch + 1)
                assert early["counts"]["complete"] == 1 and paths(start)[-1] == "/second"
                completed = run(case, env, epoch + 2)
                assert completed["counts"]["complete"] == 2 and completed["jobs"][0]["attempts"] == 2
            else:
                assert stored["jobs"][0]["state"] == "complete"
                completed = run(case, env)
                assert completed["counts"]["complete"] == 2 and paths(start) == ["/first", "/second"]
            crashes[point] = paths(start)
        observations["interruptions"] = crashes

        # An explicit recovery does not erase a known, future global quota deadline.
        case, env = setup("recover-keeps-deadline")
        routes["/first"] = {"headers": {"Retry-After": "12", "X-RateLimit-Remaining": "bad", "X-RateLimit-Reset": "0"}}
        value = run(case, env, code=1)
        # A malformed field must not erase the separately valid Retry-After value.
        assert value["not_before"] == epoch + 12
        run(case, env, BATCH_MODE="recover")
        start = len(calls)
        run(case, env, epoch + 11)
        assert len(calls) == start
        assert run(case, env, epoch + 12)["counts"]["complete"] == 2

        # Bound work per pass without changing the persisted policy.
        case, env = setup("limit")
        routes.update({"/first": {}, "/second": {}})
        assert run(case, env, BATCH_LIMIT="1")["counts"]["complete"] == 1
        assert run(case, env, BATCH_LIMIT="1")["counts"]["complete"] == 2

        # A real response delay verifies that delta seconds start after receipt, not pass start.
        case, env = setup("wall-clock")
        routes.update({"/first": {"headers": {"Retry-After": "1"}, "delay": 0.12}, "/second": {}})
        started = time.time()
        wall = run(case, env, BATCH_NOW="")
        assert wall["not_before"] >= started + 1.1
        start = len(calls)
        run(case, env, BATCH_NOW="")
        assert len(calls) == start
        time.sleep(max(0, wall["not_before"] - time.time()) + 0.01)
        assert run(case, env, BATCH_NOW="")["counts"]["complete"] == 2
        observations["real_deadline_respected"] = True

        # Invalid configuration/imports, clock rollback and checkpoint corruption make no requests.
        case, env = setup("validation")
        good_policy = json.loads((case / "batch.json").read_text())
        for patch in [
            {"attempts": 0},
            {"attempts": 9},
            {"backoff": 0},
            {"timeout_ms": 0},
            {"max_body": 65537},
            {"base_url": "file:///tmp/private"},
            {"typo": True},
        ]:
            (case / "batch.json").write_text(json.dumps({**good_policy, **patch}))
            start = len(calls)
            assert application.run(case, env).returncode != 0 and len(calls) == start
            assert not (case / "batch-state.json").exists()
        (case / "batch.json").write_text(json.dumps(good_policy))
        for incoming in [
            [{"id": "x", "url": "http://other.example/"}],
            [{"id": "bad id", "url": "/x"}],
            [{"id": "x", "url": "/x", "method": "POST"}],
            [{"id": "x", "url": "/x"}] * 101,
        ]:
            (case / "requests.json").write_text(json.dumps(incoming))
            start = len(calls)
            assert application.run(case, env).returncode != 0 and len(calls) == start
            assert not (case / "batch-state.json").exists()
        (case / "requests.json").write_text(json.dumps([{"id": "first", "url": "/first"}]))
        routes["/first"] = {"status": 500}
        run(case, env)
        good = json.loads((case / "batch-state.json").read_text())
        corruptions = []
        for key, value in [("version", 2), ("last_at", -1), ("jobs", [good["jobs"][0], good["jobs"][0]])]:
            corruptions.append({**good, key: value})
        for key, value in [
            ("attempts", 4),
            ("next_at", epoch),
            ("status", 700),
            ("state", "unknown"),
            ("result", {"injected": True}),
            ("error", "invalid JSON result"),
        ]:
            corrupted = copy.deepcopy(good)
            corrupted["jobs"][0][key] = value
            corruptions.append(corrupted)
        for corrupted in corruptions:
            (case / "batch-state.json").write_text(json.dumps(corrupted))
            saved = (case / "batch-state.json").read_bytes()
            start = len(calls)
            assert application.run(case, env).returncode != 0 and len(calls) == start
            assert (case / "batch-state.json").read_bytes() == saved
        (case / "batch-state.json").write_text(json.dumps(good))
        saved = (case / "batch-state.json").read_bytes()
        for extra in [{"BATCH_NOW": str(epoch - 1)}, {"BATCH_LIMIT": "0"}, {"BATCH_MODE": "unknown"}]:
            start = len(calls)
            assert application.run(case, {**env, **extra}).returncode != 0 and len(calls) == start
            assert (case / "batch-state.json").read_bytes() == saved
        observations["corrupt_checkpoints_rejected"] = len(corruptions)

        for name, link in [("symlink", "symlink_to"), ("hardlink", "hardlink_to")]:
            case, env = setup("alias-" + name)
            target = case / "batch.json"
            output = case / "batch-state.json"
            getattr(output, link)(target)
            saved = target.read_bytes()
            start = len(calls)
            assert application.run(case, env).returncode != 0 and len(calls) == start and target.read_bytes() == saved
        return observations
