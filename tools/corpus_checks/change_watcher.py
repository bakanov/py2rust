"""Mutable JSON service plus independent masking, change application and persistence oracles."""

import contextlib
import copy
import datetime as dt
import http.server
import json
import random
import threading
from collections.abc import Iterator
from pathlib import Path

from .common import Application


@contextlib.contextmanager
def snapshots() -> Iterator[tuple[str, dict, list]]:
    control = {"value": None}
    calls = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            calls.append(self.path)
            route = control
            if control.get("sequence"):
                route = control["sequence"].pop(0)
            if route.get("disconnect"):
                self.close_connection = True
                return
            body = route.get("raw", json.dumps(route.get("value"), ensure_ascii=False).encode())
            self.send_response(route.get("status", 200))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in route.get("headers", {}).items():
                self.send_header(name, value)
            self.end_headers()
            with contextlib.suppress(OSError):
                self.wfile.write(body)
            return

        def log_message(self, *args: object) -> None:
            return

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/snapshot", control, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return


def masked(value: object, ignored: list[str]) -> object:
    result = copy.deepcopy(value)
    for pointer in ignored:
        if pointer == "":
            return None
        tokens = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
        parent = result
        try:
            for token in tokens[:-1]:
                if isinstance(parent, list):
                    assert token == str(int(token)) and int(token) >= 0
                    parent = parent[int(token)]
                else:
                    parent = parent[token]
            token = tokens[-1]
            if isinstance(parent, list):
                assert token == str(int(token)) and int(token) >= 0
                parent[int(token)] = None
            elif isinstance(parent, dict):
                parent.pop(token, None)
        except (AssertionError, KeyError, IndexError, TypeError, ValueError):
            continue
    return result


def apply_changes(before: object, changes: list[dict]) -> object:
    result = copy.deepcopy(before)
    # Removals use the old snapshot's indices; apply them from highest to lowest.
    ordered = [change for change in changes if change["op"] != "remove"]
    ordered += sorted(
        (change for change in changes if change["op"] == "remove"),
        key=lambda item: int(item["path"].rsplit("/", 1)[-1]) if item["path"].rsplit("/", 1)[-1].isdigit() else -1,
        reverse=True,
    )
    for change in ordered:
        pointer = change["path"]
        if pointer == "":
            assert change["op"] == "replace"
            result = copy.deepcopy(change["after"])
            continue
        tokens = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
        parent = result
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        key = int(tokens[-1]) if isinstance(parent, list) else tokens[-1]
        if change["op"] == "remove":
            assert parent[key] == change["before"]
            del parent[key]
        elif change["op"] == "add" and isinstance(parent, list):
            assert key == len(parent)
            parent.append(copy.deepcopy(change["after"]))
        else:
            if change["op"] == "replace":
                assert parent[key] == change["before"]
            parent[key] = copy.deepcopy(change["after"])
    return result


