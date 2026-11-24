"""Summarize HTTP access logs without depending on a particular web server."""

from dataclasses import dataclass

from py2rust.stdlib import Json, json_int, json_loads, json_string


@dataclass
class Summary:
    requests: int
    errors: int
    total_bytes: int
    max_elapsed_ms: int
    routes: dict[str, int]


def summarize(text: str) -> Summary:
    requests: int = 0
    errors: int = 0
    total_bytes: int = 0
    max_elapsed_ms: int = 0
    routes: dict[str, int] = {}
    for raw_line in text.split("\n"):
        line: str = raw_line.strip()
        if line != "":
            event: Json = json_loads(line)
            path: str = json_string(event["path"])
            status: int = json_int(event["status"])
            size: int = json_int(event["bytes"])
            elapsed_ms: int = json_int(event["elapsed_ms"])
            assert path.startswith("/"), "expected an absolute request path"
            assert 100 <= status and status <= 599, "invalid HTTP status"
            assert size >= 0 and elapsed_ms >= 0, "negative measurement"
            route: str = path.split("?")[0]
            routes[route] = routes.get(route, 0) + 1
            requests = requests + 1
            total_bytes = total_bytes + size
            if status >= 400:
                errors = errors + 1
            if elapsed_ms > max_elapsed_ms:
                max_elapsed_ms = elapsed_ms
    return Summary(requests, errors, total_bytes, max_elapsed_ms, routes)
