"""Exact-rational ideal-circuit oracle, independent of application parsing and floating reduction."""

from __future__ import annotations

import hashlib
import json
import math
import random
from fractions import Fraction
from typing import Any


def canonical(value: Any) -> bytes:
    def encode(item: Any) -> str:
        if type(item) is float:
            mantissa, exponent = format(item, ".16e").split("e")
            return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
        if isinstance(item, dict):
            return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        if isinstance(item, list):
            return "[" + ",".join(encode(child) for child in item) + "]"
        return json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    return (encode(value) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def resistor(value: str | int) -> dict:
    return {"kind": "resistor", "ohms": str(value)}


def group(kind: str, *children: dict) -> dict:
    return {"kind": kind, "children": list(children)}


def case(name: str, tree: dict) -> dict:
    # Inputs are JSON trees, so repeated fixture dictionaries represent distinct nodes.
    tree = json.loads(json.dumps(tree))
    pending = [tree]
    index = 0
    while pending:
        node = pending.pop()
        node["id"] = "n" + str(index)
        index += 1
        pending.extend(reversed(node.get("children", [])))
    return {"id": name, "tree": tree}


def fixtures() -> list[dict]:
    return [
        case(name, tree)
        for name, tree in [
            ("single", resistor(100)),
            ("zero", resistor("-0.0")),
            ("wire", {"kind": "short"}),
            ("broken", {"kind": "open"}),
            ("series", group("series", resistor(100), resistor(220), resistor(330))),
            ("parallel", group("parallel", resistor(100), resistor(300))),
            (
                "nested",
                group(
                    "series", group("parallel", group("series", resistor(10), resistor(20)), resistor(60)), resistor(5)
                ),
            ),
            ("open_series", group("series", {"kind": "open"}, resistor(10))),
            ("open_parallel", group("parallel", {"kind": "open"}, resistor(120))),
            ("short_series", group("series", resistor(0), resistor(500))),
            ("short_parallel", group("parallel", {"kind": "short"}, {"kind": "open"}, resistor(100))),
            ("all_short", group("series", {"kind": "short"}, resistor(0))),
            ("all_open", group("parallel", {"kind": "open"}, {"kind": "open"})),
            ("tiny_parallel", group("parallel", resistor("1e-100"), resistor("1e100"))),
            ("large_series", group("series", resistor("1e-100"), resistor("1e100"))),
            ("decimal", group("parallel", resistor("+1_000.0"), resistor("1e3"))),
        ]
    ]


def generated(rng: random.Random, depth: int = 0) -> dict:
    if depth == 4 or rng.random() < 0.5:
        choice = rng.randrange(12)
        if choice == 0:
            return {"kind": "open"}
        if choice == 1:
            return {"kind": "short"}
        return resistor(str(rng.randrange(1, 10000)) + "e" + str(rng.randrange(-95, 96)))
    return group(rng.choice(["series", "parallel"]), *(generated(rng, depth + 1) for _ in range(rng.randrange(2, 5))))


def truth(tree: dict) -> tuple[Fraction | None, list[tuple[dict, Fraction | None]]]:
    kind = tree["kind"]
    reductions = [truth(child) for child in tree.get("children", [])]
    values = [row[0] for row in reductions]
    if kind == "open":
        value = None
    elif kind == "short":
        value = Fraction(0)
    elif kind == "resistor":
        value = Fraction(tree["ohms"].replace("_", ""))
    elif kind == "series":
        value = None if None in values else sum(values, Fraction(0))
    else:
        assert kind == "parallel"
        conductance = sum((1 / row for row in values if row), Fraction(0))
        value = Fraction(0) if Fraction(0) in values else (1 / conductance if conductance else None)
    return value, [row for reduction in reductions for row in reduction[1]] + [(tree, value)]


def close(actual: Any, expected: Fraction | float) -> None:
    assert type(actual) is float and math.isfinite(actual), actual
    number = float(expected)
    if number == 0:
        assert actual == 0 and math.copysign(1, actual) == 1
    else:
        assert abs(actual - number) <= abs(number) * 2e-13, (actual, number)
    return  # noqa: PLR1711


def inspect_measure(actual: dict, expected: Fraction | None) -> None:
    state = "open" if expected is None else "short" if expected == 0 else "finite"
    assert actual.keys() == {"state", "ohms"} and actual["state"] == state
    if expected is None:
        assert actual["ohms"] is None
    else:
        close(actual["ohms"], expected)
    return  # noqa: PLR1711


def inspect_result(row: dict, result: dict) -> int:
    value, nodes = truth(row["tree"])
    assert result.keys() == {"id", "status", "equivalent", "nodes", "steps"}
    assert result["id"] == row["id"] and result["status"] == "solved"
    assert type(result["nodes"]) is int and result["nodes"] == len(nodes) == len(result["steps"])
    inspect_measure(result["equivalent"], value)
    known = {}
    for (node, expected), step in zip(nodes, result["steps"]):
        assert step.keys() == {"id", "kind", "equivalent", "rule", "children", "arithmetic"}
        assert step["id"] == node["id"] and step["kind"] == node["kind"]
        inspect_measure(step["equivalent"], expected)
        kind = node["kind"]
        children = [{"id": child["id"], "equivalent": known[child["id"]]} for child in node.get("children", [])]
        assert canonical(step["children"]) == canonical(children)
        measures = [child["equivalent"] for child in children]
        finite = [item["ohms"] for item in measures if item["state"] == "finite"]
        if kind in ["series", "parallel"] and expected not in [None, 0]:
            rule = "scale * sum(R / scale)" if kind == "series" else "scale / sum(scale / R)"
            arithmetic = step["arithmetic"]
            assert arithmetic.keys() == {"scale_ohms", "normalized_terms", "normalized_sum"}
            scale = max(finite) if kind == "series" else min(finite)
            assert type(arithmetic["scale_ohms"]) is float and arithmetic["scale_ohms"].hex() == scale.hex()
            terms = [item / scale if kind == "series" else scale / item for item in finite]
            assert canonical(terms) == canonical(arithmetic["normalized_terms"])
            close(arithmetic["normalized_sum"], math.fsum(terms))
            calculated = (
                scale * arithmetic["normalized_sum"] if kind == "series" else scale / arithmetic["normalized_sum"]
            )
            assert step["equivalent"]["ohms"].hex() == calculated.hex()
        else:
            assert step["arithmetic"] is None
            if kind == "open":
                rule = "explicit open circuit"
            elif kind in ["short", "resistor"]:
                rule = "zero resistance is a short" if expected == 0 else "declared resistance in ohms"
            elif kind == "series":
                rule = "an open branch breaks the series path" if expected is None else "all series branches are shorts"
            else:
                rule = (
                    "a short branch bypasses the parallel group" if expected == 0 else "all parallel branches are open"
                )
        assert step["rule"] == rule
        known[node["id"]] = step["equivalent"]
    assert canonical(result["equivalent"]) == canonical(result["steps"][-1]["equivalent"])
    return len(nodes)
