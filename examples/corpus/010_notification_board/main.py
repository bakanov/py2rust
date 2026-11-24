"""Publish notifications and stream a resumable, bounded replay log over HTTP."""

from model import (
    configure,
    decimal,
    event_frame,
    gap_frame,
    publication,
    setting,
    valid_name,
)
from storage import append, bounds, cursor_valid, find_key, initialize, load

from py2rust.stdlib import (
    Json,
    StreamChunk,
    WebRequest,
    WebResponse,
    json_array,
    json_bool,
    json_dumps,
    json_equal,
    json_float,
    json_int,
    json_is_null,
    json_loads,
    json_string,
    monotonic,
    stream_chunk,
    web_response,
    web_serve_stream,
    web_stream,
)


def reply(status: int, value: Json) -> WebResponse:
    return web_response(status, json_dumps(value).encode(), {"Content-Type": "application/json"})


def publish(request: WebRequest) -> WebResponse:
    value: Json = None
    try:
        value = publication(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid publication"})
    state: Json = load()
    previous: Json = find_key(state, json_string(value["key"]))
    if not json_is_null(previous):
        original: Json = {"key": previous["key"], "topic": previous["topic"], "data": previous["data"]}
        if not json_equal(value, original):
            return reply(409, {"error": "publication key has different content"})
        return reply(200, previous)
    if json_int(state["last"]) == 999999999999999999:
        return reply(507, {"error": "event IDs exhausted"})
    return reply(201, append(state, value))


def requested_cursor(request: WebRequest, state: Json) -> int:
    default: str = str(json_int(bounds(state)["oldest"]) - 1)
    text: str = request.query.get("after", default)
    # A browser's reconnect header takes precedence over its original URL.
    header: str = request.headers.get("last-event-id", "")
    if header != "":
        text = header
    return decimal(text)


def subscribe(request: WebRequest) -> WebResponse:
    state: Json = load()
    after: int = 0
    try:
        after = requested_cursor(request, state)
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid replay cursor"})
    if not cursor_valid(state, after):
        return reply(409, {"error": "cursor outside retained history", "bounds": bounds(state)})
    return web_stream(
        {"Content-Type": "text/event-stream; charset=utf-8", "X-Accel-Buffering": "no"},
        {"after": after, "ready": False, "heartbeat": monotonic()},
        setting("BOARD_POLL", 50),
    )


def poll(cursor: Json) -> StreamChunk:
    if not json_bool(cursor["ready"]):
        cursor["ready"] = True
        return stream_chunk(b"retry: 1000\n: connected\n\n", cursor, False)
    state: Json = load()
    after: int = json_int(cursor["after"])
    if not cursor_valid(state, after):
        return stream_chunk(gap_frame(bounds(state)), cursor, True)
    for record in json_array(state["events"]):
        if json_int(record["id"]) > after:
            cursor["after"] = record["id"]
            cursor["heartbeat"] = monotonic()
            return stream_chunk(event_frame(record), cursor, False)
    now: float = monotonic()
    if now - json_float(cursor["heartbeat"]) >= 1.0:
        cursor["heartbeat"] = now
        return stream_chunk(b": keepalive\n\n", cursor, False)
    return stream_chunk(b"", cursor, False)


def history(request: WebRequest) -> WebResponse:
    state: Json = load()
    after: int = 0
    limit: int = 0
    topic: str = request.query.get("topic", "")
    try:
        after = decimal(request.query.get("after", str(json_int(bounds(state)["oldest"]) - 1)))
        limit = decimal(request.query.get("limit", "100"))
        assert limit >= 1 and limit <= 100, "invalid page limit"
        assert topic == "" or valid_name(topic), "invalid topic"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid history query"})
    if not cursor_valid(state, after):
        return reply(409, {"error": "cursor outside retained history", "bounds": bounds(state)})
    records: list[Json] = []
    next_cursor: int = after
    for record in json_array(state["events"]):
        if json_int(record["id"]) > after:
            next_cursor = json_int(record["id"])
            if topic == "" or topic == json_string(record["topic"]):
                records.append(record)
                if len(records) == limit:
                    break
    return reply(200, {"events": records, "next": next_cursor, "bounds": bounds(state)})


def handle(request: WebRequest) -> WebResponse:
    try:
        if len(request.body) > 16384:
            return reply(413, {"error": "request exceeds 16 KiB"})
        if request.path == "/events" and request.method == "POST":
            return publish(request)
        if request.path == "/events" and request.method == "GET":
            return history(request)
        if request.path == "/subscribe" and request.method == "GET":
            return subscribe(request)
        if request.path == "/status" and request.method == "GET":
            return reply(200, bounds(load()))
        return reply(404, {"error": "unknown route"})
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "notification storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve_stream("127.0.0.1", setting("BOARD_PORT", 8775), handle, poll)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
