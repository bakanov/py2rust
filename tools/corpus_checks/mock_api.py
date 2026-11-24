"""An explicit scenario oracle, including state persistence and invalid fixtures."""

import copy
import json
from pathlib import Path

from .common import Application

SAMPLE = Path(__file__).resolve().parents[2] / "examples/corpus/006_mock_api/routes.json"


def check(app: Application, directory: Path) -> dict:
    config = json.loads(SAMPLE.read_text())
    path = directory / "routes.json"
    path.write_text(json.dumps(config))
    settings = {"MOCK_CONFIG": str(path), "MOCK_STATE": str(directory / "state.json"), "MOCK_PORT": "0"}
    with app.server(directory, settings) as server:
        assert server.request("GET", "/_mock/state").json() == {"scenario": "signed-out", "sequence": 0}
        assert server.request("GET", "/profile").status == 409
        response = server.request("POST", "/login", b'{"user": "bob"}')
        assert response.status == 400 and response.json() == {"errors": ["user: value mismatch"]}
        assert server.request("POST", "/login", b"{broken").json() == {"errors": ["request must contain a JSON object"]}
        assert server.request("POST", "/login", b"\xff").status == 400
        assert server.request("GET", "/_mock/state").json() == {"scenario": "signed-out", "sequence": 4}
        logged_in = server.request("POST", "/login", b'{"user": "alice"}')
        assert logged_in.status == 201 and logged_in.json() == {"logged_in": True}
        profile = server.request("GET", "/profile")
        assert profile.json() == {"name": "Alice", "active": True}
        assert profile.headers["x-scenario"] == "authenticated"
        assert server.request("POST", "/login", b'{"user": "alice"}').status == 409
    with app.server(directory, settings) as server:
        assert server.request("GET", "/_mock/state").json() == {"scenario": "signed-in", "sequence": 7}
        assert server.request("GET", "/binary").body == b"\x00\xff\xfe\n"
        assert server.request("GET", "/welcome").body.decode() == "Hello, 世界"
        assert server.request("GET", "/missing").status == 404
        logout = server.request("POST", "/logout")
        assert logout.status == 204 and logout.body == b""
        transcript = server.request("GET", "/_mock/transcript").json()
        assert [event["sequence"] for event in transcript] == list(range(1, 12))
        assert [event["status"] for event in transcript] == [409, 400, 400, 400, 201, 200, 409, 200, 200, 404, 204]
        assert transcript[4]["before"] == "signed-out" and transcript[4]["after"] == "signed-in"
        assert transcript[10]["before"] == "signed-in" and transcript[10]["after"] == "signed-out"
        assert transcript[3]["body_hex"] == "ff"
        assert server.request("POST", "/_mock/reset").json() == {"reset": True, "scenario": "signed-out"}
        assert server.request("GET", "/_mock/transcript").json() == []
    invalid = []
    duplicate = copy.deepcopy(config)
    duplicate["routes"].append(duplicate["routes"][0])
    invalid.append((duplicate, "route IDs must be unique"))
    unknown_state = copy.deepcopy(config)
    unknown_state["routes"][0]["next"] = "missing"
    invalid.append((unknown_state, "unknown destination state"))
    invalid_hex = copy.deepcopy(config)
    invalid_hex["routes"][3]["body"] = "0 x"
    invalid.append((invalid_hex, ""))
    bad_header = copy.deepcopy(config)
    bad_header["routes"][1]["headers"][0]["value"] = "unsafe\r\nInjected: yes"
    invalid.append((bad_header, "invalid header value"))
    for document, diagnostic in invalid:
        path.write_text(json.dumps(document))
        result = app.run(directory, settings)
        assert result.returncode != 0
        assert diagnostic in result.stderr
    return {
        "statuses": [event["status"] for event in transcript],
        "transcript_length": 11,
        "restart_state": "signed-in",
        "binary_hex": "00fffe0a",
        "reset": True,
        "malformed_configurations_rejected": len(invalid),
    }
