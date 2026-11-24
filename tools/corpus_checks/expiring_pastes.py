"""Independent Unicode, capability separation and exact-expiration assertions."""

import copy
import json
import re
from pathlib import Path
from urllib.parse import urlencode

from .common import Application


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + key}


def check(app: Application, directory: Path) -> dict:
    state = directory / "pastes.json"
    settings = {
        "PASTE_STATE": str(state),
        "PASTE_PORT": "0",
        "PASTE_NOW": "1000",
        "PASTE_LIMIT": "3",
        "PASTE_MAX_BYTES": "1024",
    }
    text = "Привет, 世界 😀\r\n**bold** and _italic_\n<script>untrusted()</script>\n"
    public = {"title": "  Заметка  ", "text": text, "ttl": 10, "visibility": "public"}
    private = {"title": "Secret", "text": "private content " + "é" * 200, "ttl": 20, "visibility": "private"}
    with app.server(directory, settings) as server:
        pub = server.request("POST", "/pastes", json.dumps(public).encode())
        assert pub.status == 201, pub.body
        pub = pub.json()
        priv = server.request("POST", "/pastes", json.dumps(private).encode())
        assert priv.status == 201, priv.body
        priv = priv.json()
        tokens = [pub["id"], pub["delete_key"], priv["id"], priv["read_key"], priv["delete_key"]]
        assert len(set(tokens)) == 5 and all(re.fullmatch("[0-9a-f]{64}", value) for value in tokens)
        assert pub["read_key"] == "" and pub["created"] == 1000 and pub["expires"] == 1010
        assert priv["created"] == 1000 and priv["expires"] == 1020
        assert pub["title"] == "Заметка" and pub["size"] == len(text.encode())
        result = server.request("GET", "/pastes/" + pub["id"])
        assert result.status == 200 and result.body == text.encode()
        assert result.headers["content-type"] == "text/plain; charset=utf-8"
        assert result.headers["x-content-type-options"] == "nosniff"
        assert result.headers["content-security-policy"] == "default-src 'none'"
        metadata = {key: value for key, value in pub.items() if key not in {"read_key", "delete_key"}}
        assert server.request("GET", "/metadata/" + pub["id"]).json() == metadata
        listing = server.request("GET", "/pastes").json()
        assert listing == {"pastes": [metadata], "count": 1, "more": False}
        assert server.request("GET", "/pastes?" + urlencode({"q": "привет"})).json() == listing
        assert server.request("GET", "/pastes?q=secret").json()["count"] == 0
        for key in ["", "wrong", pub["delete_key"], priv["read_key"][:-1], priv["id"], "f" * 64]:
            for path in ["/pastes/", "/metadata/"]:
                denied = server.request("GET", path + priv["id"], headers=bearer(key))
                assert denied.status == 404
                assert denied.json() == {"error": "unknown paste"}
        for key in [priv["read_key"], priv["delete_key"]]:
            assert server.request("GET", "/pastes/" + priv["id"], headers=bearer(key)).body == private["text"].encode()
            private_meta = server.request("GET", "/metadata/" + priv["id"], headers=bearer(key)).json()
            assert "read_key" not in private_meta and "delete_key" not in private_meta and "text" not in private_meta
        snapshot = state.read_bytes()
        assert server.request("DELETE", "/pastes/" + pub["id"]).status == 403
        assert server.request("DELETE", "/pastes/" + priv["id"], headers=bearer(priv["read_key"])).status == 403
        assert server.request("DELETE", "/pastes/" + priv["id"]).status == 404
        malformed = [{**public, "ttl": value} for value in [0, -1, 86401, True, 1.5, "10"]]
        malformed += [
            {**public, field: value}
            for field, value in [
                ("text", "\x00"),
                ("text", "😀" * 257),
                ("title", ""),
                ("title", "bad\nname"),
                ("visibility", "hidden"),
            ]
        ]
        malformed += [{**public, "extra": 1}, {}, None]
        for value in malformed:
            assert server.request("POST", "/pastes", json.dumps(value).encode()).status == 400
        for value in [b"\xff", b"{"]:
            assert server.request("POST", "/pastes", value).status == 400
        assert server.request("POST", "/pastes", b"x" * 16385).status == 413
        for query in ["offset=-1", "offset=true", "limit=0", "limit=1001"]:
            assert server.request("GET", "/pastes?" + query).status == 400
        assert state.read_bytes() == snapshot
        temporary = server.request(
            "POST", "/pastes", json.dumps({**public, "title": "Empty", "text": "", "ttl": 30}).encode()
        ).json()
        assert temporary["size"] == 0
        assert server.request("GET", "/pastes/" + temporary["id"]).body == b""
        page = server.request("GET", "/pastes?limit=1").json()
        assert page["pastes"] == [metadata] and page["count"] == 2 and page["more"] is True
        assert server.request("GET", "/pastes?limit=1&offset=1").json()["pastes"][0]["id"] == temporary["id"]
        assert server.request("POST", "/pastes", json.dumps(public).encode()).status == 507
        assert (
            server.request("DELETE", "/pastes/" + temporary["id"], headers=bearer(temporary["delete_key"])).status
            == 200
        )
        assert server.request("GET", "/pastes/" + temporary["id"]).status == 404
    with app.server(directory, dict(settings, PASTE_NOW="1009.999")) as server:
        assert server.request("GET", "/pastes/" + pub["id"]).body == text.encode()
        assert (
            server.request("GET", "/pastes/" + priv["id"], headers=bearer(priv["read_key"])).body
            == private["text"].encode()
        )
    snapshot = state.read_bytes()
    tight = dict(settings, PASTE_MAX_STATE=str(len(snapshot) + 20))
    with app.server(directory, tight) as server:
        assert server.request("POST", "/pastes", json.dumps(public).encode()).status == 507
        assert state.read_bytes() == snapshot
    with app.server(directory, dict(settings, PASTE_NOW="1010")) as server:
        assert server.request("GET", "/pastes/" + pub["id"]).status == 410
        assert server.request("GET", "/metadata/" + pub["id"]).status == 410
        assert server.request("GET", "/pastes").json() == {"pastes": [], "count": 0, "more": False}
        assert server.request("POST", "/sweep").json() == {"removed": 1}
        assert server.request("GET", "/pastes/" + pub["id"]).status == 404
        assert server.request("GET", "/pastes/" + priv["id"], headers=bearer(priv["read_key"])).status == 200
    with app.server(directory, dict(settings, PASTE_NOW="1020")) as server:
        assert server.request("GET", "/pastes/" + priv["id"]).status == 404
        assert server.request("GET", "/pastes/" + priv["id"], headers=bearer(priv["read_key"])).status == 410
        assert server.request("POST", "/sweep").json() == {"removed": 1}
        assert server.request("POST", "/sweep").json() == {"removed": 0}
    assert json.loads(state.read_text()) == {"version": 1, "pastes": []}
    original = json.loads(snapshot)
    for field, value in [("size", 999), ("expires", 1000), ("id", "../bad"), ("delete_key", "short")]:
        corrupt = copy.deepcopy(original)
        corrupt["pastes"][0][field] = value
        state.write_text(json.dumps(corrupt))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    return {
        "unicode_bytes": len(text.encode()),
        "invalid_inputs": len(malformed) + 2,
        "capabilities_separate": True,
        "expired_public_status": 410,
        "expired_private_anonymous_status": 404,
        "expired_private_authorized_status": 410,
        "swept": 2,
        "restart": True,
    }
