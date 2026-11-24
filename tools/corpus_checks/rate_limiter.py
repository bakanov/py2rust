"""Weighted quota decisions checked at boundaries and against a discrete-time oracle."""

import copy
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from .common import Application, Response, Server


def admit(server: Server, key: str, identifier: str, cost: int) -> Response:
    return server.request("POST", "/admit", json.dumps({"key": key, "id": identifier, "cost": cost}).encode())


def inspect(server: Server, key: str) -> dict:
    response = server.request("GET", "/quota?" + urlencode({"key": key}))
    assert response.status == 200, response.body
    return response.json()


def check(app: Application, directory: Path) -> dict:
    state = directory / "rate.json"
    settings = {
        "RATE_STATE": str(state),
        "RATE_PORT": "0",
        "RATE_NOW": "1000",
        "RATE_QUOTA": "5",
        "RATE_WINDOW": "2.5",
        "RATE_KEYS": "2",
    }
    with app.server(directory, settings) as server:
        result = admit(server, "alice", "one", 2)
        assert result.status == 200 and result.json()["remaining"] == 3
        assert result.headers["x-ratelimit-limit"] == "5" and result.headers["x-ratelimit-remaining"] == "3"
        assert "retry-after" not in result.headers
        snapshot = state.read_bytes()
        duplicate = admit(server, "alice", "one", 2)
        assert duplicate.json()["duplicate"] is True and duplicate.json()["used"] == 2
        assert admit(server, "alice", "one", 3).status == 409
        invalid = [
            {"key": "", "id": "new", "cost": 1},
            {"key": "bad\nkey", "id": "new", "cost": 1},
            {"key": "alice", "id": "bad/id", "cost": 1},
        ]
        invalid += [{"key": "alice", "id": "new", "cost": value} for value in [0, -1, 6, True, 1.5, "1"]]
        for value in invalid:
            assert server.request("POST", "/admit", json.dumps(value).encode()).status == 400
        assert server.request("POST", "/admit", b"x" * 4097).status == 413
        assert state.read_bytes() == snapshot
        assert admit(server, "Боб", "one", 5).status == 200
        assert inspect(server, "observer")["remaining"] == 5
        assert server.request("GET", "/quotas").json()["count"] == 2
        assert admit(server, "third", "one", 1).status == 507
    with app.server(directory, dict(settings, RATE_NOW="1000.5")) as server:
        assert admit(server, "alice", "two", 2).json()["remaining"] == 1
        denied = admit(server, "alice", "three", 3)
        assert denied.status == 429 and denied.json()["retry_at"] == 1002.5
        assert denied.headers["retry-after"] == "2" and denied.json()["used"] == 4
        all_units = admit(server, "alice", "all", 5)
        assert all_units.status == 429 and all_units.json()["retry_at"] == 1003
        assert all_units.headers["retry-after"] == "3"
        assert inspect(server, "Боб")["used"] == 5
    with app.server(directory, dict(settings, RATE_NOW="1002.499999")) as server:
        denied = admit(server, "alice", "at-boundary", 2)
        assert denied.status == 429 and denied.headers["retry-after"] == "1"
        assert admit(server, "Боб", "new", 1).status == 429
    with app.server(directory, dict(settings, RATE_NOW="1002.5")) as server:
        assert inspect(server, "alice")["used"] == 2
        assert inspect(server, "Боб")["used"] == 0
        result = admit(server, "alice", "three", 3)
        assert result.status == 200 and result.json()["remaining"] == 0 and result.json()["duplicate"] is False
        assert admit(server, "third", "full", 5).status == 200
    with app.server(directory, dict(settings, RATE_NOW="1003")) as server:
        assert inspect(server, "alice")["remaining"] == 2
        denied = admit(server, "alice", "wait", 3)
        assert denied.status == 429 and denied.headers["retry-after"] == "2" and denied.json()["retry_at"] == 1005
        recycled = admit(server, "alice", "one", 2)
        assert recycled.status == 200 and recycled.json()["duplicate"] is False
        snapshot = state.read_bytes()
    with app.server(directory, dict(settings, RATE_NOW="900")) as server:
        now = inspect(server, "alice")
        assert now["now"] == 1003 and now["used"] == 5 and now["remaining"] == 0
        assert admit(server, "alice", "backward", 1).status == 429
        assert state.read_bytes() == snapshot
    with app.server(directory, dict(settings, RATE_NOW="1005")) as server:
        swept = server.request("POST", "/sweep").json()
        assert swept == {"removed_keys": 1, "removed_events": 2}
        assert inspect(server, "alice")["used"] == 2
        assert admit(server, "alice", "after", 3).status == 200
        assert admit(server, "alice", "one", 2).json()["duplicate"] is True
        assert admit(server, "alice", "one", 3).status == 409
    with app.server(directory, dict(settings, RATE_NOW="1005.5")) as server:
        assert inspect(server, "alice")["used"] == 3
    with app.server(directory, dict(settings, RATE_NOW="1007.5")) as server:
        assert server.request("POST", "/sweep").json() == {"removed_keys": 1, "removed_events": 1}
        assert server.request("POST", "/sweep").json() == {"removed_keys": 0, "removed_events": 0}
        assert server.request("GET", "/quotas").json() == {"keys": [], "count": 0}
    final_bytes = state.read_bytes()
    original = json.loads(snapshot)
    for field, value in [("at", 0), ("cost", 6), ("id", "bad/id")]:
        corrupted = copy.deepcopy(original)
        corrupted["keys"]["alice"][0][field] = value
        state.write_text(json.dumps(corrupted))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    state.write_bytes(final_bytes)
    assert app.run(directory, dict(settings, RATE_QUOTA="6")).returncode != 0
    assert state.read_bytes() == final_bytes
    with app.server(directory, dict(settings, RATE_STATE=str(directory / "race.json"), RATE_QUOTA="1")) as server:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [pool.submit(admit, server, "race", identifier, 1) for identifier in ["x", "y"]]
            statuses = sorted(future.result().status for future in outcomes)
        assert statuses == [200, 429] and inspect(server, "race")["used"] == 1
    capacity_state = directory / "capacity.json"
    accepted_capacity = 0
    with app.server(
        directory, dict(settings, RATE_STATE=str(capacity_state), RATE_QUOTA="100", RATE_MAX_STATE="1024")
    ) as server:
        for index in range(20):
            before = capacity_state.read_bytes()
            result = admit(server, "capacity", str(index) + "x" * 70, 1)
            if result.status == 507:
                assert capacity_state.read_bytes() == before
                break
            assert result.status == 200
            accepted_capacity += 1
        assert 0 < accepted_capacity < 20 and len(capacity_state.read_bytes()) <= 1024
        assert inspect(server, "capacity")["used"] == accepted_capacity
    # Reference decisions use an integer quarter-second timeline, retaining all
    # accepted requests and measuring occupied units at each candidate instant.
    rng = random.Random(909)
    accepted: dict[str, list[tuple[int, int]]] = {"alice": [], "Боб": []}
    trace = []
    oracle_state = directory / "oracle.json"
    for tick in range(12):
        with app.server(
            directory,
            dict(settings, RATE_STATE=str(oracle_state), RATE_QUOTA="4", RATE_WINDOW="1.25", RATE_NOW=str(tick / 4)),
        ) as server:
            for offset in range(3):
                key = rng.choice(list(accepted))
                cost = rng.randrange(1, 5)
                used = sum(units for at, units in accepted[key] if tick - at < 5)
                allowed = used + cost <= 4
                result = admit(server, key, f"trial-{tick}-{offset}", cost)
                assert result.status == (200 if allowed else 429)
                if allowed:
                    accepted[key].append((tick, cost))
                    used += cost
                else:
                    future = next(
                        candidate
                        for candidate in range(tick + 1, tick + 6)
                        if cost + sum(units for at, units in accepted[key] if candidate - at < 5) <= 4
                    )
                    assert result.json()["retry_at"] == future / 4
                    assert result.headers["retry-after"] == str((future - tick + 3) // 4)
                assert result.json()["used"] == used and result.json()["remaining"] == 4 - used
                trace.append([tick, key, cost, allowed, used])
    return {
        "invalid_inputs": len(invalid),
        "boundary": 1002.5,
        "window_open_at_left": True,
        "clock_watermark": 1003,
        "competing_statuses": statuses,
        "capacity_admissions": accepted_capacity,
        "oracle_trace": trace,
        "sweep": swept,
    }
