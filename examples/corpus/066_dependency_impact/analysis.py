"""Iterative Kosaraju components and breadth-first dependency impact explanations."""

# ruff: noqa: C414 - sorting takes an explicit typed list

from dataclasses import dataclass

from model import Graph

from py2rust.stdlib import Json, json_array, json_string


@dataclass
class Partition:
    groups: list[list[str]]
    group_for: dict[str, str]


def finishing_order(graph: Graph) -> list[str]:
    visited: set[str] = set()
    finished: list[str] = []
    for root in graph.names:
        if root in visited:
            continue
        visited.add(root)
        stack: list[tuple[str, int]] = [(root, 0)]
        while len(stack) > 0:
            frame: tuple[str, int] = stack[-1]
            module: str = frame[0]
            index: int = frame[1]
            if index == len(graph.dependencies[module]):
                finished.append(module)
                stack.pop()
                continue
            stack[-1] = (module, index + 1)
            following: str = graph.dependencies[module][index]
            if following not in visited:
                visited.add(following)
                stack.append((following, 0))
    return finished


def partition(graph: Graph) -> Partition:
    order: list[str] = finishing_order(graph)
    order.reverse()
    visited: set[str] = set()
    groups: list[list[str]] = []
    for root in order:
        if root in visited:
            continue
        pending: list[str] = [root]
        visited.add(root)
        members: list[str] = []
        while len(pending) > 0:
            module: str = pending.pop()
            members.append(module)
            for following in graph.dependents[module]:
                if following not in visited:
                    visited.add(following)
                    pending.append(following)
        groups.append(sorted(members))
    groups = sorted(groups)
    group_for: dict[str, str] = {}
    for members in groups:
        for module in members:
            group_for[module] = members[0]
    return Partition(groups, group_for)


def describe(graph: Graph, components: Partition) -> Json:
    groups: list[Json] = []
    cyclic_count: int = 0
    for members in components.groups:
        identifier: str = members[0]
        dependencies: set[str] = set()
        dependents: set[str] = set()
        for module in members:
            for following in graph.dependencies[module]:
                if components.group_for[following] != identifier:
                    dependencies.add(components.group_for[following])
            for following in graph.dependents[module]:
                if components.group_for[following] != identifier:
                    dependents.add(components.group_for[following])
        cyclic: bool = len(members) > 1 or identifier in graph.dependencies[identifier]
        if cyclic:
            cyclic_count = cyclic_count + 1
        groups.append(
            {
                "id": identifier,
                "members": members,
                "cyclic": cyclic,
                "dependencies": sorted(list(dependencies)),
                "dependents": sorted(list(dependents)),
            }
        )
    modules: list[Json] = []
    for module in graph.names:
        modules.append(
            {
                "name": module,
                "dependencies": graph.dependencies[module],
                "dependents": graph.dependents[module],
                "group": components.group_for[module],
            }
        )
    return {
        "counts": {
            "modules": len(graph.names),
            "edges": graph.edges,
            "groups": len(groups),
            "cyclic_groups": cyclic_count,
        },
        "modules": modules,
        "groups": groups,
    }


def impact(graph: Graph, components: Partition, request: Json) -> Json:
    changed: list[str] = []
    for value in json_array(request["changed"]):
        changed.append(json_string(value))
    queue: list[str] = changed.copy()
    parent: dict[str, str] = {}
    origin: dict[str, str] = {}
    hops: dict[str, int] = {}
    for module in changed:
        parent[module] = module
        origin[module] = module
        hops[module] = 0
    cursor: int = 0
    while cursor < len(queue):
        module: str = queue[cursor]
        cursor = cursor + 1
        for following in graph.dependents[module]:
            if following not in parent:
                parent[following] = module
                origin[following] = origin[module]
                hops[following] = hops[module] + 1
                queue.append(following)
    affected: list[str] = sorted(list(parent))
    unaffected: list[str] = []
    for module in graph.names:
        if module not in parent:
            unaffected.append(module)
    impacted_groups: set[str] = set()
    explanations: list[Json] = []
    for module in affected:
        impacted_groups.add(components.group_for[module])
        path: list[str] = [module]
        current: str = module
        while current != origin[module]:
            current = parent[current]
            assert len(path) < len(graph.names), "invalid explanation predecessor chain"
            path.append(current)
        explanations.append(
            {"module": module, "changed": module in changed, "root": origin[module], "hops": hops[module], "path": path}
        )
    return {
        "id": request["id"],
        "changed": changed,
        "affected": affected,
        "unaffected": unaffected,
        "groups": sorted(list(impacted_groups)),
        "explanations": explanations,
    }
