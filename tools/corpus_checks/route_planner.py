"""Exhaustive simple paths plus independent reachability/cycle diagnostics."""

import itertools
import json
import random
from pathlib import Path

from .common import Application


def oracle(graph: dict, query: dict) -> tuple[str, int | None]:
    start, end = query["from"], query["to"]
    closed = set(query.get("closed_nodes", []))
    if start in closed or end in closed:
        return "closed", None
    edges = [
        edge
        for edge in graph["edges"]
        if edge["id"] not in query.get("closed_edges", []) and edge["from"] not in closed and edge["to"] not in closed
    ]
    nodes = [node for node in graph["nodes"] if node not in closed]
    reach = {(node, node) for node in nodes} | {(edge["from"], edge["to"]) for edge in edges}
    for mid in nodes:
        for left in nodes:
            for right in nodes:
                if (left, mid) in reach and (mid, right) in reach:
                    reach.add((left, right))

    # Enumerate simple directed cycles; parallel edges remain distinct choices.
    def cycles(current: str, origin: str, visited: set, cost: int) -> bool:
        for edge in edges:
            if edge["from"] == current:
                target = edge["to"]
                following = cost + edge["cost"]
                if target == origin and following < 0:
                    return True
                if target not in visited and cycles(target, origin, visited | {target}, following):
                    return True
        return False

    for node in nodes:
        if (start, node) in reach and (node, end) in reach and cycles(node, node, {node}, 0):
            return "negative_cycle", None
    best = None

    def paths(current: str, seen: set, cost: int) -> None:
        nonlocal best
        if current == end:
            best = cost if best is None else min(best, cost)
        for edge in edges:
            if edge["from"] == current and edge["to"] not in seen:
                paths(edge["to"], seen | {edge["to"]}, cost + edge["cost"])
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    paths(start, {start}, 0)
    return ("unreachable", None) if best is None else ("ok", best)


def check(app: Application, directory: Path) -> dict:
    rng = random.Random(61001)
    graphs = []
    for index in range(9):
        nodes = ["A", "B", "C", "世界"]
        edges = []
        for left, right in itertools.product(nodes, repeat=2):
            if rng.random() < 0.33:
                edges.append({"id": str(len(edges)), "from": left, "to": right, "cost": rng.randint(-3, 7)})
        queries = [{"from": left, "to": right} for left, right in itertools.product(nodes, repeat=2)]
        queries += [dict(query, closed_nodes=["B"]) for query in queries[:4]]
        if edges:
            queries += [dict(query, closed_edges=[edges[0]["id"]]) for query in queries[:4]]
        graphs.append({"nodes": nodes, "edges": edges, "queries": queries})
    graphs.append(
        {
            "nodes": ["A", "B", "C", "D", "E"],
            "edges": [
                {"id": "ab", "from": "A", "to": "B", "cost": 2},
                {"id": "bc", "from": "B", "to": "C", "cost": -2},
                {"id": "cb", "from": "C", "to": "B", "cost": 1},
                {"id": "ad", "from": "A", "to": "D", "cost": 4},
                {"id": "de", "from": "D", "to": "E", "cost": 1},
                {"id": "ad-better", "from": "A", "to": "D", "cost": 3},
            ],
            "queries": [{"from": "A", "to": "E"}, {"from": "A", "to": "C"}, {"from": "E", "to": "C"}],
        }
    )
    totals = {"ok": 0, "closed": 0, "unreachable": 0, "negative_cycle": 0}
    for index, graph in enumerate(graphs):
        source = directory / f"graph-{index}.json"
        source.write_text(json.dumps(graph))
        target = directory / "routes.json"
        settings = {
            "ROUTE_INPUT": str(source),
            "ROUTE_REPORT": str(target),
            "ROUTE_TEXT": str(directory / "routes.txt"),
        }
        result = app.run(directory, settings)
        report = json.loads(target.read_text())
        assert json.loads(result.stdout) == report, result.stderr
        expected_failure = False
        edge_map = {edge["id"]: edge for edge in graph["edges"]}
        for query, answer in zip(graph["queries"], report["routes"], strict=True):
            status, cost = oracle(graph, query)
            assert answer["status"] == status, (graph, query, answer, (status, cost))
            totals[status] += 1
            expected_failure |= status != "ok"
            if status == "unreachable":
                reachable = {query["from"]}
                available = [
                    edge
                    for edge in graph["edges"]
                    if edge["id"] not in query.get("closed_edges", [])
                    and edge["from"] not in query.get("closed_nodes", [])
                    and edge["to"] not in query.get("closed_nodes", [])
                ]
                for _ in graph["nodes"]:
                    reachable |= {edge["to"] for edge in available if edge["from"] in reachable}
                assert answer["diagnosis"]["reachable"] == sorted(reachable)
                assert answer["diagnosis"]["unreachable"] == sorted(set(graph["nodes"]) - reachable)
            if status in {"ok", "negative_cycle"}:
                witness = answer if status == "ok" else answer["cycle"]
                assert len(witness["nodes"]) == len(witness["edges"]) + 1
                total = 0
                for left, right, identifier in zip(witness["nodes"], witness["nodes"][1:], witness["edges"]):
                    edge = edge_map[identifier]
                    assert (edge["from"], edge["to"]) == (left, right)
                    assert identifier not in query.get("closed_edges", [])
                    assert left not in query.get("closed_nodes", []) and right not in query.get("closed_nodes", [])
                    total += edge["cost"]
                assert total == witness["cost"]
                if status == "ok":
                    assert (
                        total == cost and witness["nodes"][0] == query["from"] and witness["nodes"][-1] == query["to"]
                    )
                else:
                    assert total < 0 and witness["nodes"][0] == witness["nodes"][-1]
        assert result.returncode == int(expected_failure)
        assert len((directory / "routes.txt").read_text().splitlines()) == len(graph["queries"])
    bad = dict(graphs[0], nodes=["A", "A"])
    source.write_text(json.dumps(bad))
    before = target.read_bytes()
    assert app.run(directory, settings).returncode != 0
    assert target.read_bytes() == before
    assert all(count > 0 for count in totals.values())
    return {
        "graphs": len(graphs),
        "independent_oracle_results": totals,
        "witnesses_validated": True,
        "invalid_graph_preserves_report": True,
    }
