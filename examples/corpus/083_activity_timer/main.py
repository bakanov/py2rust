"""Local HTTP commands commit each valid timer transition before replying."""

# ruff: noqa: BLE001, LOG015, PLR1711 - recoverable boundaries and explicit subset returns
import logging

from config import clocks, configure, now, setting, state_path
from model import exact, execute, identifier, title
from storage import document, initialize, load, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    file_lock,
    json_canonical,
    json_loads,
    json_string,
    process_exit,
    web_response,
    web_serve,
)


def reply(status: int, value: Json, export: bool) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json", "Cache-Control": "no-store"}
    if export:
        headers["Content-Disposition"] = 'attachment; filename="activity.json"'
    return web_response(status, json_canonical(value).encode(), headers)


def command(request: WebRequest) -> Json:
    key: str = ""
    name: str = ""
    operation: str = request.path[1:]
    if request.method == "POST":
        assert len(request.query) == 0, "unexpected query fields"
        body: Json = json_loads(request.body.decode())
        fields: list[str] = ["id", "name"] if operation == "start" else ["id"]
        exact(body, fields)
        key = identifier(body["id"])
        if operation == "start":
            name = title(body["name"])
    else:
        assert len(request.body) == 0, "unexpected request body"
        if operation == "session":
            assert len(request.query) == 1 and "id" in request.query, "expected one session ID"
            key = identifier(request.query["id"])
            operation = "get"
        else:
            assert len(request.query) == 0, "unexpected query fields"
            operation = "report"
    return {"op": operation, "id": key, "name": name}


def handle(request: WebRequest) -> WebResponse:
    if request.path not in ["/start", "/pause", "/resume", "/stop", "/session", "/report", "/export"]:
        return reply(404, {"error": "unknown route"}, False)
    method: str = "GET" if request.path in ["/session", "/report", "/export"] else "POST"
    if request.method != method:
        return reply(405, {"error": "method not allowed"}, False)
    if len(request.body) > 4096:
        return reply(413, {"error": "request body exceeds 4096 bytes"}, False)
    instruction: Json = None
    try:
        instruction = command(request)
    except Exception:
        return reply(400, {"error": "invalid timer request"}, False)
    try:
        state: Json = load()
        original: str = document(state)
        sample: tuple[int, int] = clocks()
        state["clock_ms"] = now(state, sample)
        state["mono_ms"] = sample[1]
        result: tuple[Json, int, Json] = execute(
            state, json_string(instruction["op"]), json_string(instruction["id"]), json_string(instruction["name"])
        )
        state = result[0]
        if result[1] >= 400:
            return reply(result[1], result[2], False)
        if document(state) != original:
            save(state, True)
        return reply(result[1], result[2], request.path == "/export")
    except Exception:
        return reply(500, {"error": "timer storage or clock operation failed; inspect state before retrying"}, False)


def main() -> None:
    try:
        configure()
        with file_lock(state_path() + ".lock") as _guard:
            initialize()
            web_serve("127.0.0.1", setting("TIMER_PORT", 8793), handle)
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
