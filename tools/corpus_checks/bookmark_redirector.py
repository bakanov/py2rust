"""Independent redirect, transactional import and persistence assertions."""

import copy
import json
from pathlib import Path
from urllib.parse import urlencode

from .common import Application


def check(app: Application, directory: Path) -> dict:
    state = directory / "bookmarks.json"
    settings = {"BOOKMARK_STATE": str(state), "BOOKMARK_PORT": "0", "BOOKMARK_NOW": "1000", "BOOKMARK_LIMIT": "3"}
    first = {
        "name": "docs",
        "url": "https://example.org:8443/a%20b?q=x%2By&n=2#part",
        "title": "  Документы 世界  ",
        "tags": ["Work", "rust", "work"],
    }
    with app.server(directory, settings) as server:
        assert server.request("GET", "/bookmarks").json() == {"bookmarks": [], "count": 0, "visits": 0}
        response = server.request("POST", "/bookmarks", json.dumps(first).encode())
        assert response.status == 201, response.body
        record = response.json()
        assert record == {
            **first,
            "title": "Документы 世界",
            "tags": ["rust", "work"],
            "created": 1000,
            "updated": 1000,
            "visits": 0,
        }
        snapshot = state.read_bytes()
        assert server.request("POST", "/bookmarks", json.dumps(first).encode()).status == 409
        bad_urls = [
            "javascript:alert(1)",
            "file:///etc/passwd",
            "//example.org",
            "https://",
            "http://user@host/",
            "http://host:0",
            "http://host:65536",
            "http://host:abc",
            "http://host:1.5",
            "http://256.1.2.3/",
            "http://127.1/",
            "http://01.2.3.4/",
            "http://-bad/",
            "http://bad..name/",
            "http://good/\r\nLocation:evil",
            "http://good/has space",
            "http://good/é",
            "http://good/%",
            "http://good/%A",
            "http://good/%XZ",
            "http://good\\evil/",
            "http://good/" + "a" * 4096,
        ]
        for url in bad_urls:
            assert (
                server.request("POST", "/bookmarks", json.dumps({**first, "name": "bad", "url": url}).encode()).status
                == 400
            ), url
            assert state.read_bytes() == snapshot
        for field, value in [
            ("name", "../escape"),
            ("title", ""),
            ("title", "bad\x00title"),
            ("tags", [True]),
            ("tags", ["tag"] * 2 + ["bad tag"]),
            ("url", False),
        ]:
            assert server.request("POST", "/bookmarks", json.dumps({**first, field: value}).encode()).status == 400
        assert state.read_bytes() == snapshot
        for count in range(1, 4):
            redirected = server.request("GET", "/r/docs")
            assert redirected.status == 302 and redirected.headers["location"] == first["url"]
            assert redirected.body == b""
            assert server.request("GET", "/bookmarks/docs").json()["visits"] == count
        assert server.request("GET", "/r/missing").status == 404
        for query in [{"q": "документ", "tag": "WORK"}, {"q": "世界"}, {"tag": "rust"}]:
            listing = server.request("GET", "/bookmarks?" + urlencode(query)).json()
            assert listing["count"] == 1 and listing["visits"] == 3
        assert server.request("GET", "/bookmarks?q=absent").json()["count"] == 0
        assert (
            server.request("PUT", "/bookmarks/missing", json.dumps({**first, "name": "missing"}).encode()).status == 404
        )
        assert server.request("PUT", "/bookmarks/docs", json.dumps({**first, "name": "changed"}).encode()).status == 400
        update = {**first, "title": "Updated", "url": "http://127.0.0.1:8080/new?x=1#fragment"}
        updated = server.request("PUT", "/bookmarks/docs", json.dumps(update).encode())
        assert updated.status == 200 and updated.json()["visits"] == 3 and updated.json()["created"] == 1000
        assert server.request("GET", "/r/docs").headers["location"] == update["url"]
        second = {"name": "alpha", "url": "https://example.com/", "title": "Alpha", "tags": []}
        assert server.request("POST", "/bookmarks", json.dumps(second).encode()).status == 201
        exported = server.request("GET", "/export").json()
        assert [item["name"] for item in exported["bookmarks"]] == ["alpha", "docs"]
        assert [item["visits"] for item in exported["bookmarks"]] == [0, 4]
        snapshot = state.read_bytes()
        assert server.request("POST", "/import", json.dumps(exported).encode()).json() == {"added": 0, "count": 2}
        assert state.read_bytes() == snapshot
        conflict = copy.deepcopy(exported)
        conflict["bookmarks"][0]["name"] = "new"
        conflict["bookmarks"][1]["title"] = "Conflict"
        assert server.request("POST", "/import", json.dumps(conflict).encode()).status == 409
        assert state.read_bytes() == snapshot
        for broken in [
            {"version": 2, "bookmarks": []},
            {"version": 1, "bookmarks": [exported["bookmarks"][0]] * 2},
            {"version": 1, "bookmarks": [conflict["bookmarks"][0], {"name": "invalid"}]},
        ]:
            assert server.request("POST", "/import", json.dumps(broken).encode()).status == 400
            assert state.read_bytes() == snapshot
        third = {**second, "name": "third"}
        assert server.request("POST", "/bookmarks", json.dumps(third).encode()).status == 201
        assert server.request("POST", "/bookmarks", json.dumps({**second, "name": "fourth"}).encode()).status == 507
        assert server.request("DELETE", "/bookmarks/third").json() == {"deleted": "third"}
        assert server.request("DELETE", "/bookmarks/third").status == 404
        assert server.request("GET", "/export").json() == exported
    with app.server(directory, settings) as server:
        assert server.request("GET", "/export").json() == exported
        assert server.request("GET", "/r/docs").headers["location"] == update["url"]
        assert server.request("GET", "/bookmarks/docs").json()["visits"] == 5
    # Import into an independent empty store; compare the entire exported value.
    clone_state = directory / "clone.json"
    with app.server(directory, dict(settings, BOOKMARK_STATE=str(clone_state))) as server:
        result = server.request("POST", "/import", json.dumps(exported).encode())
        assert result.status == 200 and result.json() == {"added": 2, "count": 2}
        assert server.request("GET", "/export").json() == exported
    saved = state.read_bytes()
    for field, value in [("url", "javascript:evil"), ("visits", -1), ("created", 1001)]:
        corrupted = json.loads(saved)
        corrupted["bookmarks"][0][field] = value
        state.write_text(json.dumps(corrupted))
        before = state.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert state.read_bytes() == before
    state.write_bytes(saved)
    return {"export": exported, "visits_after_restart": 5, "invalid_urls": len(bad_urls), "transactional_import": True}
