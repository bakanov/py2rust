"""Validated target definitions and deterministic forward/reverse dependency maps."""

# ruff: noqa: PLR1711, C414 - explicit returns and typed-list sorting

from dataclasses import dataclass

from py2rust.stdlib import Json, json_array, json_int, json_keys, json_string


@dataclass
class Graph:
    commands: dict[str, list[str]]
    requires: dict[str, list[str]]
    dependents: dict[str, list[str]]
    edges: int


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def text(value: Json, maximum: int, allow_empty: bool) -> str:
    result: str = json_string(value)
    assert (allow_empty or result != "") and "\x00" not in result, "invalid text"
    assert len(result) <= maximum and len(result.encode()) <= maximum * 4, "text exceeds limit"
    return result


def load(value: Json) -> Graph:
    exact(value, ["version", "targets", "edges"])
    assert json_int(value["version"]) == 1, "unsupported graph version"
    targets: list[Json] = json_array(value["targets"])
    edges: list[Json] = json_array(value["edges"])
    assert len(targets) <= 256 and len(edges) <= 4096, "graph capacity exceeded"
    commands: dict[str, list[str]] = {}
    requires: dict[str, list[str]] = {}
    dependents: dict[str, list[str]] = {}
    for target in targets:
        exact(target, ["name", "command"])
        name: str = text(target["name"], 128, False)
        assert name not in commands, "duplicate target: " + name
        arguments: list[Json] = json_array(target["command"])
        assert len(arguments) <= 32, "command exceeds 32 arguments"
        command: list[str] = []
        for argument in arguments:
            command.append(text(argument, 1024, True))
        assert len(command) == 0 or command[0] != "", "empty command executable"
        commands[name] = command
        requires[name] = []
        dependents[name] = []
    for edge in edges:
        exact(edge, ["target", "requires"])
        target_name: str = text(edge["target"], 128, False)
        prerequisite: str = text(edge["requires"], 128, False)
        assert target_name in commands and prerequisite in commands, "unknown edge endpoint"
        children: list[str] = requires[target_name]
        assert prerequisite not in children, "duplicate dependency edge"
        children.append(prerequisite)
        requires[target_name] = children
        parents: list[str] = dependents[prerequisite]
        parents.append(target_name)
        dependents[prerequisite] = parents
    for name in sorted(list(commands)):
        requires[name] = sorted(requires[name])
        dependents[name] = sorted(dependents[name])
    return Graph(commands, requires, dependents, len(edges))


def document(graph: Graph) -> Json:
    targets: list[Json] = []
    edges: list[Json] = []
    for name in sorted(list(graph.commands)):
        targets.append({"name": name, "command": graph.commands[name]})
        for prerequisite in graph.requires[name]:
            edges.append({"target": name, "requires": prerequisite})
    return {"version": 1, "targets": targets, "edges": edges}


def requests(graph: Graph, value: Json) -> list[Json]:
    rows: list[Json] = json_array(value)
    assert len(rows) <= 128, "request count exceeds 128"
    seen: set[str] = set()
    result: list[Json] = []
    for row in rows:
        exact(row, ["id", "targets"])
        identifier: str = text(row["id"], 128, False)
        assert identifier not in seen, "duplicate request id"
        seen.add(identifier)
        names: list[Json] = json_array(row["targets"])
        assert len(names) <= 256, "requested target count exceeds 256"
        selected: set[str] = set()
        for item in names:
            name: str = text(item, 128, False)
            assert name in graph.commands, "unknown requested target: " + name
            selected.add(name)
        result.append({"id": identifier, "targets": sorted(list(selected))})
    return result
