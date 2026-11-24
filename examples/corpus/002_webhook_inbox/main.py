"""Accept, query and export a bounded local webhook history."""

import logging

from model import clock, normalize, setting, validate_configuration
from storage import find, initialize, load, save, statistics

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_array,
    json_dumps,
    json_equal,
    json_int,
    json_kind,
    json_loads,
    json_parse,
    json_string,
    log,
    log_configure,
    pretty,
    web_response,
    web_serve,
)


def reply(status: int, payload: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(payload).encode(), headers)


def submit(request: WebRequest) -> WebResponse:
    if len(request.body) > setting("INBOX_MAX_BODY", 65536):
        return reply(413, {"error": "event body exceeds limit"})
    event: Json = None
    try:
        event = normalize(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        return reply(400, {"error": "invalid event envelope"})
    identifier: str = json_string(event["id"])
    if request.headers.get("idempotency-key", identifier) != identifier:
        return reply(400, {"error": "idempotency key differs from event ID"})
    state: Json = load()
    events: list[Json] = json_array(state["events"])
    previous: Json = find(events, identifier)
    if json_kind(previous) != "null":
        if not json_equal(previous["event"], event):
            return reply(409, {"error": "event ID already contains different content"})
        return reply(200, {"receipt": previous["receipt"], "duplicate": True})
    if len(events) >= setting("INBOX_LIMIT", 1000):
        return reply(507, {"error": "inbox is full"})
    receipt: int = json_int(state["next_receipt"])
    events.append({"event": event, "receipt": receipt, "received_at": clock()})
    updated: Json = {"format": 1, "next_receipt": receipt + 1, "events": events}
    if len(pretty(updated).encode()) > setting("INBOX_MAX_STATE", 8388608):
        return reply(507, {"error": "snapshot would exceed limit"})
    save(updated)
    log(logging.INFO, "accepted event " + identifier)
    return reply(201, {"receipt": receipt, "duplicate": False})


def history(request: WebRequest) -> WebResponse:
    cursor: int = 0
    limit: int = 100
    try:
        cursor = json_int(json_parse(request.query.get("after", "0"), None))
        limit = json_int(json_parse(request.query.get("limit", "100"), None))
        assert cursor >= 0 and limit > 0 and limit <= 1000, "invalid history range"
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        return reply(400, {"error": "after and limit must be bounded integers"})
    source: str = request.query.get("source", "")
    kind: str = request.query.get("type", "")
    chosen: list[Json] = []
    more: bool = False
    next_cursor: int = cursor
    for item in json_array(load()["events"]):
        event: Json = item["event"]
        if (
            json_int(item["receipt"]) > cursor
            and (source == "" or source == json_string(event["source"]))
            and (kind == "" or kind == json_string(event["type"]))
        ):
            if len(chosen) == limit:
                more = True
                break
            chosen.append(item)
            next_cursor = json_int(item["receipt"])
    return reply(200, {"events": chosen, "next": next_cursor, "more": more})


def export(request: WebRequest) -> WebResponse:
    ids: list[str] = []
    try:
        selection: Json = json_loads(request.body.decode())
        for value in json_array(selection["ids"]):
            identifier: str = json_string(value)
            assert identifier not in ids, "duplicate export ID"
            ids.append(identifier)
        assert len(ids) <= 1000, "export too large"
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        return reply(400, {"error": "expected unique event IDs"})
    events: list[Json] = json_array(load()["events"])
    lines: list[str] = []
    for identifier in ids:
        item: Json = find(events, identifier)
        if json_kind(item) == "null":
            return reply(404, {"error": "unknown event ID", "id": identifier})
        lines.append(json_dumps(item))
    content: str = ""
    if len(lines) > 0:
        content = "\n".join(lines) + "\n"
    headers: dict[str, str] = {"Content-Type": "application/x-ndjson; charset=utf-8"}
    return web_response(200, content.encode(), headers)


def dispatch(request: WebRequest) -> WebResponse:
    if request.path == "/events":
        if request.method == "POST":
            return submit(request)
        if request.method == "GET":
            return history(request)
        return reply(405, {"error": "use GET or POST"})
    if request.path == "/export" and request.method == "POST":
        return export(request)
    if request.path == "/stats" and request.method == "GET":
        return reply(200, statistics(load()))
    if request.path.startswith("/receipts/") and request.method == "GET":
        item: Json = find(json_array(load()["events"]), request.path[10:])
        if json_kind(item) == "null":
            return reply(404, {"error": "unknown event ID"})
        return reply(200, item)
    return reply(404, {"error": "unknown route"})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        log(logging.ERROR, "webhook storage operation failed")
        return reply(500, {"error": "storage operation failed"})


def main() -> None:
    validate_configuration()
    log_configure(logging.INFO)
    initialize()
    web_serve("127.0.0.1", setting("INBOX_PORT", 8768), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
