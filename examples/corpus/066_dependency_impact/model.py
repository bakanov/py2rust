"""Strict module graphs, sorted reverse dependencies and normalized change requests."""

# ruff: noqa: PLR1711, C414 - explicit returns and sorting typed lists

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_string


@dataclass
class Graph:
    names: list[str]
    dependencies: dict[str, list[str]]
    dependents: dict[str, list[str]]
    edges: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def name(value: Json) -> str:
    result: str = json_string(value)
    assert 1 <= len(result) <= 128 and len(result.encode()) <= 512 and "\x00" not in result, "invalid name"
    return result


def load(value: Json) -> Graph:
    exact(value, ["version", "modules", "edges"])
    assert json_int(value["version"]) == 1, "unsupported graph version"
    modules: list[Json] = json_array(value["modules"])
    edges: list[Json] = json_array(value["edges"])
    assert len(modules) <= 256 and len(edges) <= 4096, "graph capacity exceeded"
    dependencies: dict[str, list[str]] = {}
    dependents: dict[str, list[str]] = {}
    for item in modules:
        module: str = name(item)
        assert module not in dependencies, "duplicate module"
        dependencies[module] = []
        dependents[module] = []
    for edge in edges:
        exact(edge, ["module", "depends_on"])
        module: str = name(edge["module"])
        dependency: str = name(edge["depends_on"])
        assert module in dependencies and dependency in dependencies, "unknown edge endpoint"
        assert dependency not in dependencies[module], "duplicate dependency edge"
        dependencies[module].append(dependency)
        dependents[dependency].append(module)
    names: list[str] = sorted(list(dependencies))
    for module in names:
        dependencies[module] = sorted(dependencies[module])
        dependents[module] = sorted(dependents[module])
    return Graph(names, dependencies, dependents, len(edges))


def document(graph: Graph) -> Json:
    edges: list[Json] = []
    for module in graph.names:
        for dependency in graph.dependencies[module]:
            edges.append({"module": module, "depends_on": dependency})
    return {"version": 1, "modules": graph.names, "edges": edges}


def requests(graph: Graph, value: Json) -> list[Json]:
    rows: list[Json] = json_array(value)
    assert len(rows) <= 64, "request count exceeds 64"
    seen: set[str] = set()
    result: list[Json] = []
    for row in rows:
        exact(row, ["id", "changed"])
        identifier: str = name(row["id"])
        assert identifier not in seen, "duplicate request id"
        seen.add(identifier)
        values: list[Json] = json_array(row["changed"])
        assert len(values) <= 256, "change count exceeds 256"
        selected: set[str] = set()
        for item in values:
            module: str = name(item)
            assert module in graph.dependencies, "unknown changed module"
            selected.add(module)
        result.append({"id": identifier, "changed": sorted(list(selected))})
    return result
