"""Iterative prerequisite traversal, Kahn build layers and a concrete directed cycle witness."""

# ruff: noqa: C414 - sorting takes an explicit typed list

from model import Graph

from py2rust.stdlib import Json, json_array, json_string


def closure(graph: Graph, requested: list[str]) -> set[str]:
    pending: list[str] = requested.copy()
    selected: set[str] = set()
    while len(pending) > 0:
        name: str = pending.pop()
        if name not in selected:
            selected.add(name)
            pending.extend(graph.requires[name])
    return selected


def witness(graph: Graph, requested: list[str], blocked: set[str]) -> tuple[list[str], list[str]]:
    finished: set[str] = set()
    for root in requested:
        if root not in blocked or root in finished:
            continue
        stack: list[tuple[str, int]] = [(root, 0)]
        path: list[str] = [root]
        positions: dict[str, int] = {root: 0}
        while len(stack) > 0:
            frame: tuple[str, int] = stack[-1]
            name: str = frame[0]
            index: int = frame[1]
            neighbors: list[str] = graph.requires[name]
            if index == len(neighbors):
                stack.pop()
                path.pop()
                del positions[name]
                finished.add(name)
                continue
            stack[-1] = (name, index + 1)
            following: str = neighbors[index]
            if following not in blocked or following in finished:
                continue
            if following in positions:
                start: int = positions[following]
                return (path[start:] + [following], path[: start + 1])
            positions[following] = len(path)
            path.append(following)
            stack.append((following, 0))
    assert len(blocked) == 0, "internal error: blocked graph has no cycle witness"
    return ([], [])


def plan(graph: Graph, request: Json) -> Json:
    requested: list[str] = []
    for value in json_array(request["targets"]):
        requested.append(json_string(value))
    selected: set[str] = closure(graph, requested)
    remaining: dict[str, int] = {}
    ready: list[str] = []
    for name in sorted(list(selected)):
        remaining[name] = len(graph.requires[name])
        if remaining[name] == 0:
            ready.append(name)
    layers: list[list[str]] = []
    order: list[str] = []
    completed: set[str] = set()
    while len(ready) > 0:
        layers.append(ready)
        following: list[str] = []
        for name in ready:
            order.append(name)
            completed.add(name)
            for dependent in graph.dependents[name]:
                if dependent in selected:
                    remaining[dependent] = remaining[dependent] - 1
                    if remaining[dependent] == 0:
                        following.append(dependent)
        ready = sorted(following)
    blocked: set[str] = selected - completed
    found: tuple[list[str], list[str]] = witness(graph, requested, blocked)
    prerequisites: set[str] = selected - set(requested)
    return {
        "id": request["id"],
        "status": "ready" if len(blocked) == 0 else "cycle",
        "requested": requested,
        "selected": sorted(list(selected)),
        "prerequisites": sorted(list(prerequisites)),
        "layers": layers,
        "order": order,
        "blocked": sorted(list(blocked)),
        "cycle": found[0],
        "requires_path": found[1],
    }
