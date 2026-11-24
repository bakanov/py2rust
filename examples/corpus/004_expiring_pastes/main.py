"""Serve public and capability-protected text pastes with strict expiration."""

from model import (
    can_read,
    clock,
    configure,
    matches,
    metadata,
    normalize,
    setting,
    valid_token,
)
from storage import document, find, initialize, load, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_dumps,
    json_float,
    json_int,
    json_kind,
    json_loads,
    json_parse,
    json_string,
    random_token,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(value).encode(), headers)


def key_from(request: WebRequest) -> str:
    header: str = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    return ""


def create(request: WebRequest) -> WebResponse:
    if len(request.body) > setting("PASTE_MAX_BYTES", 65536) * 12 + 4096:
        return reply(413, {"error": "request body exceeds byte limit"})
    value: Json = None
    try:
        value = normalize(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid paste or text exceeds limit"})
    records: list[Json] = load()
    if len(records) >= setting("PASTE_LIMIT", 1000):
        return reply(507, {"error": "paste storage is full; delete or sweep entries"})
    identifier: str = random_token()
    read_key: str = ""
    delete_key: str = random_token()
    if json_string(value["visibility"]) == "private":
        read_key = random_token()
    # Include every existing key when detecting the extremely unlikely random
    # collision, so a new capability cannot accidentally grant access elsewhere.
    used: set[str] = set()
    for entry in records:
        used.add(json_string(entry["id"]))
        used.add(json_string(entry["read_key"]))
        used.add(json_string(entry["delete_key"]))
    for key in [identifier, delete_key, read_key]:
        if key != "":
            assert key not in used, "random identifier collision; retry creation"
            used.add(key)
    created: float = clock()
    ttl: float = json_int(value["ttl"])
    record: Json = {
        "id": identifier,
        "title": value["title"],
        "text": value["text"],
        "visibility": value["visibility"],
        "size": len(json_string(value["text"]).encode()),
        "created": created,
        "expires": created + ttl,
        "read_key": read_key,
        "delete_key": delete_key,
    }
    records.append(record)
    if len(document(records).encode()) > setting("PASTE_MAX_STATE", 8388608):
        return reply(507, {"error": "paste snapshot would exceed byte limit"})
    save(records)
    result: Json = metadata(record)
    result["read_key"] = read_key
    result["delete_key"] = delete_key
    return reply(201, result)


def listing(request: WebRequest) -> WebResponse:
    offset: int = 0
    limit: int = 100
    try:
        offset = json_int(json_parse(request.query.get("offset", "0"), None))
        limit = json_int(json_parse(request.query.get("limit", "100"), None))
        assert offset >= 0 and limit >= 1 and limit <= 1000, "invalid page range"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "offset and limit must be bounded integers"})
    query: str = request.query.get("q", "").lower()
    selected: list[Json] = []
    count: int = 0
    now: float = clock()
    for record in load():
        text: str = json_string(record["title"]) + " " + json_string(record["text"])
        if (
            json_string(record["visibility"]) == "public"
            and json_float(record["expires"]) > now
            and query in text.lower()
        ):
            if count >= offset and len(selected) < limit:
                selected.append(metadata(record))
            count = count + 1
    return reply(200, {"pastes": selected, "count": count, "more": offset + len(selected) < count})


def access(request: WebRequest, identifier: str, is_metadata: bool) -> WebResponse:
    if not valid_token(identifier):
        return reply(404, {"error": "unknown paste"})
    records: list[Json] = load()
    record: Json = find(records, identifier)
    if json_kind(record) == "null" or not can_read(record, key_from(request)):
        return reply(404, {"error": "unknown paste"})
    if request.method == "DELETE" and not is_metadata:
        if not matches(key_from(request), json_string(record["delete_key"])):
            return reply(403, {"error": "delete capability required"})
        kept: list[Json] = []
        for entry in records:
            if json_string(entry["id"]) != identifier:
                kept.append(entry)
        save(kept)
        return reply(200, {"deleted": identifier})
    if request.method != "GET":
        return reply(405, {"error": "unsupported paste method"})
    if json_float(record["expires"]) <= clock():
        return reply(410, {"error": "paste expired"})
    if is_metadata:
        return reply(200, metadata(record))
    headers: dict[str, str] = {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Security-Policy": "default-src 'none'",
    }
    return web_response(200, json_string(record["text"]).encode(), headers)


def sweep() -> WebResponse:
    now: float = clock()
    kept: list[Json] = []
    removed: int = 0
    for record in load():
        if json_float(record["expires"]) <= now:
            removed = removed + 1
        else:
            kept.append(record)
    if removed > 0:
        save(kept)
    return reply(200, {"removed": removed})


def handle(request: WebRequest) -> WebResponse:
    try:
        if request.path == "/pastes":
            if request.method == "POST":
                return create(request)
            if request.method == "GET":
                return listing(request)
            return reply(405, {"error": "use GET or POST"})
        if request.path == "/sweep" and request.method == "POST":
            return sweep()
        if request.path.startswith("/pastes/"):
            return access(request, request.path[8:], False)
        if request.path.startswith("/metadata/"):
            return access(request, request.path[10:], True)
        return reply(404, {"error": "unknown route"})
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "paste storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve("127.0.0.1", setting("PASTE_PORT", 8770), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
