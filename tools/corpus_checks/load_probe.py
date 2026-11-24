"""Independent HTTP, concurrency, cancellation and numeric oracles for application 020."""

from __future__ import annotations

import contextlib
import copy
import csv
import hashlib
import io
import json
import math
import threading
import time
from collections import Counter
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import Application


class Fixture:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.release = threading.Event()
        self.routes: dict = {}
        self.calls: list[dict] = []
        self.active = 0
        self.peak = 0
        self.url = ""
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def configure(self, routes: dict) -> None:
        self.idle()
        with self.condition:
            self.routes = routes
            self.calls = []
            self.peak = 0
            self.release.clear()
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def reached(self, count: int) -> None:
        with self.condition:
            assert self.condition.wait_for(lambda: self.active >= count, timeout=5), self.calls
            assert self.active == count
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    def idle(self) -> None:
        with self.condition:
            assert self.condition.wait_for(lambda: self.active == 0, timeout=5), self.calls
        return  # noqa: PLR1711 - explicit return required by repository guidelines


@contextlib.contextmanager
def origin() -> Iterator[Fixture]:
    fixture = Fixture()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            with fixture.condition:
                fixture.calls.append(
                    {"path": self.path, "method": self.command, "body": body, "headers": dict(self.headers)}
                )
                route = fixture.routes.get(self.path, {"status": 404, "body": b"missing"})
                fixture.active += 1
                fixture.peak = max(fixture.peak, fixture.active)
                fixture.condition.notify_all()
            try:
                if route.get("gate"):
                    assert fixture.release.wait(timeout=5), "test controller did not release held requests"
                time.sleep(route.get("delay", 0))
                if route.get("disconnect"):
                    self.close_connection = True
                    return
                payload = route.get("body", b"ok")
                self.send_response(route.get("status", 200))
                self.send_header("Content-Length", str(route.get("length", len(payload))))
                for name, value in route.get("headers", {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                with fixture.condition:
                    fixture.active -= 1
                    fixture.condition.notify_all()
            return

        do_POST = do_GET
        do_PUT = do_GET
        do_DELETE = do_GET

        def log_message(self, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fixture.url = "http://127.0.0.1:" + str(server.server_port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield fixture
    finally:
        fixture.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        fixture.idle()
    return


def policy(fixture: Fixture, count: int = 9, workers: int = 3, **settings: object) -> dict:
    return {
        "targets": [{"id": "a", "url": fixture.url + "/ok"}],
        "schedule": [{"target": "a", "at_ms": 0, "interval_ms": 0, "count": count}],
        "concurrency": workers,
        "timeout_ms": 2000,
        "duration_ms": 4000,
        "max_lag_ms": 2000,
        "buckets_ms": [1, 20, 100, 1000],
        "max_body": 64,
        **settings,
    }


def setup(directory: Path, name: str, config: dict) -> tuple[Path, dict[str, str]]:
    work = directory / name
    work.mkdir()
    path = work / "config.json"
    path.write_text(json.dumps(config))
    return work, {
        "LOAD_CONFIG": str(path),
        "LOAD_REPORT": str(work / "report.json"),
        "LOAD_CANCEL": str(work / "cancel"),
        "LOAD_CA": "",
    }


def aggregate(samples: list[dict], bounds: list[int]) -> dict:
    counts = dict.fromkeys(["ok", "http_error", "transport_error", "cancelled", "late"], 0)
    counts.update(Counter(row["state"] for row in samples))
    attempts = [row for row in samples if row["started_us"] is not None]
    values = sorted(row["latency_us"] for row in attempts)
    latency = None
    if values:
        latency = {
            "min_us": min(values),
            "max_us": max(values),
            "sum_us": sum(values),
            "mean_us": sum(values) // len(values),
            **{f"p{p}_us": values[math.ceil(p / 100 * len(values)) - 1] for p in [50, 95, 99]},
        }
    buckets = []
    previous = -1
    for bound in bounds:
        buckets.append({"le_ms": bound, "count": sum(previous < value <= bound * 1000 for value in values)})
        previous = bound * 1000
    buckets.append({"le_ms": None, "count": sum(value > previous for value in values)})
    return {
        "planned": len(samples),
        "attempted": len(attempts),
        "counts": counts,
        "statuses": dict(Counter(str(row["status"]) for row in attempts)),
        "bytes": sum(row["bytes"] for row in samples),
        "latency": latency,
        "buckets": buckets,
    }


def report(work: Path, config: dict, process: object, exit_code: int) -> dict:
    assert process.returncode == exit_code, (process.stdout, process.stderr)
    value = json.loads((work / "report.json").read_text())
    assert value["format"] == 1 and value["phase"] == "finished"
    assert value["status"] == {0: "passed", 1: "failed", 2: "incomplete"}[exit_code]
    plan = [
        {"id": f"{slot['target']}-{i}-{j}", "target": slot["target"], "at_ms": slot["at_ms"] + j * slot["interval_ms"]}
        for i, slot in enumerate(config["schedule"])
        for j in range(slot["count"])
    ]
    plan.sort(key=lambda row: row["at_ms"])
    assert value["plan"] == plan
    samples = value["samples"]
    assert len(samples) == len(plan) and len({row["id"] for row in samples}) == len(plan)
    for job, sample in zip(plan, samples, strict=True):
        assert (sample["id"], sample["target"], sample["scheduled_ms"]) == (job["id"], job["target"], job["at_ms"])
        assert 0 <= sample["finished_us"] <= value["elapsed_us"]
        if sample["state"] in {"cancelled", "late"}:
            assert sample["started_us"] is None and sample["latency_us"] is None
            assert sample["status"] == 0 and sample["bytes"] == 0 and sample["sha256"] == ""
            assert sample["lateness_us"] == max(0, sample["finished_us"] - job["at_ms"] * 1000)
        else:
            assert sample["started_us"] >= job["at_ms"] * 1000
            assert sample["latency_us"] == sample["finished_us"] - sample["started_us"] >= 0
            assert sample["lateness_us"] == sample["started_us"] - job["at_ms"] * 1000
    bounds = config["buckets_ms"]
    assert value["parameters"] == {key: config[key] for key in value["parameters"]}
    assert value["targets"] == [
        {"id": target["id"], "url": target["url"], "method": target.get("method", "GET")}
        for target in config["targets"]
    ]
    assert value["overall"] == aggregate(samples, bounds)
    assert value["by_target"] == [
        {"target": target["id"], "summary": aggregate([s for s in samples if s["target"] == target["id"]], bounds)}
        for target in config["targets"]
    ]
    assert json.loads(process.stdout) == value["overall"]["counts"]
    rows = list(csv.DictReader(io.StringIO((work / "report.json.csv").read_text())))
    assert len(rows) == len(samples)
    for row, sample in zip(rows, samples, strict=True):
        assert row == {key: "" if item is None else str(item) for key, item in sample.items()}
    return value


def check(app: Application, directory: Path) -> dict:
    peaks = []
    with origin() as fixture:
        for workers in [1, 3, 4]:
            fixture.configure({"/ok": {"gate": True, "delay": 0.01}})
            config = policy(fixture, count=workers * 2 + 1, workers=workers)
            work, env = setup(directory, "workers-" + str(workers), config)
            with ThreadPoolExecutor(max_workers=1) as controller:
                future = controller.submit(app.run, work, env)
                try:
                    fixture.reached(workers)
                    assert not future.done() and len(fixture.calls) == workers
                    assert json.loads((work / "report.json").read_text())["phase"] == "running"
                    assert not (work / "report.json.csv").exists()
                finally:
                    fixture.release.set()
                completed = future.result(timeout=10)
            value = report(work, config, completed, 0)
            fixture.idle()
            assert fixture.peak == workers and len(fixture.calls) == workers * 2 + 1
            assert value["overall"]["counts"]["ok"] == workers * 2 + 1
            peaks.append(fixture.peak)

        fixture.configure({"/ok": {"gate": True}})
        config = policy(fixture)
        work, env = setup(directory, "cancel-active", config)
        with ThreadPoolExecutor(max_workers=1) as controller:
            future = controller.submit(app.run, work, env)
            try:
                fixture.reached(3)
                Path(env["LOAD_CANCEL"]).write_text("cancel")
                time.sleep(0.05)
                assert not future.done(), "active requests must drain before returning results"
                assert len(fixture.calls) == 3 and fixture.active == 3
                assert json.loads((work / "report.json").read_text())["phase"] == "running"
            finally:
                fixture.release.set()
            completed = future.result(timeout=10)
        value = report(work, config, completed, 2)
        fixture.idle()
        assert [row["state"] for row in value["samples"]] == ["ok"] * 3 + ["cancelled"] * 6
        assert {row["reason"] for row in value["samples"][3:]} == {"requested"}
        assert len(fixture.calls) == 3 and fixture.peak == 3
        cancelled = value["overall"]["counts"]

        for mode in ["before", "waiting"]:
            fixture.configure({"/ok": {}})
            config = policy(fixture)
            config["schedule"][0]["at_ms"] = 2000
            work, env = setup(directory, "cancel-" + mode, config)
            if mode == "before":
                Path(env["LOAD_CANCEL"]).touch()
            with ThreadPoolExecutor(max_workers=1) as controller:
                future = controller.submit(app.run, work, env)
                if mode == "waiting":
                    deadline = time.monotonic() + 5
                    while not (work / "report.json").exists():
                        assert time.monotonic() < deadline and not future.done()
                        time.sleep(0.005)
                    time.sleep(0.05)
                    assert not future.done()
                    Path(env["LOAD_CANCEL"]).touch()
                completed = future.result(timeout=1)
            value = report(work, config, completed, 2)
            assert value["overall"]["counts"]["cancelled"] == 9 and not fixture.calls
            assert {row["reason"] for row in value["samples"]} == {"requested"}

        fixture.configure({"/ok": {"delay": 0.35}})
        config = policy(fixture, duration_ms=120, timeout_ms=2000)
        work, env = setup(directory, "deadline", config)
        began = time.monotonic()
        value = report(work, config, app.run(work, env), 2)
        assert time.monotonic() - began < 2
        fixture.idle()
        assert value["overall"]["counts"] == {"ok": 0, "http_error": 0, "transport_error": 3, "cancelled": 6, "late": 0}
        assert [row["reason"] for row in value["samples"][3:]] == ["deadline"] * 6
        assert len(fixture.calls) == 3

        fixture.configure({"/ok": {"delay": 0.12}})
        config = policy(fixture, workers=1, count=5, max_lag_ms=60)
        work, env = setup(directory, "late", config)
        value = report(work, config, app.run(work, env), 2)
        fixture.idle()
        assert [row["state"] for row in value["samples"]] == ["ok"] + ["late"] * 4
        assert [row["reason"] for row in value["samples"][1:]] == ["schedule_lag"] * 4
        assert len(fixture.calls) == 1

        fixture.configure({"/ok": {}, "/second": {"body": b"two"}})
        config = policy(fixture)
        config["targets"].append({"id": "b", "url": fixture.url + "/second"})
        config["schedule"] = [
            {"target": "b", "at_ms": 160, "interval_ms": 100, "count": 2},
            {"target": "a", "at_ms": 0, "interval_ms": 80, "count": 3},
        ]
        work, env = setup(directory, "schedule", config)
        value = report(work, config, app.run(work, env), 0)
        fixture.idle()
        assert [row["id"] for row in value["samples"]] == ["a-1-0", "a-1-1", "b-0-0", "a-1-2", "b-0-1"]
        assert len(fixture.calls) == 5 and fixture.peak <= 3 and value["elapsed_us"] >= 260000

        binary = "hello 世界".encode() + b"\x00\xff"
        routes = {
            "/binary?q=one&q=two": {"body": binary},
            "/created": {"status": 201, "body": b'{"created":true}'},
            "/error": {"status": 503, "body": b"unavailable"},
            "/redirect": {"status": 302, "body": b"moved", "headers": {"Location": "/unexpected"}},
            "/disconnect": {"disconnect": True},
            "/large": {"body": b"x" * 65},
            "/truncated": {"body": b"short", "length": 20},
        }
        fixture.configure(routes)
        config = policy(fixture)
        config["targets"] = [{"id": "case" + str(i), "url": fixture.url + path} for i, path in enumerate(routes)]
        config["targets"][1].update(method="POST", body_hex=b'{"text":"hello"}'.hex(), headers={"X-Test": "secret"})
        config["schedule"] = [
            {"target": target["id"], "at_ms": 0, "interval_ms": 0, "count": 1} for target in config["targets"]
        ]
        work, env = setup(directory, "mixed", config)
        value = report(work, config, app.run(work, env), 1)
        fixture.idle()
        assert [row["state"] for row in value["samples"]] == ["ok"] * 2 + ["http_error"] * 2 + ["transport_error"] * 3
        assert sorted(row["path"] for row in fixture.calls) == sorted(routes)
        for sample, route in zip(value["samples"][:4], list(routes.values())[:4], strict=True):
            assert sample["status"] == route.get("status", 200)
            assert (
                sample["bytes"] == len(route["body"]) and sample["sha256"] == hashlib.sha256(route["body"]).hexdigest()
            )
        for sample in value["samples"][4:]:
            assert sample["reason"] == "request_failed" and sample["status"] == 0 and sample["bytes"] == 0
        posted = next(row for row in fixture.calls if row["path"] == "/created")
        assert posted["body"] == b'{"text":"hello"}' and posted["method"] == "POST"
        assert {k.lower(): v for k, v in posted["headers"].items()}["x-test"] == "secret"
        assert "secret" not in (work / "report.json").read_text()
        mixed = value["overall"]["counts"]
        rejected = invalid_inputs(app, directory, fixture)
    return {
        "worker_peaks": peaks,
        "cancel_active": cancelled,
        "cancel_before_and_while_waiting": 9,
        "deadline": {"attempted": 3, "cancelled": 6},
        "late": 4,
        "stable_schedule": [0, 80, 160, 160, 260],
        "mixed": mixed,
        "report_oracles": ["counts", "statuses", "bytes", "sha256", "buckets", "nearest_rank", "CSV", "target_groups"],
        "invalid_inputs": rejected,
    }


def invalid_inputs(app: Application, directory: Path, fixture: Fixture) -> int:
    fixture.configure({"/ok": {}})
    base = policy(fixture)
    invalid = [
        dict(base, **{key: value})
        for key, value in [
            ("concurrency", 0),
            ("concurrency", 33),
            ("concurrency", True),
            ("duration_ms", 0),
            ("timeout_ms", 0),
            ("max_body", 0),
            ("max_lag_ms", -1),
            ("buckets_ms", []),
            ("buckets_ms", [2, 1]),
            ("buckets_ms", [1, 1]),
            ("buckets_ms", [True]),
            ("unknown", 1),
            ("targets", []),
            ("targets", base["targets"] * 2),
            ("schedule", []),
        ]
    ]
    for key, value in [
        ("method", "HEAD"),
        ("id", "bad,id"),
        ("body_hex", "zz"),
        ("body_hex", "00" * 4097),
        ("url", "file:///tmp/no"),
        ("headers", {"Host": "bad"}),
        ("headers", {"X-Test": "a\r\nb"}),
        ("headers", {"X-Test": "one", "x-test": "two"}),
        ("unknown", 1),
    ]:
        config = copy.deepcopy(base)
        config["targets"][0][key] = value
        invalid.append(config)
    for key, value in [
        ("count", 0),
        ("count", 1001),
        ("target", "missing"),
        ("at_ms", 4000),
        ("at_ms", -1),
        ("interval_ms", 1000),
        ("count", True),
        ("unknown", 1),
    ]:
        config = copy.deepcopy(base)
        config["schedule"][0][key] = value
        invalid.append(config)
    config = copy.deepcopy(base)
    config["schedule"] *= 100
    config["schedule"].append(config["schedule"][0])
    invalid.append(config)
    config = copy.deepcopy(base)
    config["schedule"] = [dict(base["schedule"][0], count=600)] * 2
    invalid.append(config)
    for index, config in enumerate(invalid):
        work, env = setup(directory, "invalid-" + str(index), config)
        output = Path(env["LOAD_REPORT"])
        output.write_text("old report")
        completed = app.run(work, env)
        assert completed.returncode != 0 and output.read_text() == "old report", (index, completed.stderr)
        assert not Path(str(output) + ".csv").exists() and not fixture.calls
    for mode in ["config", "cancel", "csv", "hardlink", "symlink"]:
        work, env = setup(directory, "alias-" + mode, base)
        source = Path(env["LOAD_CONFIG"])
        output = Path(env["LOAD_REPORT"])
        before = source.read_bytes()
        if mode == "config":
            env["LOAD_REPORT"] = str(source)
        elif mode == "cancel":
            env["LOAD_CANCEL"] = str(output)
        elif mode == "csv":
            source.rename(Path(str(output) + ".csv"))
            source = Path(str(output) + ".csv")
            env["LOAD_CONFIG"] = str(source)
        elif mode == "hardlink":
            output.hardlink_to(source)
        else:
            output.symlink_to(source)
        completed = app.run(work, env)
        assert completed.returncode != 0 and source.read_bytes() == before and not fixture.calls
    return len(invalid) + 5
