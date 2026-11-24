"""A complete bounded file-drop HTTP application, implemented in Python."""

from config import (
    default_lifetime,
    maximum_size,
    now,
    setting_integer,
    validate_configuration,
)
from storage import add, erase, initialize, lookup, read_blob, records, text, valid_id

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    json_dumps,
    json_float,
    json_int,
    json_kind,
    json_parse,
    random_token,
    url_quote,
    web_response,
    web_serve,
)


def reply(status: int, value: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json; charset=utf-8"}
    return web_response(status, json_dumps(value).encode(), headers)


def problem(status: int, reason: str) -> WebResponse:
    return reply(status, {"error": reason})


def valid_name(name: str) -> bool:
    if len(name) == 0 or len(name) > 200:
        return False
    for forbidden in ["/", "\\", "\x00", "\r", "\n"]:
        if forbidden in name:
            return False
    return name != "." and name != ".."


def expired(record: Json) -> bool:
    return json_float(record["expires"]) <= now()


def listing(request: WebRequest) -> WebResponse:
    prefix: str = request.query.get("prefix", "")
    visible: list[Json] = []
    total_bytes: int = 0
    for entry in records():
        if not expired(entry) and text(entry, "name").startswith(prefix):
            visible.append(entry)
            total_bytes = total_bytes + json_int(entry["size"])
    return reply(200, {"files": visible, "count": len(visible), "bytes": total_bytes})


def upload(request: WebRequest) -> WebResponse:
    name: str = request.query.get("name", "")
    if not valid_name(name):
        return problem(400, "name must be a safe basename of 1–200 characters")
    if len(request.body) > maximum_size():
        return problem(413, "file exceeds configured size limit")
    lifetime: int = default_lifetime()
    supplied: str = request.query.get("ttl", "")
    if supplied != "":
        value: Json = json_parse(supplied, None)
        if json_kind(value) != "number":
            return problem(400, "ttl must be an integer")
        try:
            lifetime = json_int(value)
        except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
            return problem(400, "ttl must be an integer")
    if lifetime < 1 or lifetime > 86400:
        return problem(400, "ttl must be between 1 and 86400 seconds")
    identifier: str = random_token()
    record: Json = {
        "id": identifier,
        "name": name,
        "size": len(request.body),
        "created": now(),
        "expires": now() + json_float(lifetime),
    }
    add(record, request.body)
    return reply(201, record)


def retrieve(identifier: str, metadata_only: bool) -> WebResponse:
    if not valid_id(identifier):
        return problem(404, "unknown file")
    record: Json = lookup(identifier)
    if text(record, "id") == "":
        return problem(404, "unknown file")
    if expired(record):
        return problem(410, "file expired")
    if metadata_only:
        return reply(200, record)
    headers: dict[str, str] = {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": "attachment; filename*=UTF-8''" + url_quote(text(record, "name")),
    }
    return web_response(200, read_blob(identifier), headers)


def remove(identifier: str) -> WebResponse:
    if not valid_id(identifier):
        return problem(404, "unknown file")
    record: Json = lookup(identifier)
    if text(record, "id") == "":
        return problem(404, "unknown file")
    erase(identifier)
    return reply(200, {"removed": identifier})


def sweep() -> WebResponse:
    removed: list[str] = []
    recovered: int = 0
    for entry in records():
        if expired(entry):
            identifier: str = text(entry, "id")
            recovered = recovered + json_int(entry["size"])
            erase(identifier)
            removed.append(identifier)
    return reply(200, {"removed": removed, "count": len(removed), "bytes": recovered})


def dispatch(request: WebRequest) -> WebResponse:
    if request.path == "/health" and request.method == "GET":
        return reply(200, {"service": "file-drop", "version": 1})
    if request.path == "/files":
        if request.method == "GET":
            return listing(request)
        if request.method == "POST":
            return upload(request)
        return problem(405, "use GET or POST")
    if request.path == "/sweep" and request.method == "POST":
        return sweep()
    if request.path.startswith("/metadata/") and request.method == "GET":
        return retrieve(request.path[10:], True)
    if request.path.startswith("/files/"):
        identifier: str = request.path[7:]
        if request.method == "GET":
            return retrieve(identifier, False)
        if request.method == "DELETE":
            return remove(identifier)
        return problem(405, "use GET or DELETE")
    return problem(404, "unknown route")


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception as failure:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
        print("file-drop request failed:", str(failure))
        return problem(500, "storage operation failed")


def main() -> None:
    validate_configuration()
    initialize()
    web_serve("127.0.0.1", setting_integer("DROP_PORT", 8766), handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
