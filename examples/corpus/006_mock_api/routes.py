"""Validate a finite scenario graph and encode configured responses."""

from py2rust.stdlib import (
    Json,
    WebResponse,
    env_get,
    json_array,
    json_dumps,
    json_equal,
    json_get,
    json_int,
    json_kind,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    web_response,
)


def text(value: Json, key: str, default: str) -> str:
    result: Json = json_get(value, key, default)
    assert json_kind(result) == "string", "expected string field: " + key
    return json_string(result)


def configuration() -> Json:
    return json_loads(read_text(env_get("MOCK_CONFIG", "routes.json")))


def response_body(route: Json) -> bytes:
    encoding: str = text(route, "encoding", "json")
    value: Json = json_get(route, "body", None)
    if encoding == "json":
        return json_dumps(value).encode()
    if encoding == "text":
        return json_string(value).encode()
    assert encoding == "hex", "unknown response encoding"
    return bytes.fromhex(json_string(value))


def response_headers(route: Json) -> dict[str, str]:
    encoding: str = text(route, "encoding", "json")
    content_type: str = "application/json"
    if encoding == "text":
        content_type = "text/plain; charset=utf-8"
    if encoding == "hex":
        content_type = "application/octet-stream"
    headers: dict[str, str] = {"Content-Type": content_type}
    for header in json_array(json_get(route, "headers", [])):
        name: str = text(header, "name", "")
        value: str = text(header, "value", "")
        assert regex_fullmatch("[A-Za-z0-9-]+", name), "invalid header name"
        assert "\r" not in value and "\n" not in value, "invalid header value"
        assert name.lower() not in ["content-length", "transfer-encoding", "connection"], "reserved header"
        headers[name] = value
    return headers


def configured_response(route: Json) -> WebResponse:
    return web_response(json_int(route["status"]), response_body(route), response_headers(route))


def validate_routes(config: Json) -> None:
    assert json_kind(config) == "object", "configuration must be an object"
    states: list[str] = []
    for item in json_array(config["states"]):
        state: str = json_string(item)
        assert state != "" and state != "*", "invalid state name"
        assert state not in states, "duplicate state"
        states.append(state)
    assert text(config, "initial", "") in states, "initial state is not declared"
    assert len(states) <= 64, "too many scenario states"
    routes: list[Json] = json_array(config["routes"])
    assert len(routes) > 0 and len(routes) <= 200, "expected 1–200 routes"
    identifiers: set[str] = set()
    selectors: set[str] = set()
    for route in routes:
        identifier: str = text(route, "id", "")
        assert identifier != "" and identifier not in identifiers, "route IDs must be unique"
        identifiers.add(identifier)
        method: str = text(route, "method", "GET")
        assert method in ["GET", "POST", "PUT", "DELETE"], "unsupported method"
        path: str = text(route, "path", "")
        assert path.startswith("/") and not path.startswith("/_mock"), "invalid route path"
        assert "?" not in path and "#" not in path, "route paths exclude query and fragment"
        current: str = text(route, "when", "*")
        following: str = text(route, "next", "")
        assert current == "*" or current in states, "unknown source state"
        assert following == "" or following in states, "unknown destination state"
        selector: str = method + " " + path + " " + current
        assert selector not in selectors, "duplicate route selector"
        selectors.add(selector)
        status: int = json_int(route["status"])
        assert status >= 200 and status <= 599, "unsupported response status"
        payload: bytes = response_body(route)
        assert len(payload) <= 1048576, "response exceeds one MiB"
        assert status != 204 or len(payload) == 0, "204 responses must be empty"
        response_headers(route)
        fields: set[str] = set()
        for rule in json_array(json_get(route, "require", [])):
            field: str = text(rule, "field", "")
            assert field != "" and field not in fields, "duplicate or empty request field"
            fields.add(field)
            kind: str = text(rule, "kind", "any")
            assert kind in ["any", "string", "number", "bool", "array", "object", "null"], "invalid field kind"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def field_errors(route: Json, body: Json) -> list[str]:
    errors: list[str] = []
    rules: list[Json] = json_array(json_get(route, "require", []))
    if len(rules) == 0:
        return errors
    if json_kind(body) != "object":
        errors.append("request must contain a JSON object")
        return errors
    for rule in rules:
        field: str = text(rule, "field", "")
        # Membership distinguishes a missing field from an explicit JSON null.
        if field not in body:
            errors.append(field + ": missing")
            continue
        value: Json = body[field]
        kind: str = text(rule, "kind", "any")
        if kind != "any" and json_kind(value) != kind:
            errors.append(field + ": expected " + kind)
        if "equals" in rule and not json_equal(value, rule["equals"]):
            errors.append(field + ": value mismatch")
    return errors
