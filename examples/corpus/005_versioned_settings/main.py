"""Compare revisions before changing settings; keep rollback as a new revision."""

from schema import apply_changes, clock, differences, load_schema, setting
from storage import ChangeKind, initialize, load, save, serialize

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_dumps,
    json_float,
    json_int,
    json_keys,
    json_loads,
    json_parse,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(value).encode(), headers)


def current(entry: Json) -> Json:
    return {"revision": entry["revision"], "values": entry["values"], "timestamp": entry["timestamp"]}


def commit(fields: list[Json], history: list[Json], values: Json, kind: ChangeKind, source: int) -> WebResponse:
    previous: Json = history[-1]
    entry: Json = {
        "revision": len(history),
        "kind": kind.value,
        "source": source,
        "timestamp": max(clock(), json_float(previous["timestamp"])),
        "values": values,
        "changed": differences(previous["values"], values),
    }
    proposed: list[Json] = history.copy()
    proposed.append(entry)
    if len(proposed) > setting("SETTINGS_HISTORY", 100) or len(serialize(fields, proposed).encode()) > 8388608:
        return reply(507, {"error": "retained history is full"})
    save(fields, proposed)
    return reply(200, current(entry))


def update(request: WebRequest, fields: list[Json], history: list[Json]) -> WebResponse:
    revision: int = -1
    changes: Json = None
    try:
        value: Json = json_loads(request.body.decode())
        assert json_keys(value) == ["changes", "revision"], "invalid update fields"
        revision = json_int(value["revision"])
        changes = value["changes"]
        assert revision >= 0, "negative revision"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "expected revision and changes"})
    previous: Json = history[-1]
    if revision != json_int(previous["revision"]):
        return reply(409, {"error": "stale revision", "current_revision": previous["revision"]})
    values: Json = None
    try:
        values = apply_changes(fields, previous["values"], changes)
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid settings change"})
    if len(differences(previous["values"], values)) == 0:
        return reply(200, current(previous))
    return commit(fields, history, values, ChangeKind.UPDATE, revision)


def rollback(request: WebRequest, fields: list[Json], history: list[Json]) -> WebResponse:
    revision: int = -1
    target: int = -1
    try:
        value: Json = json_loads(request.body.decode())
        assert json_keys(value) == ["revision", "target"], "invalid rollback fields"
        revision = json_int(value["revision"])
        target = json_int(value["target"])
        assert revision >= 0 and target >= 0, "negative revision"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "expected revision and target"})
    if revision != json_int(history[-1]["revision"]):
        return reply(409, {"error": "stale revision", "current_revision": history[-1]["revision"]})
    if target >= len(history):
        return reply(404, {"error": "unknown rollback revision"})
    return commit(fields, history, history[target]["values"], ChangeKind.ROLLBACK, target)


def history_page(request: WebRequest, history: list[Json]) -> WebResponse:
    after: int = -1
    limit: int = 100
    try:
        after = json_int(json_parse(request.query.get("after", "-1"), None))
        limit = json_int(json_parse(request.query.get("limit", "100"), None))
        assert after >= -1 and limit >= 1 and limit <= 1000, "invalid history page"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "after and limit must be bounded integers"})
    entries: list[Json] = []
    for entry in history:
        if json_int(entry["revision"]) > after and len(entries) < limit:
            entries.append(entry)
    next_revision: int = after
    if len(entries) > 0:
        next_revision = json_int(entries[-1]["revision"])
    return reply(200, {"history": entries, "next": next_revision, "more": next_revision < len(history) - 1})


def handle(request: WebRequest) -> WebResponse:
    try:
        if len(request.body) > 65536:
            return reply(413, {"error": "request exceeds byte limit"})
        fields: list[Json] = load_schema()
        history: list[Json] = load(fields)
        if request.path == "/settings":
            if request.method == "GET":
                return reply(200, current(history[-1]))
            if request.method == "PUT":
                return update(request, fields, history)
            return reply(405, {"error": "use GET or PUT"})
        if request.path == "/rollback" and request.method == "POST":
            return rollback(request, fields, history)
        if request.path == "/history" and request.method == "GET":
            return history_page(request, history)
        if request.path == "/schema" and request.method == "GET":
            return reply(200, {"fields": fields})
        return reply(404, {"error": "unknown route"})
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "settings storage operation failed"})


def main() -> None:
    fields: list[Json] = load_schema()
    initialize(fields)
    web_serve("127.0.0.1", setting("SETTINGS_PORT", 8771), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
