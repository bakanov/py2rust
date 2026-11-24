"""Independent circuit trace, binary forwarding and crash/restart assertions."""

import contextlib
import copy
import http.client
import http.server
import json
import math
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from .common import Application, Server


@contextlib.contextmanager
def upstream() -> Iterator[tuple[str, dict, list]]:
    routes = {}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            route = routes.get(urlsplit(self.path).path, {})
            event = {
                "method": self.command,
                "path": self.path,
                "body": body.hex(),
                "headers": {name.lower(): value for name, value in self.headers.items()},
            }
            if "snapshot" in route:
                event["snapshot"] = json.loads(route["snapshot"].read_text())["circuits"][0]
            calls.append(event)
            if "arrived" in route:
                route["arrived"].set()
            if "release" in route:
                route["release"].wait(timeout=5)
            if route.get("disconnect"):
                self.close_connection = True
                return
            time.sleep(route.get("delay", 0))
            status = route.get("status", 200)
            output = route.get("raw", body if route.get("echo") else json.dumps({"upstream": status}).encode())
            if status in [204, 304]:
                output = b""
            self.send_response(status)
            self.send_header("Content-Length", str(route.get("length", len(output))))
            for name, value in route.get("headers", {"Content-Type": "application/json"}).items():
                self.send_header(name, value)
            self.end_headers()
            with contextlib.suppress(OSError):
                self.wfile.write(output)
            return

        do_POST = do_GET
        do_PUT = do_GET
        do_DELETE = do_GET

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", routes, calls
    finally:
        for route in routes.values():
            if "release" in route:
                route["release"].set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


class Oracle:
    def __init__(self, threshold: int = 2, cooldown: float = 3.0, probes: int = 2) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self.probes = probes
        self.phase = "closed"
        self.failures = self.successes = self.calls = self.failed_calls = self.rejected = 0
        self.retry_at = 0.0
        self.history = []
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def transition(self, target: str, now: float, reason: str) -> None:
        self.history.append(
            {"sequence": len(self.history) + 1, "at": now, "before": self.phase, "after": target, "reason": reason}
        )
        self.phase = target
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def request(self, now: float, status: int) -> int:
        if self.phase == "open":
            if now < self.retry_at:
                self.rejected += 1
                return 503
            self.transition("half_open", now, "probe")
            self.retry_at = 0.0
            self.successes = 0
        self.calls += 1
        if status in [408, 429] or status >= 500:
            self.failed_calls += 1
            self.failures = min(self.threshold, self.failures + 1)
            self.successes = 0
            if self.phase == "half_open" or self.failures == self.threshold:
                self.retry_at = now + self.cooldown
                self.transition("open", now, "http")
        else:
            self.failures = 0
            if self.phase == "half_open":
                self.successes += 1
                if self.successes == self.probes:
                    self.successes = 0
                    self.transition("closed", now, "recovered")
        return status

    def verify(self, record: dict) -> None:
        for field in ["phase", "failures", "successes", "retry_at", "calls", "failed_calls", "rejected"]:
            assert record[field] == getattr(self, field), (field, record, vars(self))
        assert record["history"] == self.history[-20:] and record["sequence"] == len(self.history)
        assert not record["inflight"]
        return  # noqa: PLR1711 - explicit return required by repository guidelines


