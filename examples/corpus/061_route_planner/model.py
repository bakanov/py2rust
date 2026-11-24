"""Named directed graphs, explicit edge IDs, and per-query closures."""

from py2rust.stdlib import Json, json_array, json_get, json_int, json_string


def names(graph: Json) -> list[str]:
    result: list[str] = []
    for item in json_array(graph["nodes"]):
        result.append(json_string(item))
    return result


def text(value: Json, key: str) -> str:
    return json_string(value[key])


def validate(graph: Json) -> None:
    vertices: list[str] = names(graph)
    assert len(vertices) > 0 and len(vertices) <= 100, "expected 1–100 graph nodes"
    seen: set[str] = set()
    for name in vertices:
        assert len(name) > 0 and len(name) <= 128, "invalid node name"
        assert name not in seen, "duplicate graph node"
        seen.add(name)
    edges: list[Json] = json_array(graph["edges"])
    assert len(edges) <= 2000, "graph exceeds 2000 edges"
    identifiers: set[str] = set()
    for edge in edges:
        identifier: str = text(edge, "id")
        assert identifier != "" and identifier not in identifiers, "edge IDs must be unique"
        identifiers.add(identifier)
        assert text(edge, "from") in seen and text(edge, "to") in seen, "edge references an unknown node"
        cost: int = json_int(edge["cost"])
        assert cost >= -1000000000 and cost <= 1000000000, "edge cost exceeds supported bound"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_query(graph: Json, query: Json) -> None:
    vertices: list[str] = names(graph)
    assert text(query, "from") in vertices and text(query, "to") in vertices, "unknown query endpoint"
    for node in json_array(json_get(query, "closed_nodes", [])):
        assert json_string(node) in vertices, "unknown closed node"
    identifiers: set[str] = set()
    for edge in json_array(graph["edges"]):
        identifiers.add(text(edge, "id"))
    for identifier in json_array(json_get(query, "closed_edges", [])):
        assert json_string(identifier) in identifiers, "unknown closed edge"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def closed_nodes(query: Json) -> set[str]:
    result: set[str] = set()
    for node in json_array(json_get(query, "closed_nodes", [])):
        result.add(json_string(node))
    return result


def open_edges(graph: Json, query: Json) -> list[Json]:
    closed: set[str] = closed_nodes(query)
    identifiers: set[str] = set()
    for identifier in json_array(json_get(query, "closed_edges", [])):
        identifiers.add(json_string(identifier))
    result: list[Json] = []
    for edge in json_array(graph["edges"]):
        if text(edge, "from") not in closed and text(edge, "to") not in closed and text(edge, "id") not in identifiers:
            result.append(edge)
    return result
