"""Independent CAS, immutable-history and exact rollback assertions."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import Application


def check(app: Application, directory: Path) -> dict:
    schema_path = directory / "schema.json"
    source = Path(__file__).resolve().parents[2] / "examples/corpus/005_versioned_settings/schema.json"
    schema = json.loads(source.read_text())
    schema_path.write_text(json.dumps(schema))
    state = directory / "state.json"
    settings = {
        "SETTINGS_SCHEMA": str(schema_path),
        "SETTINGS_STATE": str(state),
        "SETTINGS_PORT": "0",
        "SETTINGS_NOW": "1000",
        "SETTINGS_HISTORY": "6",
    }
    defaults = {"enabled": True, "workers": 2, "greeting": "Hello, 世界", "theme": "system", "rooms": ["general"]}
    with app.server(directory, settings) as server:
        initial = server.request("GET", "/settings").json()
        assert initial == {"revision": 0, "values": defaults, "timestamp": 1000}
        assert server.request("GET", "/schema").json() == schema
        snapshot = state.read_bytes()
        invalid = [
            {"workers": True},
            {"workers": 1.5},
            {"workers": 0},
            {"workers": 17},
            {"enabled": 1},
            {"theme": "unknown"},
            {"rooms": ["same", "same"]},
            {"rooms": [False]},
            {"rooms": ["a"] * 9},
            {"greeting": "😀" * 81},
            {"workers": 8, "unknown": 1},
            [],
        ]
        for changes in invalid:
            response = server.request("PUT", "/settings", json.dumps({"revision": 0, "changes": changes}).encode())
            assert response.status == 400, (changes, response.body)
            assert state.read_bytes() == snapshot
        for body in [b"{", b"null", b"\xff", b'{"revision":true,"changes":{}}', b'{"revision":-1,"changes":{}}']:
            assert server.request("PUT", "/settings", body).status == 400
        assert server.request("PUT", "/settings", b"x" * 65537).status == 413
        assert state.read_bytes() == snapshot
        # Two independently connected writers see the same revision. Exactly
        # one succeeds; identical proposals make observations deterministic.
        body = b'{"revision":0,"changes":{"workers":8}}'
        with ThreadPoolExecutor(max_workers=2) as pool:
            attempts = [pool.submit(server.request, "PUT", "/settings", body) for _ in range(2)]
            statuses = sorted(future.result().status for future in attempts)
        assert statuses == [200, 409]
        first_values = {**defaults, "workers": 8}
        assert server.request("GET", "/settings").json() == {"revision": 1, "values": first_values, "timestamp": 1000}
        snapshot = state.read_bytes()
        no_change = server.request("PUT", "/settings", b'{"revision":1,"changes":{"workers":8}}')
        assert no_change.status == 200 and no_change.json()["revision"] == 1
        assert server.request("PUT", "/settings", b'{"revision":0,"changes":{}}').status == 409
        assert state.read_bytes() == snapshot
        changed = {"enabled": False, "rooms": ["general", "Заметки"], "greeting": "Привет, мир 😀", "theme": "dark"}
        result = server.request("PUT", "/settings", json.dumps({"revision": 1, "changes": changed}).encode())
        second_values = {**first_values, **changed}
        assert result.status == 200 and result.json() == {"revision": 2, "values": second_values, "timestamp": 1000}
        page = server.request("GET", "/history?limit=2").json()
        assert page["more"] is True and page["next"] == 1
        assert [entry["revision"] for entry in page["history"]] == [0, 1]
        assert page["history"][0]["values"] == defaults
        assert page["history"][1]["values"] == first_values
        assert page["history"][1]["changed"] == ["workers"]
        page = server.request("GET", "/history?after=1&limit=2").json()
        assert page["more"] is False and page["next"] == 2 and len(page["history"]) == 1
        assert page["history"][0]["changed"] == ["enabled", "greeting", "rooms", "theme"]
        for query in ["after=-2", "after=true", "limit=0", "limit=1001"]:
            assert server.request("GET", "/history?" + query).status == 400
        snapshot = state.read_bytes()
        assert server.request("POST", "/rollback", b'{"revision":1,"target":0}').status == 409
        assert server.request("POST", "/rollback", b'{"revision":2,"target":99}').status == 404
        assert server.request("POST", "/rollback", b'{"revision":2,"target":true}').status == 400
        assert state.read_bytes() == snapshot
        result = server.request("POST", "/rollback", b'{"revision":2,"target":0}')
        assert result.status == 200 and result.json() == {"revision": 3, "values": defaults, "timestamp": 1000}
        result = server.request("PUT", "/settings", b'{"revision":3,"changes":{"rooms":["recreated"]}}')
        fourth_values = {**defaults, "rooms": ["recreated"]}
        assert result.status == 200 and result.json()["values"] == fourth_values
        result = server.request("POST", "/rollback", b'{"revision":4,"target":2}')
        assert result.status == 200 and result.json() == {"revision": 5, "values": second_values, "timestamp": 1000}
        snapshot = state.read_bytes()
        assert server.request("PUT", "/settings", b'{"revision":5,"changes":{"workers":9}}').status == 507
        assert server.request("POST", "/rollback", b'{"revision":5,"target":0}').status == 507
        assert server.request("PUT", "/settings", b'{"revision":5,"changes":{}}').status == 200
        assert state.read_bytes() == snapshot
        history = server.request("GET", "/history").json()["history"]
        assert [entry["values"] for entry in history] == [
            defaults,
            first_values,
            second_values,
            defaults,
            fourth_values,
            second_values,
        ]
        assert [entry["kind"] for entry in history] == ["initial", "update", "update", "rollback", "update", "rollback"]
        assert [entry["source"] for entry in history] == [0, 0, 1, 0, 3, 2]
        assert server.request("POST", "/settings").status == 405
        assert server.request("GET", "/missing").status == 404
    with app.server(directory, dict(settings, SETTINGS_NOW="900")) as server:
        assert server.request("GET", "/history").json()["history"] == history
        assert server.request("GET", "/settings").json()["revision"] == 5
    # The history is not trusted simply because the final values validate.
    original = json.loads(snapshot)
    for index, field, value in [
        (1, "revision", 9),
        (1, "changed", []),
        (3, "source", 1),
        (1, "timestamp", -1),
        (0, "values", first_values),
    ]:
        corrupt = copy.deepcopy(original)
        corrupt["history"][index][field] = value
        state.write_text(json.dumps(corrupt))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    state.write_bytes(snapshot)
    changed_schema = copy.deepcopy(schema)
    changed_schema["fields"][1]["max"] = 32
    schema_path.write_text(json.dumps(changed_schema))
    assert app.run(directory, settings).returncode != 0
    assert state.read_bytes() == snapshot
    invalid_schemas = []
    for index, field, value in [
        (0, "default", 1),
        (1, "min", 100),
        (2, "pattern", "(?=a)"),
        (3, "choices", ["system", "system"]),
        (4, "max_items", -1),
        (1, "name", "enabled"),
    ]:
        malformed = copy.deepcopy(schema)
        malformed["fields"][index][field] = value
        invalid_schemas.append(malformed)
    fresh = directory / "must-not-create.json"
    for malformed in invalid_schemas:
        schema_path.write_text(json.dumps(malformed))
        assert app.run(directory, dict(settings, SETTINGS_STATE=str(fresh))).returncode != 0
        assert not fresh.exists()
    schema_path.write_text(json.dumps(schema))
    return {
        "history": history,
        "competing_writers": statuses,
        "invalid_changes": len(invalid),
        "invalid_schemas": len(invalid_schemas),
        "rollback_exact": True,
        "history_preserved": True,
    }
