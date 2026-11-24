"""Bellman–Ford with directed route and relevant negative-cycle witnesses."""

from model import closed_nodes, names, open_edges, text, validate_query

from py2rust.stdlib import Json, json_int


def can_reach(edges: list[Json], destination: str, count: int) -> set[str]:
    reachable: set[str] = {destination}
    for step in range(count):
        for edge in edges:
            if text(edge, "to") in reachable:
                reachable.add(text(edge, "from"))
    return reachable


def route_path(start: str, destination: str, parents: dict[str, Json], count: int) -> Json:
    nodes: list[str] = [destination]
    edges: list[str] = []
    current: str = destination
    seen: set[str] = {destination}
    while current != start:
        assert current in parents, "route predecessor is missing"
        parent: Json = parents[current]
        edges.append(text(parent, "id"))
        current = text(parent, "from")
        assert current not in seen, "finite route contains a cycle"
        seen.add(current)
        nodes.append(current)
        assert len(nodes) <= count, "route exceeds node bound"
    nodes.reverse()
    edges.reverse()
    return {"nodes": nodes, "edges": edges}


def negative_cycle(seed: str, parents: dict[str, Json], count: int) -> Json:
    current: str = seed
    # Walking n predecessors moves past any path leading out of the cycle.
    for step in range(count):
        current = text(parents[current], "from")
    start: str = current
    nodes: list[str] = [start]
    edges: list[str] = []
    total: int = 0
    for step in range(count + 1):
        parent: Json = parents[current]
        edges.append(text(parent, "id"))
        total = total + json_int(parent["cost"])
        current = text(parent, "from")
        nodes.append(current)
        if current == start:
            break
    assert current == start and total < 0, "invalid negative-cycle witness"
    nodes.reverse()
    edges.reverse()
    return {"nodes": nodes, "edges": edges, "cost": total}


def diagnose_unreachable(start: str, vertices: list[str], edges: list[Json]) -> Json:
    reachable: set[str] = {start}
    for step in range(len(vertices)):
        for edge in edges:
            if text(edge, "from") in reachable:
                reachable.add(text(edge, "to"))
    reached: list[str] = []
    unavailable: list[str] = []
    for vertex in vertices:
        if vertex in reachable:
            reached.append(vertex)
        else:
            unavailable.append(vertex)
    reached.sort()
    unavailable.sort()
    return {
        "reachable": reached,
        "unreachable": unavailable,
        "reachable_count": len(reached),
        "open_edges": len(edges),
        "reason": "destination is outside the source's reachable component",
    }


def solve(graph: Json, query: Json) -> Json:
    validate_query(graph, query)
    start: str = text(query, "from")
    destination: str = text(query, "to")
    closed: set[str] = closed_nodes(query)
    if start in closed or destination in closed:
        return {"status": "closed", "from": start, "to": destination}
    vertices: list[str] = names(graph)
    edges: list[Json] = open_edges(graph, query)
    distances: dict[str, int] = {start: 0}
    parents: dict[str, Json] = {}
    changed: list[str] = []
    passes: int = 0
    relaxations: int = 0
    for iteration in range(len(vertices)):
        changed = []
        passes = passes + 1
        for edge in edges:
            source: str = text(edge, "from")
            target: str = text(edge, "to")
            if source in distances:
                cost: int = distances[source] + json_int(edge["cost"])
                if target not in distances or cost < distances[target]:
                    distances[target] = cost
                    parents[target] = edge
                    changed.append(target)
                    relaxations = relaxations + 1
        if len(changed) == 0:
            break
    relevant: set[str] = can_reach(edges, destination, len(vertices))
    for seed in changed:
        if seed in relevant:
            return {
                "status": "negative_cycle",
                "from": start,
                "to": destination,
                "cycle": negative_cycle(seed, parents, len(vertices)),
                "passes": passes,
            }
    if destination not in distances:
        return {
            "status": "unreachable",
            "from": start,
            "to": destination,
            "passes": passes,
            "diagnosis": diagnose_unreachable(start, vertices, edges),
        }
    path: Json = route_path(start, destination, parents, len(vertices))
    return {
        "status": "ok",
        "from": start,
        "to": destination,
        "cost": distances[destination],
        "nodes": path["nodes"],
        "edges": path["edges"],
        "passes": passes,
        "relaxations": relaxations,
    }