def check(app: Application, directory: Path) -> dict:
    observations = {}
    with upstream() as (url, routes, calls):

        def setup(name: str, **changes: object) -> tuple[Path, dict, Path, Path]:
            folder = directory / name
            folder.mkdir()
            policy = {
                "threshold": 2,
                "cooldown": 3.0,
                "probes": 2,
                "timeout_ms": 1000,
                "max_body": 65536,
                "routes": [
                    {
                        "id": "alpha",
                        "path": "/alpha",
                        "url": url + "/up/alpha",
                        "methods": ["GET", "POST", "PUT", "DELETE"],
                    },
                    {"id": "beta", "path": "/beta", "url": url + "/up/beta", "methods": ["GET"]},
                ],
                **changes,
            }
            (folder / "gateway.json").write_text(json.dumps(policy))
            clock = folder / "clock.json"
            clock.write_text("1000")
            return folder, {"GATEWAY_CLOCK": str(clock), "GATEWAY_PORT": "0"}, clock, folder / "gateway-state.json"

        def state(server: Server) -> dict:
            response = server.request("GET", "/_gateway/state")
            assert response.status == 200, response.body
            assert response.headers["cache-control"] == "no-store"
            return response.json()

        folder, settings, clock, path = setup("trace")
        oracle = Oracle()
        trace = [
            (1000, 500),
            (1000.25, 200),
            (1001, 500),
            (1002, 503),
            (1002.5, 200),
            (1004.999, 200),
            (1005, 200),
            (1005.1, 502),
            (1008.099, 200),
            (1008.1, 404),
            (1008.2, 200),
            (1009, 429),
            (1010, 408),
            (1013, 204),
            (1013.1, 302),
        ]
        observed_trace = []
        # Restart with open and half-open circuits, preserving exact deadlines and probe counts.
        for group in [trace[:4], trace[4:7], trace[7:]]:
            with app.server(folder, settings) as gateway:
                before = state(gateway)
                oracle.verify(before["circuits"][0])
                for now, status in group:
                    clock.write_text(str(now))
                    routes["/up/alpha"] = {
                        "status": status,
                        "snapshot": path,
                        "headers": {"Location": "/not-followed", "Content-Type": "application/json"},
                    }
                    count = len(calls)
                    expected = oracle.request(now, status)
                    response = gateway.request("GET", "/alpha")
                    assert response.status == expected, response.body
                    record = state(gateway)["circuits"][0]
                    oracle.verify(record)
                    assert response.headers["x-circuit-state"] == record["phase"]
                    if len(calls) == count:
                        assert response.json()["error"] == "circuit open" and oracle.phase == "open"
                        assert response.headers["retry-after"] == str(max(1, math.ceil(oracle.retry_at - now)))
                    else:
                        assert len(calls) == count + 1 and calls[-1]["snapshot"]["inflight"]
                        if calls[-1]["snapshot"]["phase"] == "half_open":
                            assert now >= before["circuits"][0]["retry_at"]
                    observed_trace.append(
                        [now, status, expected, record["phase"], record["failures"], record["successes"]]
                    )
                    assert gateway.request("GET", "/beta").status == 200
                    assert state(gateway)["circuits"][1]["phase"] == "closed"
                    before = state(gateway)
        assert all(item["path"] in ["/up/alpha", "/up/beta"] for item in calls)
        observations["transition_trace"] = observed_trace
        observations["history"] = oracle.history

        # Exact binary payloads, repeated query fields, selected headers and all supported methods.
        folder, settings, clock, path = setup("forwarding")
        body = bytes.fromhex("00ff807ff09f9880") + b"\r\nbytes"
        suffix = "?tag=a&tag=b&blank=&q=a+b&slash=%2f%2F&u=%E4%B8%96%E7%95%8C"
        routes["/up/alpha"] = {
            "status": 201,
            "echo": True,
            "headers": {
                "Content-Type": "application/custom",
                "ETag": '"version-1"',
                "X-Internal": "not-forwarded",
                "Cache-Control": "private",
                "Connection": "keep-alive, ETag",
                "Keep-Alive": "timeout=5",
            },
        }
        with app.server(folder, settings) as gateway:
            for method in ["POST", "PUT", "DELETE", "GET"]:
                response = gateway.request(
                    method,
                    "/alpha" + suffix,
                    body,
                    {
                        "Content-Type": "application/custom",
                        "Authorization": "Bearer TOP-SECRET",
                        "Idempotency-Key": "stable-key",
                        "X-Request-Id": "hop-specific",
                        "X-Unlisted": "hidden",
                        "Connection": "keep-alive, X-Request-Id",
                    },
                )
                assert response.status == 201 and response.body == body
                assert response.headers["content-type"] == "application/custom"
                assert response.headers["cache-control"] == "private"
                assert (
                    "etag" not in response.headers
                    and "x-internal" not in response.headers
                    and "keep-alive" not in response.headers
                )
                received = calls[-1]
                assert (
                    received["path"] == "/up/alpha" + suffix
                    and received["method"] == method
                    and received["body"] == body.hex()
                )
                assert received["headers"]["authorization"] == "Bearer TOP-SECRET"
                assert received["headers"]["idempotency-key"] == "stable-key"
                assert received["headers"]["content-type"] == "application/custom"
                assert received["headers"]["accept-encoding"] == "identity"
                assert received["headers"]["via"] == "1.1 py2rust-gateway"
                assert "x-request-id" not in received["headers"] and "x-unlisted" not in received["headers"]
            assert "TOP-SECRET" not in path.read_text() and "TOP-SECRET" not in json.dumps(state(gateway))
            # Both existing outbound transports normalize an empty query to an absent one.
            assert gateway.request("GET", "/alpha?").status == 201 and calls[-1]["path"] == "/up/alpha"
            saved = path.read_bytes()
            count = len(calls)
            for method, target, payload, headers, expected in [
                ("POST", "/beta", b"", {}, 405),
                ("GET", "/missing", b"", {}, 404),
                ("POST", "/_gateway/state", b"", {}, 405),
                ("GET", "/alpha", b"", {"Via": "1.1 py2rust-gateway"}, 508),
                ("GET", "/alpha?bad=%zz", b"", {}, 400),
                ("GET", url + "/alpha", b"", {}, 400),
                ("POST", "/alpha", b"x" * 65537, {}, 413),
                ("GET", "/alpha?" + "x" * 8192, b"", {}, 414),
            ]:
                response = gateway.request(method, target, payload, headers)
                assert response.status == expected, (target[:100], response.status, response.body)
                if expected == 405:
                    assert response.headers["allow"] == "GET"
            assert len(calls) == count and path.read_bytes() == saved
            clock.write_text("999")
            assert gateway.request("GET", "/alpha").status == 500 and len(calls) == count and path.read_bytes() == saved
        observations["forwarding"] = {
            "methods": ["GET", "POST", "PUT", "DELETE"],
            "body_hex": body.hex(),
            "query": suffix,
        }

        # Transport/body/deadline failures open at the configured threshold and are not retried.
        failures = []
        for name, route in [
            ("disconnect", {"disconnect": True}),
            ("truncated", {"raw": b"{}", "length": 100}),
            ("overflow", {"raw": b"x" * 1025}),
            ("timeout", {"delay": 0.2}),
        ]:
            folder, settings, clock, path = setup(name, threshold=1, timeout_ms=50, max_body=1024)
            routes["/up/alpha"] = route
            start = len(calls)
            with app.server(folder, settings) as gateway:
                began = time.monotonic()
                response = gateway.request("POST", "/alpha", b"mutation")
                assert response.status == 502 and response.json()["error"] == "upstream transport failure"
                assert time.monotonic() - began < 2
                record = state(gateway)["circuits"][0]
                assert record["phase"] == "open" and record["failed_calls"] == record["calls"] == 1
                assert record["last_error"] == "transport" and record["last_status"] == 0 and record["retry_at"] == 1003
                assert gateway.request("GET", "/alpha").status == 503 and len(calls) == start + 1
                failures.append({"case": name, "phase": record["phase"], "error": record["last_error"]})
        observations["transport_failures"] = failures

        # Competing recovery requests cannot both probe a circuit that the first probe reopens.
        folder, settings, clock, path = setup("competing", threshold=1)
        routes["/up/alpha"] = {"status": 500}
        with app.server(folder, settings) as gateway:
            assert gateway.request("GET", "/alpha").status == 500
            clock.write_text("1003")
            routes["/up/alpha"] = {"status": 500, "delay": 0.1, "snapshot": path}
            start = len(calls)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(gateway.request, "GET", "/alpha") for _ in range(2)]
                statuses = sorted(future.result().status for future in futures)
            assert statuses == [500, 503] and len(calls) == start + 1
            assert calls[-1]["snapshot"]["phase"] == "half_open" and calls[-1]["snapshot"]["inflight"]
            record = state(gateway)["circuits"][0]
            assert record["phase"] == "open" and record["retry_at"] == 1006 and record["rejected"] == 1
        observations["competing_probes"] = statuses

        # Each fault boundary is observable; recovery never resends a saved request body.
        interruptions = {}
        for point in ["after_claim", "after_response", "after_checkpoint"]:
            folder, settings, clock, path = setup("fault-" + point, threshold=1)
            routes["/up/alpha"] = {"echo": True}
            start = len(calls)
            with app.server(folder, {**settings, "GATEWAY_STOP": point}) as gateway:
                assert gateway.request("POST", "/alpha", b"do-once").status == 500
                record = state(gateway)["circuits"][0]
                assert record["inflight"] == (point != "after_checkpoint")
                assert len(calls) == start + (0 if point == "after_claim" else 1)
                if point != "after_checkpoint":
                    assert gateway.request("GET", "/beta").status == 503 and len(calls) == start + (
                        point == "after_response"
                    )
            with app.server(folder, settings) as gateway:
                record = state(gateway)["circuits"][0]
                assert not record["inflight"] and record["calls"] == 1
                assert len(calls) == start + (0 if point == "after_claim" else 1)
                if point != "after_checkpoint":
                    assert (
                        record["phase"] == "open"
                        and record["last_error"] == "interrupted"
                        and record["retry_at"] == 1003
                    )
                    assert gateway.request("GET", "/alpha").status == 503
                    clock.write_text("1003")
                    assert gateway.request("GET", "/alpha").status == 200
                    assert state(gateway)["circuits"][0]["phase"] == "half_open"
                    assert gateway.request("GET", "/alpha").status == 200
                assert state(gateway)["circuits"][0]["phase"] == "closed"
            assert [event["body"] for event in calls[start:] if event["method"] == "POST"] == (
                [] if point == "after_claim" else [b"do-once".hex()]
            )
            interruptions[point] = {"calls": len(calls) - start, "recovered_phase": "closed"}
        observations["fault_boundaries"] = interruptions

        # Terminate a real process while an upstream request is held, then recover from its claim.
        folder, settings, clock, path = setup("terminated", threshold=1)
        arrived = threading.Event()
        release = threading.Event()
        routes["/up/alpha"] = {"arrived": arrived, "release": release, "echo": True}
        start = len(calls)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with app.server(folder, settings) as gateway:
                future = pool.submit(gateway.request, "POST", "/alpha", b"unacknowledged")
                assert arrived.wait(timeout=3)
                assert json.loads(path.read_text())["circuits"][0]["inflight"]
            release.set()
            with contextlib.suppress(OSError, http.client.HTTPException):
                future.result(timeout=3)
        assert len(calls) == start + 1
        with app.server(folder, settings) as gateway:
            record = state(gateway)["circuits"][0]
            assert record["phase"] == "open" and record["last_error"] == "interrupted" and len(calls) == start + 1
        observations["terminated_inflight_request"] = "recovered without replay"

        # Long traces keep monotonic sequence IDs and only the last twenty transitions.
        folder, settings, clock, path = setup("retention", threshold=1, probes=1, cooldown=0.25)
        oracle = Oracle(threshold=1, probes=1, cooldown=0.25)
        with app.server(folder, settings) as gateway:
            for index in range(24):
                now = 1000 + index * 0.25
                status = 500 if index % 2 == 0 else 200
                clock.write_text(str(now))
                routes["/up/alpha"] = {"status": status}
                assert gateway.request("GET", "/alpha").status == oracle.request(now, status)
                oracle.verify(state(gateway)["circuits"][0])
            record = state(gateway)["circuits"][0]
            assert record["sequence"] == 36 and len(record["history"]) == 20 and record["history"][0]["sequence"] == 17
            saved = path.read_bytes()
        with app.server(folder, settings) as gateway:
            oracle.verify(state(gateway)["circuits"][0])
        observations["retained_history"] = {"sequence": 36, "first": 17, "count": 20}

        # Corrupted state is rejected before listening or contacting an upstream.
        good = json.loads(saved)
        corruptions = []
        for key, value in [
            ("phase", "invalid"),
            ("retry_at", 1),
            ("failures", 1),
            ("successes", 1),
            ("failed_calls", 999),
            ("calls", -1),
            ("last_status", 700),
            ("sequence", 35),
            ("last_error", "invalid"),
            ("id", "other"),
        ]:
            broken = copy.deepcopy(good)
            broken["circuits"][0][key] = value
            corruptions.append(broken)
        for corrupted in corruptions:
            path.write_text(json.dumps(corrupted))
            before = path.read_bytes()
            count = len(calls)
            assert app.run(folder, settings).returncode != 0 and len(calls) == count and path.read_bytes() == before
        path.write_bytes(saved)
        original_policy = json.loads((folder / "gateway.json").read_text())
        for patch in [
            {"threshold": 0},
            {"cooldown": 0},
            {"probes": 11},
            {"timeout_ms": 0},
            {"max_body": 1048577},
            {"typo": 1},
            {"routes": []},
            {"routes": original_policy["routes"] * 2},
        ]:
            (folder / "gateway.json").write_text(json.dumps({**original_policy, **patch}))
            count = len(calls)
            assert app.run(folder, settings).returncode != 0 and len(calls) == count and path.read_bytes() == saved
        for key, value in [
            ("url", "file:///private"),
            ("url", url + "/?bad"),
            ("path", "/_gateway/state"),
            ("path", "//alpha"),
            ("methods", ["TRACE"]),
            ("methods", ["GET", "GET"]),
        ]:
            invalid = copy.deepcopy(original_policy)
            invalid["routes"][0][key] = value
            (folder / "gateway.json").write_text(json.dumps(invalid))
            assert app.run(folder, settings).returncode != 0 and path.read_bytes() == saved
        (folder / "gateway.json").write_text(json.dumps(original_policy))
        clock.write_text("900")
        assert app.run(folder, settings).returncode != 0 and path.read_bytes() == saved
        observations["corrupt_states_rejected"] = len(corruptions)
        for name, link in [("symlink", "symlink_to"), ("hardlink", "hardlink_to")]:
            folder, settings, clock, path = setup("alias-" + name)
            target = folder / "gateway.json"
            before = target.read_bytes()
            getattr(path, link)(target)
            assert app.run(folder, settings).returncode != 0 and target.read_bytes() == before
        return observations
