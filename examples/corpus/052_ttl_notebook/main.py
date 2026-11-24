# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
"""A local HTTP notebook: each request is a durable, single-process transaction."""

from config import clock, configure, setting, state_path
from model import exact, execute, key, lifetime, value_check
from storage import document, initialize, load, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    file_lock,
    json_canonical,
    json_float,
    json_int,
    json_loads,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json", "Cache-Control": "no-store"}
    return web_response(status, json_canonical(value).encode(), headers)


def command(request: WebRequest) -> Json:
    result: Json = {"op": "list", "key": ""}
    if request.method == "PUT":
        assert len(request.query) == 0, "put accepts no query fields"
        value: Json = json_loads(request.body.decode())
        exact(value, ["key", "value", "ttl"])
        result = {"op": "put", "key": key(value["key"]), "value": value["value"], "ttl": lifetime(value["ttl"])}
        value_check(value["value"])
    else:
        assert len(request.body) == 0, "unexpected request body"
        if request.path == "/entry":
            assert len(request.query) == 1 and "key" in request.query, "expected only a key query"
            result["key"] = key(request.query["key"])
            result["op"] = "get" if request.method == "GET" else "delete"
        elif request.path == "/sweep":
            assert len(request.query) == 0, "sweep accepts no query fields"
            result["op"] = "sweep"
        else:
            for name in request.query:
                assert name in ["prefix", "offset", "limit"], "unknown listing field"
            prefix: str = request.query.get("prefix", "")
            assert len(prefix.encode()) <= 128, "prefix exceeds key limit"
            offset: int = json_int(json_loads(request.query.get("offset", "0")))
            limit: int = json_int(json_loads(request.query.get("limit", "100")))
            assert 0 <= offset <= 256 and 1 <= limit <= 256, "invalid listing bounds"
            result["prefix"] = prefix
            result["offset"] = offset
            result["limit"] = limit
    return result


def handle(request: WebRequest) -> WebResponse:
    if request.path not in ["/entry", "/entries", "/sweep"]:
        return reply(404, {"error": "unknown route"})
    methods: list[str] = ["GET", "PUT", "DELETE"]
    if request.path == "/entries":
        methods = ["GET"]
    elif request.path == "/sweep":
        methods = ["POST"]
    if request.method not in methods:
        return reply(405, {"error": "method not allowed"})
    if len(request.body) > setting("TTL_VALUE_BYTES", 16384) * 6 + 4096:
        return reply(413, {"error": "request exceeds byte limit"})
    instruction: Json = None
    try:
        instruction = command(request)
    except Exception:  # noqa: BLE001 - recoverable errors are explicit in this subset
        return reply(400, {"error": "invalid notebook request"})
    try:
        before: Json = load()
        original: str = document(before)
        now: float = max(clock(), json_float(before["clock"]))
        # Compare serialized snapshots: Python aliases must not affect change detection.
        updated: Json = {"version": 1, "clock": now, "entries": before["entries"]}
        transaction: tuple[Json, int, Json] = execute(updated, instruction)
        updated = transaction[0]
        status: int = transaction[1]
        result: Json = transaction[2]
        if status == 507:
            return reply(status, result)
        content: str = document(updated)
        if len(content.encode()) > setting("TTL_STATE_BYTES", 8388608):
            return reply(507, {"error": "snapshot would exceed byte limit"})
        if original != content:
            save(updated)
        return reply(status, result)
    except Exception:  # noqa: BLE001 - an uncommitted read must not claim expiration
        return reply(500, {"error": "notebook storage operation failed"})


def main() -> None:
    configure()
    with file_lock(state_path() + ".lock") as _guard:
        initialize()
        web_serve("127.0.0.1", setting("TTL_PORT", 8790), handle)
    return


if __name__ == "__main__":
    main()
