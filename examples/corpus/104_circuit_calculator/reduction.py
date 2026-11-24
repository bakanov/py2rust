"""Reduce every subtree in postorder, using scaled sums and explicit open/short states."""

# ruff: noqa: BLE001 - each invalid circuit has a recoverable diagnostic

from dataclasses import dataclass

from model import Node, parse, text

from py2rust.stdlib import Json


@dataclass
class Equivalent:
    state: str
    ohms: float


def measure(value: Equivalent) -> Json:
    return {"state": value.state, "ohms": None if value.state == "open" else value.ohms}


def compensated(values: list[float]) -> float:
    total: float = 0.0
    correction: float = 0.0
    for value in values:
        adjusted: float = value - correction
        updated: float = total + adjusted
        correction = (updated - total) - adjusted
        total = updated
    return total


def combine(kind: str, inputs: list[Equivalent]) -> tuple[Equivalent, str, Json]:
    finite: list[float] = []
    states: list[str] = []
    for item in inputs:
        states.append(item.state)
        if item.state == "finite":
            finite.append(item.ohms)
    if kind == "series" and "open" in states:
        return (Equivalent("open", 0.0), "an open branch breaks the series path", None)
    if kind == "parallel" and "short" in states:
        return (Equivalent("short", 0.0), "a short branch bypasses the parallel group", None)
    if len(finite) == 0:
        if kind == "series":
            return (Equivalent("short", 0.0), "all series branches are shorts", None)
        return (Equivalent("open", 0.0), "all parallel branches are open", None)
    scale: float = max(finite) if kind == "series" else min(finite)
    terms: list[float] = []
    for value in finite:
        terms.append(value / scale if kind == "series" else scale / value)
    total: float = compensated(terms)
    ohms: float = scale * total if kind == "series" else scale / total
    assert 1e-103 <= ohms <= 1e103, "equivalent resistance outside supported range"
    formula: str = "scale * sum(R / scale)" if kind == "series" else "scale / sum(scale / R)"
    return (
        Equivalent("finite", ohms),
        formula,
        {"scale_ohms": scale, "normalized_terms": terms, "normalized_sum": total},
    )


def reduce(node: Node) -> tuple[Equivalent, list[Json]]:
    steps: list[Json] = []
    inputs: list[Equivalent] = []
    children: list[Json] = []
    for child in node.children:
        reduced: tuple[Equivalent, list[Json]] = reduce(child)
        inputs.append(reduced[0])
        children.append({"id": child.name, "equivalent": measure(reduced[0])})
        steps = steps + reduced[1]
    result: Equivalent = Equivalent("open", 0.0)
    rule: str = "explicit open circuit"
    arithmetic: Json = None
    if node.kind == "short" or (node.kind == "resistor" and node.ohms == 0.0):
        result = Equivalent("short", 0.0)
        rule = "zero resistance is a short"
    elif node.kind == "resistor":
        result = Equivalent("finite", node.ohms)
        rule = "declared resistance in ohms"
    elif node.kind in ["series", "parallel"]:
        combined: tuple[Equivalent, str, Json] = combine(node.kind, inputs)
        result = combined[0]
        rule = combined[1]
        arithmetic = combined[2]
    steps.append(
        {
            "id": node.name,
            "kind": node.kind,
            "equivalent": measure(result),
            "rule": rule,
            "children": children,
            "arithmetic": arithmetic,
        }
    )
    return (result, steps)


def evaluate(rows: list[Json]) -> list[Json]:
    results: list[Json] = []
    for row in rows:
        name: str = text(row["id"])
        try:
            parsed: tuple[Node, list[str]] = parse(row["tree"], 0, [])
            solved: tuple[Equivalent, list[Json]] = reduce(parsed[0])
            results.append(
                {
                    "id": name,
                    "status": "solved",
                    "equivalent": measure(solved[0]),
                    "nodes": len(parsed[1]),
                    "steps": solved[1],
                }
            )
        except Exception as error:
            results.append({"id": name, "status": "rejected", "reason": str(error)})
    return results
