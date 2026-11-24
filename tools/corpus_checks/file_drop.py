"""Exercise binary fidelity, rejection, recovery, restart and expiration over real HTTP."""

import json
from pathlib import Path
from urllib.parse import quote, urlencode

from .common import Application


def check(app: Application, directory: Path) -> dict:
    data = directory / "data"
    settings = {"DROP_DATA": str(data), "DROP_PORT": "0", "DROP_MAX_BYTES": "1024", "DROP_NOW": "1000"}
    payload = bytes(range(256)) + b"\x00\xff\xfe\r\n" + "世界".encode()
    name = "résumé 世界.bin"
    with app.server(directory, settings) as server:
        assert server.request("GET", "/health").json() == {"service": "file-drop", "version": 1}
        response = server.request("POST", "/files?" + urlencode({"name": name, "ttl": 10}), payload)
        assert response.status == 201, response.body
        record = response.json()
        identifier = record["id"]
        assert record == {"id": identifier, "name": name, "size": len(payload), "created": 1000, "expires": 1010}
        assert len(identifier) == 64 and all(char in "0123456789abcdef" for char in identifier)
        downloaded = server.request("GET", "/files/" + identifier)
        assert downloaded.status == 200 and downloaded.body == payload
        assert downloaded.headers["content-disposition"] == "attachment; filename*=UTF-8''" + quote(name, safe="")
        assert server.request("GET", "/metadata/" + identifier).json() == record
        assert server.request("GET", "/files?prefix=" + quote("rés")).json()["count"] == 1
        assert server.request("GET", "/files?prefix=absent").json()["count"] == 0
        assert server.request("GET", "/files/" + "f" * 64).status == 404
        assert server.request("GET", "/files/../index.json").status == 404
        assert server.request("PUT", "/files").status == 405
        before = (data / "index.json").read_bytes()
        for bad_name in ["", "../escape", "slash/name", "back\\name", "\x00", "\r\nX-Test: evil", ".", "..", "a" * 201]:
            assert server.request("POST", "/files?" + urlencode({"name": bad_name}), b"x").status == 400
        for ttl in ["0", "-1", "86401", "1.5", "true", "oops", "null"]:
            assert server.request("POST", "/files?" + urlencode({"name": "x", "ttl": ttl}), b"x").status == 400
        assert server.request("POST", "/files?name=large", b"a" * 1025).status == 413
        assert (data / "index.json").read_bytes() == before
        zero = server.request("POST", "/files?name=empty", b"")
        assert zero.status == 201 and zero.json()["size"] == 0
        empty_id = zero.json()["id"]
        assert server.request("GET", "/files/" + empty_id).body == b""
        assert server.request("DELETE", "/files/" + empty_id).status == 200
        assert server.request("DELETE", "/files/" + empty_id).status == 404
        # A failed request is recoverable and does not stop the server.
        (data / "index.json").write_text("broken")
        assert server.request("GET", "/files").status == 500
        (data / "index.json").write_bytes(before)
        assert server.request("GET", "/files").json()["count"] == 1
    orphan = data / "blobs" / ("a" * 64)
    orphan.write_bytes(b"uncommitted upload")
    with app.server(directory, settings) as server:
        assert not orphan.exists()
        assert server.request("GET", "/files/" + identifier).body == payload
        listing = server.request("GET", "/files").json()
        assert listing == {"files": [record], "count": 1, "bytes": len(payload)}
    with app.server(directory, dict(settings, DROP_NOW="1010")) as server:
        assert server.request("GET", "/files/" + identifier).status == 410
        assert server.request("GET", "/metadata/" + identifier).status == 410
        assert server.request("GET", "/files").json() == {"files": [], "count": 0, "bytes": 0}
        assert server.request("POST", "/sweep").json() == {"removed": [identifier], "count": 1, "bytes": len(payload)}
        assert server.request("GET", "/files/" + identifier).status == 404
        assert server.request("POST", "/sweep").json()["count"] == 0
    assert not (data / "blobs" / identifier).exists()
    (data / "index.json").write_text(json.dumps({"version": 1, "files": [{"id": "../../outside"}]}))
    failed = app.run(directory, settings)
    assert failed.returncode != 0 and "corrupt index identifier" in failed.stderr
    return {
        "binary_bytes": len(payload),
        "persisted_restart": True,
        "expiration_status": 410,
        "after_sweep_status": 404,
        "invalid_inputs_do_not_mutate": True,
        "orphan_recovery": True,
        "recoverable_request_errors": True,
        "unsafe_index_rejected": True,
    }
