"""Plan a bounded batch of routes and explain each result in JSON and plain text."""

import sys

from model import text, validate
from solver import solve

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_int,
    json_loads,
    json_string,
    pretty,
    read_text,
    write_text_atomic,
)


def explain(result: Json) -> str:
    heading: str = text(result, "from") + " -> " + text(result, "to") + ": "
    status: str = text(result, "status")
    if status == "closed":
        return heading + "an endpoint is closed"
    if status == "unreachable":
        return heading + "no directed path remains after closures"
    if status == "negative_cycle":
        return heading + "no finite minimum; a reachable negative cycle can lead to the destination"
    route: list[str] = []
    for name in json_array(result["nodes"]):
        route.append(json_string(name))
    return heading + "cost " + str(json_int(result["cost"])) + " via " + " -> ".join(route)


def main() -> None:
    graph: Json = json_loads(read_text(env_get("ROUTE_INPUT", "graph.json")))
    validate(graph)
    queries: list[Json] = json_array(graph["queries"])
    assert len(queries) > 0 and len(queries) <= 100, "expected 1–100 route queries"
    results: list[Json] = []
    explanations: list[str] = []
    failures: int = 0
    for query in queries:
        result: Json = solve(graph, query)
        results.append(result)
        explanations.append(explain(result))
        if text(result, "status") != "ok":
            failures = failures + 1
    report: Json = {"routes": results, "queries": len(queries), "without_finite_route": failures}
    write_text_atomic(env_get("ROUTE_REPORT", "routes.json"), pretty(report))
    write_text_atomic(env_get("ROUTE_TEXT", "routes.txt"), "\n".join(explanations) + "\n")
    print(pretty(report))
    if failures > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
