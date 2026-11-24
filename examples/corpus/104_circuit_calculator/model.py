"""Parse bounded ideal resistor trees; validate every branch before any reduction."""

# ruff: noqa: BLE001, PLR1711 - bounded numeric errors and explicit returns

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_kind,
    json_string,
    regex_fullmatch,
)


@dataclass
class Node:
    name: str
    kind: str
    ohms: float
    children: list["Node"]


def text(value: Json) -> str:
    assert json_kind(value) == "string", "expected text"
    return json_string(value)


def exact(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object", "expected object"
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def identifier(value: Json) -> str:
    name: str = text(value)
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid identifier"
    return name


def resistance(value: Json) -> float:
    spelling: str = text(value)
    assert 1 <= len(spelling) <= 64, "resistance spelling length limit"
    try:
        assert regex_fullmatch("[-+0-9_eE.]+", spelling), "expected ASCII decimal"
        number: float = float(spelling)
        nonzero: str = spelling.lower().split("e")[0].replace("_", "").strip("+-0.")
        assert number >= 0.0 and number <= 1e100, "resistance range"
        assert number == 0.0 or number >= 1e-100, "resistance range"
        assert number != 0.0 or nonzero == "", "resistance underflow"
        return 0.0 if number == 0.0 else number
    except Exception:
        assert False, "expected zero or finite resistance in 1e-100..1e100 ohms"
    return 0.0


def parse(value: Json, depth: int, seen: list[str]) -> tuple[Node, list[str]]:
    assert depth <= 16, "tree depth limit"
    assert len(seen) < 256, "tree node limit"
    assert json_kind(value) == "object" and "id" in value and "kind" in value, "expected identified node"
    name: str = identifier(value["id"])
    assert name not in seen, "duplicate node identifier"
    seen = seen + [name]
    kind: str = text(value["kind"])
    if kind == "resistor":
        exact(value, ["id", "kind", "ohms"])
        return (Node(name, kind, resistance(value["ohms"]), []), seen)
    if kind in ["open", "short"]:
        exact(value, ["id", "kind"])
        return (Node(name, kind, 0.0, []), seen)
    assert kind in ["series", "parallel"], "unknown node kind"
    exact(value, ["id", "kind", "children"])
    assert json_kind(value["children"]) == "array", "expected child array"
    branches: list[Json] = json_array(value["children"])
    assert 2 <= len(branches) <= 16, "group requires 2..16 children"
    children: list[Node] = []
    for branch in branches:
        parsed: tuple[Node, list[str]] = parse(branch, depth + 1, seen)
        children.append(parsed[0])
        seen = parsed[1]
    return (Node(name, kind, 0.0, children), seen)


def cases(document: Json) -> list[Json]:
    exact(document, ["version", "cases"])
    assert json_int(document["version"]) == 1, "unsupported version"
    assert json_kind(document["cases"]) == "array", "expected case array"
    rows: list[Json] = json_array(document["cases"])
    assert 1 <= len(rows) <= 16, "case count limit"
    seen: list[str] = []
    for row in rows:
        exact(row, ["id", "tree"])
        name: str = identifier(row["id"])
        assert name not in seen, "duplicate case identifier"
        seen.append(name)
    return rows
