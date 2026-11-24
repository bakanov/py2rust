"""Independent assertions for immutable receipts, validation and restart."""

import copy
import json
from pathlib import Path

from .common import Application


def envelope(identifier: str, source: str = "checkout", kind: str = "order.created") -> dict:
    return {
        "id": identifier,
        "source": source,
        "type": kind,
        "occurred_at": "2026-10-06T12:34:56+05:00",
        "data": {"note": "Заказ 😀", "amount": 123},
    }


def check(app: Application, directory: Path) -> dict:
    state = directory / "inbox.json"
    settings = {"INBOX_STATE": str(state), "INBOX_PORT": "0", "INBOX_NOW": "1000", "INBOX_LIMIT": "3"}
    with app.server(directory, settings) as server:
        assert server.request("GET", "/stats").json() == {"count": 0, "next_receipt": 1, "sources": {}, "types": {}}
        first = envelope("a")
        response = server.request("POST", "/events", json.dumps(first).encode(), {"Idempotency-Key": "a"})
        assert response.status == 201 and response.json() == {"receipt": 1, "duplicate": False}
        snapshot = state.read_bytes()
        first["occurred_at"] = "2026-10-06T07:34:56Z"
        assert server.request("POST", "/events", json.dumps(first).encode()).json() == {"receipt": 1, "duplicate": True}
        assert state.read_bytes() == snapshot
        invalid = []
        for field, value in [
            ("id", "a/b"),
            ("id", True),
            ("data", []),
            ("type", ""),
            ("occurred_at", "2026-10-06T12:34:56"),
            ("source", "not a source"),
        ]:
            item = copy.deepcopy(first)
            item[field] = value
            invalid.append(item)
        invalid.extend([{}, {**first, "extra": 0}])
        for item in invalid:
            assert server.request("POST", "/events", json.dumps(item).encode()).status == 400
            assert state.read_bytes() == snapshot
        for raw in [b"\xff", b"{", b"null"]:
            assert server.request("POST", "/events", raw).status == 400
        assert server.request("POST", "/events", b"x" * 65537).status == 413
        assert (
            server.request("POST", "/events", json.dumps(first).encode(), {"Idempotency-Key": "different"}).status
            == 400
        )
        changed = copy.deepcopy(first)
        changed["data"]["amount"] = 999
        assert server.request("POST", "/events", json.dumps(changed).encode()).status == 409
        assert state.read_bytes() == snapshot
        for identifier, source, kind in [("b", "billing", "invoice.paid"), ("c", "checkout", "order.created")]:
            assert (
                server.request("POST", "/events", json.dumps(envelope(identifier, source, kind)).encode()).status == 201
            )
        snapshot = state.read_bytes()
        assert server.request("POST", "/events", json.dumps(envelope("d")).encode()).status == 507
        assert state.read_bytes() == snapshot
        page = server.request("GET", "/events?limit=1").json()
        assert page["next"] == 1 and page["more"] is True and len(page["events"]) == 1
        assert page["events"][0]["event"]["occurred_at"] == "2026-10-06T07:34:56.000000+00:00"
        page = server.request("GET", "/events?after=1&source=checkout&type=order.created").json()
        assert page["next"] == 3 and page["more"] is False
        assert [item["event"]["id"] for item in page["events"]] == ["c"]
        for query in ["after=-1", "after=true", "limit=0", "limit=1001", "limit=oops"]:
            assert server.request("GET", "/events?" + query).status == 400
        assert server.request("PUT", "/events").status == 405
        assert server.request("GET", "/receipts/missing").status == 404
        exported = server.request("POST", "/export", b'{"ids":["c","a"]}')
        assert exported.status == 200 and exported.headers["content-type"].startswith("application/x-ndjson")
        records = [json.loads(line) for line in exported.body.splitlines()]
        assert [item["receipt"] for item in records] == [3, 1]
        assert records[1] == server.request("GET", "/receipts/a").json()
        assert records[1]["received_at"] == 1000
        assert server.request("POST", "/export", b'{"ids":["a","a"]}').status == 400
        assert server.request("POST", "/export", b'{"ids":["missing"]}').status == 404
        assert server.request("POST", "/export", b'{"ids":[]}').body == b""
        stats = server.request("GET", "/stats").json()
        assert stats == {
            "count": 3,
            "next_receipt": 4,
            "sources": {"checkout": 2, "billing": 1},
            "types": {"order.created": 2, "invoice.paid": 1},
        }
    with app.server(directory, settings) as server:
        assert server.request("GET", "/stats").json() == stats
        duplicate = server.request("POST", "/events", json.dumps(first).encode())
        assert duplicate.status == 200 and duplicate.json()["duplicate"] is True
        assert state.read_bytes() == snapshot
    corrupted = json.loads(snapshot)
    corrupted["next_receipt"] = 42
    state.write_text(json.dumps(corrupted))
    broken = state.read_bytes()
    assert app.run(directory, settings).returncode != 0
    assert state.read_bytes() == broken
    state.write_bytes(snapshot)
    # Reject a snapshot-size overflow before replacing the last durable state.
    tight = dict(settings, INBOX_LIMIT="4", INBOX_MAX_STATE=str(len(snapshot) + 20))
    with app.server(directory, tight) as server:
        assert server.request("POST", "/events", json.dumps(envelope("d")).encode()).status == 507
        assert state.read_bytes() == snapshot
    return {"stats": stats, "export": records, "invalid_envelopes": len(invalid) + 3, "restart": True}
