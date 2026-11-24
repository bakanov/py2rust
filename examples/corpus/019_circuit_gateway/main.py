"""Forward one request once; persist each circuit transition before returning a response."""

import math

from circuit import Phase, claim, finish
from model import clock, configuration, forwarded_headers
from storage import initialize, load, save, validate_paths

from py2rust.stdlib import (
    Json,
    WebRequest,
    WebResponse,
    env_get,
    json_array,
    json_bool,
    json_dumps,
    json_float,
    json_int,
    json_loads,
    json_string,
    regex_fullmatch,
    url_resolve,
    web_request,
    web_request_ca,
    web_response,
    web_serve,
)


def reply(status: int, value: Json, headers: dict[str, str]) -> WebResponse:
    headers["content-type"] = "application/json"
    headers["cache-control"] = "no-store"
    return web_response(status, json_dumps(value).encode(), headers)


def stop(point: str) -> None:
    assert env_get("GATEWAY_STOP", "") != point, "injected callback interruption"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def forward(request: WebRequest, url: str, policy: Json) -> WebResponse:
    headers: dict[str, str] = forwarded_headers(
        request.headers,
        [
            "accept",
            "content-type",
            "authorization",
            "if-match",
            "if-none-match",
            "idempotency-key",
            "x-request-id",
        ],
    )
    headers["Accept-Encoding"] = "identity"
    headers["Via"] = "1.1 py2rust-gateway"
    ca: str = env_get("GATEWAY_CA", "")
    if ca != "" and url.startswith("https://"):
        return web_request_ca(
            request.method, url, request.body, headers, json_int(policy["timeout_ms"]), json_int(policy["max_body"]), ca
        )
    return web_request(
        request.method, url, request.body, headers, json_int(policy["timeout_ms"]), json_int(policy["max_body"])
    )


def exchange(request: WebRequest, state: Json, index: int, url: str, now: float) -> WebResponse:
    records: list[Json] = json_array(state["circuits"])
    record: Json = records[index]
    assert not json_bool(record["inflight"]), "request outcome is unresolved"
    assert json_int(record["sequence"]) <= 999999998, "transition counter limit reached"
    assert json_int(record["calls"]) < 1000000000 and json_int(record["rejected"]) < 1000000000, "counter limit reached"
    if json_string(record["phase"]) == Phase.OPEN.value and now < json_float(record["retry_at"]):
        record["rejected"] = json_int(record["rejected"]) + 1
        records[index] = record
        state["circuits"] = records
        state["clock"] = now
        save(state)
        return reply(
            503,
            {"error": "circuit open", "id": record["id"], "retry_at": record["retry_at"]},
            {
                "Retry-After": str(max(1, math.ceil(json_float(record["retry_at"]) - now))),
                "X-Circuit-State": Phase.OPEN.value,
            },
        )
    records[index] = claim(record, now)
    state["circuits"] = records
    state["clock"] = now
    save(state)
    stop("after_claim")
    response: WebResponse = reply(502, {"error": "upstream transport failure"}, {})
    status: int = 0
    error: str = "transport"
    try:
        response = forward(request, url, state["policy"])
        assert response.status >= 200 and response.status <= 599, "unsupported upstream status"
        status = response.status
        error = ""
        if status == 408 or status == 429 or status >= 500:
            error = "http"
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        response = reply(502, {"error": "upstream transport failure"}, {})
    stop("after_response")
    ended: float = clock()
    assert ended >= now, "clock moved backwards during request"
    records[index] = finish(records[index], status, error, ended, state["policy"])
    state["circuits"] = records
    state["clock"] = ended
    save(state)
    stop("after_checkpoint")
    headers: dict[str, str] = forwarded_headers(
        response.headers,
        [
            "content-type",
            "content-encoding",
            "cache-control",
            "etag",
            "last-modified",
            "location",
            "retry-after",
            "www-authenticate",
        ],
    )
    headers["X-Circuit-State"] = json_string(records[index]["phase"])
    headers["Via"] = "1.1 py2rust-gateway"
    return web_response(response.status, response.body, headers)


def dispatch(request: WebRequest) -> WebResponse:
    validate_paths()
    policy: Json = configuration()
    state: Json = load(policy)
    if request.path == "/_gateway/state":
        if request.method != "GET":
            return reply(405, {"error": "use GET for circuit state"}, {"Allow": "GET"})
        return reply(200, {"clock": state["clock"], "circuits": state["circuits"]}, {})
    for record in json_array(state["circuits"]):
        if json_bool(record["inflight"]):
            return reply(503, {"error": "unresolved request; restart gateway to recover"}, {})
    if "py2rust-gateway" in request.headers.get("via", ""):
        return reply(508, {"error": "gateway loop"}, {})
    if len(request.body) > json_int(policy["max_body"]):
        return reply(413, {"error": "request body exceeds limit"}, {})
    if len(request.target.encode()) > 8192:
        return reply(414, {"error": "request target exceeds limit"}, {})
    now: float = clock()
    assert now >= json_float(state["clock"]), "clock moved backwards"
    routes: list[Json] = json_array(policy["routes"])
    for index in range(len(routes)):
        route: Json = routes[index]
        if request.path == json_string(route["path"]):
            methods: list[str] = []
            for item in json_array(route["methods"]):
                methods.append(json_string(item))
            if request.method not in methods:
                return reply(405, {"error": "method not configured"}, {"Allow": ", ".join(methods)})
            url: str = json_string(route["url"])
            try:
                assert request.target == request.path or request.target.startswith(
                    request.path + "?"
                ), "expected origin-form target"
                suffix: str = request.target[len(request.path) :]
                assert "#" not in suffix and regex_fullmatch("[!-~]*", suffix), "invalid query bytes"
                url = url + suffix
                url_resolve(url, "")
            except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
                return reply(400, {"error": "invalid request target"}, {})
            return exchange(request, state, index, url, now)
    return reply(404, {"error": "route not configured"}, {})


def handle(request: WebRequest) -> WebResponse:
    try:
        return dispatch(request)
    except Exception:  # noqa: BLE001 - the compiled subset uses recoverable Exception
        return reply(500, {"error": "gateway state, clock or configuration failure"}, {})


def main() -> None:
    validate_paths()
    initialize(configuration())
    port: int = json_int(json_loads(env_get("GATEWAY_PORT", "8784")))
    assert port >= 0 and port <= 65535, "invalid port"
    web_serve("127.0.0.1", port, handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
