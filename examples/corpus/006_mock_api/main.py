"""A deterministic HTTP fixture server driven by a validated JSON scenario."""

from routes import (
    configuration,
    configured_response,
    field_errors,
    text,
    validate_routes,
)
from state import fresh, initialize, load, record, save

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    env_get,
    json_array,
    json_dumps,
    json_int,
    json_parse,
    web_response,
    web_serve,
)


def reply(status: int, payload: Json) -> WebResponse:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    return web_response(status, json_dumps(payload).encode(), headers)


def admin(request: WebRequest, config: Json) -> WebResponse:
    if request.path == "/_mock/reset" and request.method == "POST":
        save(fresh(config))
        return reply(200, {"reset": True, "scenario": text(config, "initial", "")})
    state: Json = load()
    if request.path == "/_mock/state" and request.method == "GET":
        return reply(200, {"scenario": state["scenario"], "sequence": state["sequence"]})
    if request.path == "/_mock/transcript" and request.method == "GET":
        return reply(200, state["transcript"])
    return reply(404, {"error": "unknown administration route"})


def dispatch(request: WebRequest) -> WebResponse:
    config: Json = configuration()
    validate_routes(config)
    if request.path.startswith("/_mock/"):
        return admin(request, config)
    state: Json = load()
    if json_int(state["sequence"]) >= 1000:
        return reply(503, {"error": "transcript full; reset required"})
    current: str = text(state, "scenario", "")
    selected: Json = {}
    wildcard: Json = {}
    matched_path: bool = False
    for route in json_array(config["routes"]):
        if text(route, "method", "GET") == request.method and text(route, "path", "") == request.path:
            matched_path = True
            when: str = text(route, "when", "*")
            if when == current:
                selected = route
            if when == "*":
                wildcard = route
    if text(selected, "id", "") == "":
        selected = wildcard
    event: Json = {"method": request.method, "path": request.path, "body_hex": request.body.hex()}
    status: int = 404
    following: str = current
    error: str = "unknown route"
    if matched_path:
        status = 409
        error = "route unavailable in current scenario"
    if text(selected, "id", "") != "":
        body: Json = None
        if len(request.body) > 0:
            try:
                body = json_parse(request.body.decode(), None)
            except Exception:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
                body = None
        errors: list[str] = field_errors(selected, body)
        if len(errors) > 0:
            event["status"] = 400
            event["errors"] = errors
            record(state, event, current)
            return reply(400, {"errors": errors})
        status = json_int(selected["status"])
        following = text(selected, "next", current)
        if following == "":
            following = current
        event["route"] = text(selected, "id", "")
        event["status"] = status
        record(state, event, following)
        return configured_response(selected)
    event["status"] = status
    record(state, event, following)
    return reply(status, {"error": error, "scenario": current})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception as failure:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
        print("mock API failed:", str(failure))
        return reply(500, {"error": "mock API storage or configuration failure"})


def main() -> None:
    config: Json = configuration()
    validate_routes(config)
    initialize(config)
    port: int = json_int(json_parse(env_get("MOCK_PORT", "8767"), None))
    assert port >= 0 and port <= 65535, "port out of range"
    web_serve("127.0.0.1", port, handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