def check(application: Application, directory: Path) -> dict:
    config = directory / "watch.json"
    state_path = directory / "state.json"
    report_path = Path(str(state_path) + ".report.json")
    text_path = Path(str(state_path) + ".report.txt")
    settings = {"WATCH_CONFIG": str(config), "WATCH_STATE": str(state_path)}
    observations = {}
    tick = 0
    with snapshots() as (url, control, calls):
        ignored = ["/profile/last_seen", "/metrics/changed_at", "/items/0/noise"]
        policy = {"url": url, "ignore": ignored, "retain": 3, "interval_ms": 1, "max_changes": 100}
        config.write_text(json.dumps(policy))

        def run(code: int = 0, **extra: str) -> dict:
            nonlocal tick
            tick += 1
            now = (dt.datetime(2024, 3, 1, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=tick)).isoformat()
            result = application.run(directory, {**settings, "WATCH_NOW": now, **extra})
            assert result.returncode == code, result.stderr + result.stdout
            report = json.loads(report_path.read_text())
            assert json.loads(result.stdout) == {
                "checks": report["checks"],
                "ready": report["ready"],
                "events": report["next_id"] - 1,
                "retained": len(report["history"]),
                "error": report["error"],
            }
            assert "SECRET" not in report_path.read_text() + text_path.read_text()
            return report

        before = {
            "profile": {
                "name": "Alice",
                "active": True,
                "last_seen": "SECRET-1",
                "roles": ["reader"],
                "optional": None,
            },
            "metrics": {"hits": 1, "changed_at": "SECRET-2"},
            "a/b": {"~x": "one"},
            "items": [{"id": 1, "noise": "SECRET-3"}, {"id": 2}],
            "remove_me": {"x": 1},
            "": {"value": "empty key"},
        }
        control["value"] = before
        initial = run(WATCH_MODE="inspect")
        assert initial["checks"] == 0 and not initial["ready"] and not state_path.exists() and not calls
        first = run()
        assert first["checks"] == 1 and first["ready"] and first["history"] == []
        assert first["snapshot"] == masked(before, ignored) and len(calls) == 1
        noise = copy.deepcopy(before)
        noise["profile"].pop("last_seen")
        noise["metrics"]["changed_at"] = "SECRET-updated"
        noise["metrics"]["hits"] = 1.0
        noise["items"][0]["noise"] = {"nested": "SECRET-nested"}
        control["value"] = noise
        unchanged = run()
        assert unchanged["next_id"] == 1 and unchanged["history"] == []
        after = copy.deepcopy(noise)
        after["profile"].update(name="Bob", active=1, roles=["reader", "writer"])
        after["profile"].pop("optional")
        after["metrics"]["hits"] = 2
        after["a/b"]["~x"] = "two"
        after["items"][1]["id"] = 3
        after[""]["value"] = "new"
        after.pop("remove_me")
        after["new"] = None
        control["value"] = after
        changed = run()
        event = changed["history"][0]
        assert event["id"] == 1 and event["at"] == changed["last_at"]
        expected_paths = [
            "//value",
            "/a~1b/~0x",
            "/items/1/id",
            "/metrics/hits",
            "/new",
            "/profile/active",
            "/profile/name",
            "/profile/optional",
            "/profile/roles/1",
            "/remove_me",
        ]
        assert [entry["path"] for entry in event["changes"]] == expected_paths
        assert [entry["op"] for entry in event["changes"]] == ["replace"] * 4 + [
            "add",
            "replace",
            "replace",
            "remove",
            "add",
            "remove",
        ]
        assert apply_changes(first["snapshot"], event["changes"]) == masked(after, ignored)
        assert event["changes"][4] == {"op": "add", "path": "/new", "before": None, "after": None}
        assert event["changes"][5]["before"] is True and type(event["changes"][5]["after"]) is int
        assert 'replace "/a~1b/~0x"' in text_path.read_text() and 'remove "/profile/optional"' in text_path.read_text()
        observations["first_change"] = event
        repeated = run()
        assert repeated["next_id"] == 2 and repeated["history"] == changed["history"]
        saved = state_path.read_bytes()
        before_calls = len(calls)
        assert run(WATCH_MODE="inspect") == repeated
        assert state_path.read_bytes() == saved and len(calls) == before_calls

        errors = []
        deep = None
        for _ in range(26):
            deep = [deep]
        for route, kind, status in [
            ({"status": 503}, "http", 503),
            ({"status": 302, "headers": {"Location": "/unexpected"}}, "http", 302),
            ({"disconnect": True}, "transport", 0),
            ({"raw": b"x" * 65537}, "transport", 0),
            ({"raw": b"\xff"}, "json", 200),
            ({"raw": b"{broken"}, "json", 200),
            ({"raw": b"NaN"}, "json", 200),
            ({"value": deep}, "json", 200),
            ({"value": list(range(2001))}, "json", 200),
            ({"value": {}, "headers": {"Content-Encoding": "gzip"}}, "json", 200),
        ]:
            control.clear()
            control.update(route)
            rejected = run(code=1)
            assert rejected["error"] == {"kind": kind, "status": status}
            assert rejected["snapshot"] == masked(after, ignored) and rejected["history"] == changed["history"]
            errors.append(rejected["error"])
        assert set(calls) == {"/snapshot"}
        control.clear()
        control["value"] = after
        assert run()["error"] is None
        observations["failures"] = errors

        # Reconstruct every accepted transition with a patch applier independent of the differ.
        generator = random.Random(17)
        current = masked(after, ignored)
        sequence = [
            None,
            True,
            1,
            9007199254740993,
            9007199254740992.0,
            [1, 2, 3, 4],
            [1, 8],
            {"": None, "a/b": [True, 1]},
        ]
        sequence += [
            {
                "revision": index,
                "list": [generator.randint(-10, 10) for _ in range(generator.randrange(5))],
                "object": {
                    name: generator.choice([None, True, 1, "世界"])
                    for name in generator.sample(["a", "b", "x/y", "~"], generator.randrange(5))
                },
            }
            for index in range(12)
        ]
        for value in sequence:
            control["value"] = value
            report = run()
            event = report["history"][-1]
            assert apply_changes(current, event["changes"]) == value
            assert report["snapshot"] == value
            current = copy.deepcopy(value)
        assert [event["id"] for event in report["history"]] == list(range(report["next_id"] - 3, report["next_id"]))
        observations["replayed_transitions"] = len(sequence)
        observations["retained_ids"] = [event["id"] for event in report["history"]]

        # Bounded multiple polls continue through a failure and keep each visible change once.
        control["sequence"] = [
            {"value": {"sequence": 1}},
            {"disconnect": True},
            {"value": {"sequence": 2}},
            {"value": {"sequence": 2}},
        ]
        old_id = report["next_id"]
        report = run(code=1, WATCH_ROUNDS="4")
        assert report["error"] is None and report["next_id"] == old_id + 2 and not control["sequence"]
        observations["bounded_polling"] = {"new_events": 2, "continued_after_failure": True}

        good = state_path.read_bytes()
        reports = (report_path.read_bytes(), text_path.read_bytes())
        before_calls = len(calls)
        for changed_policy in [
            {**policy, "retain": 2},
            {**policy, "ignore": ["/bad~2"]},
            {**policy, "ignore": ["/x", "/x"]},
            {**policy, "max_changes": True},
            {**policy, "interval_ms": 0},
            {**policy, "url": "http://user@localhost/"},
            {**policy, "extra": 1},
        ]:
            config.write_text(json.dumps(changed_policy))
            assert application.run(directory, settings).returncode != 0
            assert state_path.read_bytes() == good and len(calls) == before_calls
            assert (report_path.read_bytes(), text_path.read_bytes()) == reports
        config.write_text(json.dumps(policy))
        for change in [
            {"checks": -1},
            {"next_id": 100},
            {"last_at": "invalid"},
            {"ready": False},
            {"history": []},
            {"snapshot": {"profile": {"last_seen": "SECRET-corrupt"}}},
            {"error": {"kind": "transport", "status": 200}},
        ]:
            state_path.write_text(json.dumps({**json.loads(good), **change}))
            damaged = state_path.read_bytes()
            assert application.run(directory, settings).returncode != 0
            assert state_path.read_bytes() == damaged and len(calls) == before_calls
        state_path.write_bytes(good)
        assert application.run(directory, dict(settings, WATCH_NOW="2020-01-01T00:00:00Z")).returncode != 0
        assert state_path.read_bytes() == good and len(calls) == before_calls
        observations["invalid_state_policy_and_clock"] = True

        crash_events = {}
        for boundary in ["before_checkpoint", "after_checkpoint"]:
            root = directory / boundary
            root.mkdir()
            target = root / "state.json"
            fixed = dict(settings, WATCH_STATE=str(target), WATCH_NOW="2024-01-01T00:00:00Z")
            control.clear()
            control["value"] = {"value": 1}
            assert application.run(root, fixed).returncode == 0
            control["value"] = {"value": 2}
            assert application.run(root, dict(fixed, WATCH_STOP=boundary)).returncode == 75
            interrupted = json.loads(target.read_text())
            assert interrupted["next_id"] == (1 if boundary == "before_checkpoint" else 2)
            assert application.run(root, fixed).returncode == 0
            final = json.loads(target.read_text())
            assert final["next_id"] == 2 and len(final["history"]) == 1 and final["snapshot"] == {"value": 2}
            crash_events[boundary] = final["history"][0]["changes"]
        observations["interruptions"] = crash_events

        for name, patch, before, after in [
            ("ignored-root", {"ignore": [""]}, {"secret": 1}, ["secret"]),
            ("ignored-array-slot", {"ignore": ["/1"]}, [1], [1, "secret"]),
            ("ignored-empty-key", {"ignore": ["/"]}, {"": 1, "a": 2}, {"": 99, "a": 2}),
            ("budget", {"max_changes": 1}, {"a": 1, "b": 1}, {"a": 2, "b": 2}),
        ]:
            root = directory / name
            root.mkdir()
            target = root / "state.json"
            local_config = root / "config.json"
            local_config.write_text(json.dumps({**policy, **patch}))
            fixed = dict(
                settings, WATCH_CONFIG=str(local_config), WATCH_STATE=str(target), WATCH_NOW="2024-01-01T00:00:00Z"
            )
            control["value"] = before
            assert application.run(root, fixed).returncode == 0
            control["value"] = after
            result = application.run(root, fixed)
            assert result.returncode == (1 if name == "budget" else 0), result.stderr
            observed = json.loads(target.read_text())
            assert observed["next_id"] == 1 and observed["history"] == []
            if name == "budget":
                assert observed["error"] == {"kind": "change_budget", "status": 200} and observed["snapshot"] == before
            else:
                assert observed["snapshot"] == masked(after, patch["ignore"])
            assert application.run(root, dict(fixed, WATCH_MODE="inspect")).returncode == 0
        observations["ignored_slots_root_and_budget"] = True

        for suffix in ["", ".report.json", ".report.txt"]:
            protected = directory / ("alias" + suffix)
            protected.hardlink_to(config)
            target = str(protected) if not suffix else str(protected)[: -len(suffix)]
            saved_config = config.read_bytes()
            before_calls = len(calls)
            assert application.run(directory, dict(settings, WATCH_STATE=target)).returncode != 0
            assert config.read_bytes() == saved_config and len(calls) == before_calls
            protected.unlink()
        observations["protected_paths"] = True
    return observations
