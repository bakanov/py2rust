"""UTC normalization, half-open intervals, cancellation and independent slot oracle."""

import copy
import datetime as dt
import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

from .common import Application, Response, Server


def post(server: Server, path: str, value: object) -> Response:
    return server.request("POST", path, json.dumps(value).encode())


def booking(identifier: str, start: str, end: str, resource: str = "room-a") -> dict:
    return {
        "id": identifier,
        "resource": resource,
        "start": start,
        "end": end,
        "owner": "Мира",
        "title": "Planning 世界",
    }


def check(app: Application, directory: Path) -> dict:
    state = directory / "reservations.json"
    settings = {
        "RESERVE_STATE": str(state),
        "RESERVE_PORT": "0",
        "RESERVE_NOW": "1000",
        "RESERVE_RESOURCES": "3",
        "RESERVE_BOOKINGS": "6",
    }
    first = booking("a", "2026-10-06T15:00:00+05:00", "2026-10-06T16:00:00+05:00")
    second = booking("b", "2026-10-06T11:00:00Z", "2026-10-06T12:00:00Z")
    with app.server(directory, settings) as server:
        for identifier, name in [("room-a", "Комната А"), ("room-b", "Room B"), ("empty", "Unused")]:
            assert post(server, "/resources", {"id": identifier, "name": name}).status == 201
        assert post(server, "/resources", {"id": "overflow", "name": "Full"}).status == 507
        assert server.request("DELETE", "/resources/empty").status == 200
        assert server.request("DELETE", "/resources/empty").status == 404
        snapshot = state.read_bytes()
        assert post(server, "/resources", {"id": "room-a", "name": "Комната А"}).status == 200
        assert post(server, "/resources", {"id": "room-a", "name": "Conflict"}).status == 409
        assert post(server, "/resources", {"id": "../escape", "name": "Bad"}).status == 400
        assert state.read_bytes() == snapshot
        created = post(server, "/bookings", first)
        assert created.status == 201, created.body
        record = created.json()
        assert record == {
            **first,
            "start": "2026-10-06T10:00:00.000000+00:00",
            "end": "2026-10-06T11:00:00.000000+00:00",
            "status": "active",
            "created_at": 1000,
            "cancelled_at": 0,
        }
        assert post(server, "/bookings", second).status == 201
        snapshot = state.read_bytes()
        equivalent = {**first, "start": "2026-10-06T10:00:00Z", "end": "2026-10-06T11:00:00Z"}
        assert post(server, "/bookings", equivalent).json() == record
        assert post(server, "/bookings", {**equivalent, "title": "Conflicting identity"}).status == 409
        assert (
            post(
                server, "/bookings", booking("overlap", "2026-10-06T10:59:59.999999Z", "2026-10-06T11:00:00.000001Z")
            ).status
            == 409
        )
        invalid = [
            {**first, "start": "2026-10-06T15:00:00"},
            {**first, "end": first["start"]},
            {**first, "end": "2026-10-06T09:00:00Z"},
            {**first, "start": "2026-02-30T00:00:00Z"},
            {**first, "owner": ""},
            {**first, "title": "bad\nlabel"},
            {**first, "id": "bad/id"},
            {**first, "start": False},
            {**first, "extra": 1},
        ]
        for value in invalid:
            assert post(server, "/bookings", value).status == 400
        assert post(server, "/bookings", {**first, "id": "missing", "resource": "absent"}).status == 404
        assert state.read_bytes() == snapshot
        other = booking("other", "2026-10-06T10:30:00Z", "2026-10-06T11:30:00Z", "room-b")
        assert post(server, "/bookings", other).status == 201
        assert server.request("DELETE", "/resources/room-a").status == 409
        cancelled = server.request("DELETE", "/bookings/a")
        assert cancelled.status == 200 and cancelled.json()["status"] == "cancelled"
        assert cancelled.json()["cancelled_at"] == 1000
        snapshot = state.read_bytes()
        assert server.request("DELETE", "/bookings/a").json() == cancelled.json()
        assert post(server, "/bookings", first).json()["status"] == "cancelled"
        assert state.read_bytes() == snapshot
        assert post(server, "/bookings", {**equivalent, "id": "c"}).status == 201
        tiny = booking("tiny", "2026-10-06T12:00:00Z", "2026-10-06T12:00:00.000001Z")
        assert post(server, "/bookings", tiny).status == 201
        query = urlencode({"resource": "room-a", "from": "2026-10-06T11:00:00Z", "to": "2026-10-06T12:00:00Z"})
        agenda = server.request("GET", "/agenda?" + query).json()
        assert agenda["count"] == 1 and agenda["bookings"][0]["id"] == "b"
        assert server.request("GET", "/agenda?resource=absent").status == 404
        assert server.request("GET", "/agenda?include_cancelled=1").status == 400
        assert (
            server.request("GET", "/agenda?" + urlencode({"from": first["start"], "to": first["start"]})).status == 400
        )
        assert server.request("GET", "/agenda?" + urlencode({"owner": "absent"})).json()["count"] == 0
        all_entries = server.request("GET", "/agenda?include_cancelled=true").json()["bookings"]
        assert [item["id"] for item in all_entries] == ["a", "c", "other", "b", "tiny"]
        assert post(server, "/bookings", booking("last", "2026-10-06T13:00:00Z", "2026-10-06T14:00:00Z")).status == 201
        snapshot = state.read_bytes()
        assert post(server, "/bookings", booking("full", "2026-10-06T14:00:00Z", "2026-10-06T15:00:00Z")).status == 507
        assert state.read_bytes() == snapshot
        assert server.request("DELETE", "/bookings/missing").status == 404
    with app.server(directory, settings) as server:
        assert server.request("GET", "/bookings/a").json()["status"] == "cancelled"
        assert server.request("GET", "/agenda").json()["count"] == 5
        assert server.request("GET", "/bookings/c").json()["start"] == record["start"]
    original = json.loads(snapshot)
    corruptions = []
    for field, value in [("resource", "absent"), ("status", "invented"), ("cancelled_at", -1)]:
        corrupted = copy.deepcopy(original)
        corrupted["bookings"][0][field] = value
        corruptions.append(corrupted)
    overlapping = copy.deepcopy(original)
    for value in overlapping["bookings"]:
        if value["id"] == "c":
            value["end"] = "2026-10-06T11:30:00.000000+00:00"
    corruptions.append(overlapping)
    for corrupted in corruptions:
        state.write_text(json.dumps(corrupted))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    state.write_bytes(snapshot)
    with app.server(directory, dict(settings, RESERVE_STATE=str(directory / "race.json"))) as server:
        assert post(server, "/resources", {"id": "room-a", "name": "Race"}).status == 201
        with ThreadPoolExecutor(max_workers=2) as pool:
            requests = [
                pool.submit(post, server, "/bookings", {**first, "id": identifier}) for identifier in ["x", "y"]
            ]
            statuses = sorted(result.result().status for result in requests)
        assert statuses == [201, 409]
        assert server.request("GET", "/agenda").json()["count"] == 1
    # Use discrete occupied slots as an independent model of random intervals.
    rng = random.Random(805)
    occupied = {"room-a": set(), "room-b": set()}
    accepted = 0
    base = dt.datetime(2026, 10, 6, tzinfo=dt.UTC)
    with app.server(
        directory, dict(settings, RESERVE_STATE=str(directory / "slots.json"), RESERVE_BOOKINGS="100")
    ) as server:
        for identifier in occupied:
            assert post(server, "/resources", {"id": identifier, "name": identifier}).status == 201
        for index in range(60):
            resource = rng.choice(list(occupied))
            start = rng.randrange(30)
            end = start + rng.randrange(1, 6)
            slots = set(range(start, end))
            free = not occupied[resource].intersection(slots)
            value = booking(
                "trial-" + str(index),
                (base + dt.timedelta(minutes=start)).isoformat(),
                (base + dt.timedelta(minutes=end)).isoformat(),
                resource,
            )
            response = post(server, "/bookings", value)
            assert response.status == (201 if free else 409), (value, response.body)
            if free:
                occupied[resource].update(slots)
                accepted += 1
        assert server.request("GET", "/agenda").json()["count"] == accepted
    return {
        "initial_agenda": all_entries,
        "competing_writers": statuses,
        "invalid_inputs": len(invalid),
        "random_trials": 60,
        "random_accepted": accepted,
        "cancelled_retained": True,
        "restart": True,
    }
