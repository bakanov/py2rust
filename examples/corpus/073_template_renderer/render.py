"""Bounded interpretation of parsed templates with lexical loop bindings and HTML escaping."""

# ruff: noqa: PLC0206 - explicit returns and supported subset operations
from dataclasses import dataclass

from syntax import Node

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_canonical,
    json_float,
    json_keys,
    json_kind,
    json_string,
)


@dataclass
class Rendered:
    text: str
    steps: int


def lookup(path: str, scope: dict[str, Json], location: str) -> Json:
    parts: list[str] = path.split(".")
    assert parts[0] in scope, location + "missing variable: " + path
    value: Json = scope[parts[0]]
    for index in range(1, len(parts)):
        assert json_kind(value) == "object" and parts[index] in json_keys(value), location + "missing field: " + path
        value = value[parts[index]]
    return value


def truth(value: Json) -> bool:
    kind: str = json_kind(value)
    if kind == "null":
        return False
    if kind == "bool":
        return json_bool(value)
    if kind == "number":
        return json_float(value) != 0.0
    if kind == "string":
        return json_string(value) != ""
    if kind == "array":
        return len(json_array(value)) > 0
    return len(json_keys(value)) > 0


def escaped(value: Json, location: str) -> str:
    kind: str = json_kind(value)
    assert kind not in ["array", "object"], location + "substitution requires a scalar"
    text: str = "" if value is None else (json_string(value) if kind == "string" else json_canonical(value))
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def bind(scope: dict[str, Json], name: str, value: Json) -> dict[str, Json]:
    nested: dict[str, Json] = {}
    for key in scope:
        nested[key] = scope[key]
    nested[name] = value
    return nested


def render(
    nodes: list[Node], templates: dict[str, list[Node]], scope: dict[str, Json], budget: int, depth: int
) -> Rendered:
    assert depth <= 24, "render recursion exceeds 24"
    text: str = ""
    steps: int = 0
    for node in nodes:
        steps = steps + 1
        assert steps <= budget, node.location + "render step budget exhausted"
        part: str = ""
        if node.kind == "text":
            part = node.value
        elif node.kind == "value":
            part = escaped(lookup(node.value, scope, node.location), node.location)
        elif node.kind == "include":
            child: Rendered = render(templates[node.value], templates, scope, budget - steps, depth + 1)
            part = child.text
            steps = steps + child.steps
        elif node.kind == "if":
            selected: list[Node] = node.children if truth(lookup(node.value, scope, node.location)) else node.fallback
            child: Rendered = render(selected, templates, scope, budget - steps, depth + 1)
            part = child.text
            steps = steps + child.steps
        else:
            iterable: Json = lookup(node.value, scope, node.location)
            assert json_kind(iterable) == "array", node.location + "for requires an array"
            values: list[Json] = json_array(iterable)
            assert len(values) <= 256, node.location + "loop exceeds 256 items"
            for value in values:
                steps = steps + 1
                assert steps <= budget, node.location + "render step budget exhausted"
                child: Rendered = render(
                    node.children, templates, bind(scope, node.binding, value), budget - steps, depth + 1
                )
                part = part + child.text
                steps = steps + child.steps
                assert len(part.encode()) <= 1048576, node.location + "rendered output exceeds 1 MiB"
        text = text + part
        assert len(text.encode()) <= 1048576, node.location + "rendered output exceeds 1 MiB"
    return Rendered(text, steps)
