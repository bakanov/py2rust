"""Create searchable named links, redirect visitors and transfer complete snapshots."""

from model import clock, configure, normalize, setting, valid_name, validate_record
from storage import find, initialize, load, ordered, replace, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_array,
    json_dumps,
    json_equal,
    json_float,
    json_int,
    json_kind,
    json_loads,
    json_string,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(value).encode(), headers)


def write_bookmark(request: WebRequest, name: str) -> WebResponse:
    value: Json = None
    try:
        value = normalize(json_loads(request.body.decode()))
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid bookmark"})
    if name != "" and name != json_string(value["name"]):
        return reply(400, {"error": "path name differs from bookmark name"})
    records: list[Json] = load()
    previous: Json = find(records, json_string(value["name"]))
    status: int = 201
    value["created"] = clock()
    value["updated"] = value["created"]
    value["visits"] = 0
    if name == "":
        if json_kind(previous) != "null":
            return reply(409, {"error": "bookmark already exists"})
        if len(records) >= setting("BOOKMARK_LIMIT", 1000):
            return reply(507, {"error": "bookmark collection is full"})
    else:
        if json_kind(previous) == "null":
            return reply(404, {"error": "unknown bookmark"})
        value["created"] = previous["created"]
        value["updated"] = max(clock(), json_float(previous["updated"]))
        value["visits"] = previous["visits"]
        status = 200
    save(replace(records, value))
    return reply(status, value)


def redirect(name: str) -> WebResponse:
    records: list[Json] = load()
    record: Json = find(records, name)
    if json_kind(record) == "null":
        return reply(404, {"error": "unknown bookmark"})
    count: int = json_int(record["visits"])
    if count >= 1000000000000:
        return reply(409, {"error": "visit counter is full"})
    record["visits"] = count + 1
    save(replace(records, record))
    headers: dict[str, str] = {"Location": json_string(record["url"])}
    return web_response(302, b"", headers)


def listing(request: WebRequest) -> WebResponse:
    query: str = request.query.get("q", "").lower()
    tag: str = request.query.get("tag", "").lower()
    result: list[Json] = []
    total_visits: int = 0
    for record in ordered(load()):
        haystack: str = (
            json_string(record["name"]) + " " + json_string(record["title"]) + " " + json_string(record["url"])
        )
        if query in haystack.lower() and (tag == "" or tag in json_array(record["tags"])):
            result.append(record)
            total_visits = total_visits + json_int(record["visits"])
    return reply(200, {"bookmarks": result, "count": len(result), "visits": total_visits})


def import_bookmarks(request: WebRequest) -> WebResponse:
    incoming: list[Json] = []
    try:
        document: Json = json_loads(request.body.decode())
        assert json_int(document["version"]) == 1, "unsupported import version"
        seen: set[str] = set()
        for raw in json_array(document["bookmarks"]):
            record: Json = validate_record(raw)
            name: str = json_string(record["name"])
            assert name not in seen, "duplicate imported name"
            seen.add(name)
            incoming.append(record)
        assert len(incoming) <= setting("BOOKMARK_LIMIT", 1000), "import too large"
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(400, {"error": "invalid bookmark snapshot"})
    proposed: list[Json] = load()
    added: int = 0
    for record in incoming:
        previous: Json = find(proposed, json_string(record["name"]))
        if json_kind(previous) == "null":
            proposed.append(record)
            added = added + 1
        elif not json_equal(previous, record):
            return reply(409, {"error": "conflicting imported bookmark", "name": record["name"]})
    if len(proposed) > setting("BOOKMARK_LIMIT", 1000):
        return reply(507, {"error": "bookmark collection is full"})
    if added > 0:
        save(proposed)
    return reply(200, {"added": added, "count": len(proposed)})


def dispatch(request: WebRequest) -> WebResponse:
    if len(request.body) > 8388608:
        return reply(413, {"error": "request exceeds size limit"})
    if request.path == "/bookmarks":
        if request.method == "POST":
            return write_bookmark(request, "")
        if request.method == "GET":
            return listing(request)
        return reply(405, {"error": "use GET or POST"})
    if request.path == "/export" and request.method == "GET":
        return reply(200, {"version": 1, "bookmarks": ordered(load())})
    if request.path == "/import" and request.method == "POST":
        return import_bookmarks(request)
    if request.path.startswith("/r/") and request.method == "GET":
        return redirect(request.path[3:])
    if request.path.startswith("/bookmarks/"):
        name: str = request.path[11:]
        if not valid_name(name):
            return reply(404, {"error": "unknown bookmark"})
        if request.method == "PUT":
            return write_bookmark(request, name)
        record: Json = find(load(), name)
        if json_kind(record) == "null":
            return reply(404, {"error": "unknown bookmark"})
        if request.method == "GET":
            return reply(200, record)
        if request.method == "DELETE":
            kept: list[Json] = []
            for item in load():
                if json_string(item["name"]) != name:
                    kept.append(item)
            save(kept)
            return reply(200, {"deleted": name})
        return reply(405, {"error": "use GET, PUT or DELETE"})
    return reply(404, {"error": "unknown route"})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception:  # noqa: BLE001 - the compiled profile uses recoverable Exception
        return reply(500, {"error": "bookmark storage operation failed"})


def main() -> None:
    configure()
    initialize()
    web_serve("127.0.0.1", setting("BOOKMARK_PORT", 8769), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
