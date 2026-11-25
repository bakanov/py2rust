"""Fixed follow-up workloads, with independent references outside timed execution."""

from __future__ import annotations

from collections.abc import Callable
import datetime as dt
import heapq
import json
from pathlib import Path

from corpus_checks.common import Application


def route_job(root: Path, large: bool, *, count: int | None = None) -> tuple[Callable[[Application], object], str, int]:
    """Stress ordered Bellman–Ford passes; check nonnegative paths with Dijkstra."""
    root.mkdir(parents=True)
    count = (100 if large else 12) if count is None else count
    if not 3 <= count <= 100:
        raise ValueError("route scaling requires 3..100 vertices")
    nodes = [f"node-{index:03}" for index in range(count)]
    edges = [
        {"id": f"edge-{index}", "from": nodes[index], "to": nodes[index + 1], "cost": 1 + index % 7}
        for index in reversed(range(count - 1))
    ]
    edges += [
        {"id": f"skip-{index}", "from": nodes[index], "to": nodes[index + 2], "cost": 17}
        for index in reversed(range(count - 2))
    ]
    queries = []
    for index in range(count):
        case = index % 5
        query = {"from": nodes[index % (count // 3)], "to": nodes[-1 - index % (count // 3)]}
        if case == 1:
            query["from"], query["to"] = query["to"], query["from"]
        elif case == 2:
            query["closed_nodes"] = [query["from"]]
        elif case == 3:
            query["closed_edges"] = [f"edge-{count // 2}", f"skip-{count // 2 - 1}"]
        elif case == 4:
            query["to"] = query["from"]
        queries.append(query)
    graph = {"nodes": nodes, "edges": edges, "queries": queries}
    source = root / "graph.json"
    source.write_text(json.dumps(graph, ensure_ascii=False))
    original = source.read_bytes()
    edge_by_id = {edge["id"]: edge for edge in edges}

    def verify(app: Application) -> dict:
        result = app.run(
            root,
            {
                "ROUTE_INPUT": str(source),
                "ROUTE_REPORT": str(root / "routes.json"),
                "ROUTE_TEXT": str(root / "routes.txt"),
            },
            timeout=120,
        )
        report = json.loads((root / "routes.json").read_text())
        assert json.loads(result.stdout) == report and not result.stderr, result
        assert source.read_bytes() == original
        assert report["queries"] == len(queries) and len(report["routes"]) == len(queries)
        failures = 0
        explanations = []
        for query, answer in zip(queries, report["routes"], strict=True):
            start, end = query["from"], query["to"]
            closed_nodes = set(query.get("closed_nodes", []))
            closed_edges = set(query.get("closed_edges", []))
            available = [
                edge
                for edge in edges
                if edge["id"] not in closed_edges
                and edge["from"] not in closed_nodes
                and edge["to"] not in closed_nodes
            ]
            distances = {start: 0}
            pending = [(0, start)]
            adjacency = {node: [] for node in nodes}
            for edge in available:
                adjacency[edge["from"]].append((edge["to"], edge["cost"]))
            while pending:
                distance, vertex = heapq.heappop(pending)
                if distances[vertex] != distance:
                    continue
                for target, cost in adjacency[vertex]:
                    candidate = distance + cost
                    if target not in distances or candidate < distances[target]:
                        distances[target] = candidate
                        heapq.heappush(pending, (candidate, target))
            status = (
                "closed"
                if start in closed_nodes or end in closed_nodes
                else "ok" if end in distances else "unreachable"
            )
            assert answer["status"] == status and answer["from"] == start and answer["to"] == end
            heading = f"{start} -> {end}: "
            if status == "closed":
                explanations.append(heading + "an endpoint is closed")
            elif status == "unreachable":
                assert answer["diagnosis"] == {
                    "reachable": sorted(distances),
                    "unreachable": sorted(set(nodes) - distances.keys()),
                    "reachable_count": len(distances),
                    "open_edges": len(available),
                    "reason": "destination is outside the source's reachable component",
                }
                explanations.append(heading + "no directed path remains after closures")
            else:
                assert answer["cost"] == distances[end]
                path, identifiers = answer["nodes"], answer["edges"]
                assert path[0] == start and path[-1] == end and len(path) == len(identifiers) + 1
                assert len(path) == len(set(path))
                cost = 0
                for left, right, identifier in zip(path, path[1:], identifiers):
                    edge = edge_by_id[identifier]
                    assert edge in available and (edge["from"], edge["to"]) == (left, right)
                    cost += edge["cost"]
                assert cost == answer["cost"]
                explanations.append(heading + f"cost {cost} via " + " -> ".join(path))
            failures += status != "ok"
        assert report["without_finite_route"] == failures
        assert result.returncode == int(failures > 0)
        assert (root / "routes.txt").read_text() == "\n".join(explanations) + "\n"
        return report

    return verify, f"{count} vertices, {len(edges)} reverse-ordered edges, {count} route queries", count


def terrain_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import terrain_routes

    size = 64 if large else 12
    count = 32 if large else 4
    rows = ["".join("~" if (row * 7 + column * 3) % 11 < 3 else "." for column in range(size)) for row in range(size)]
    # A wall with two gaps makes routes exercise detours and varying terrain costs.
    for row in range(size):
        if row not in {size // 4, 3 * size // 4}:
            rows[row] = rows[row][: size // 2] + "#" + rows[row][size // 2 + 1 :]
    queries = [
        terrain_routes.query(f"route-{index}", (index % size, 0), ((size - 1 - index) % size, size - 1))
        for index in range(count)
    ]
    case = terrain_routes.fixture(root, "job", "\n".join(rows) + "\n", {".": 1, "~": 7}, queries)
    return lambda app: terrain_routes.success(app, case), f"{size}×{size} weighted terrain, {count} queries", count


def cron_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import cron_explorer

    days = 3660 if large else 366
    count = 16 if large else 4
    start = dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=days)
    specs = []
    explicit = {}
    for index in range(count):
        minute, hour, date = index * 3 % 60, index % 24, 29 if index % 2 == 0 else 31
        specs.append(cron_explorer.spec(f"{minute} {hour} {date} 2 *", {minute}, {hour}, {date}, {2}))
        occurrences = []
        # Calendar construction is independent of the application's day-by-day search.
        for year in range(start.year, end.year + 1):
            try:
                candidate = dt.datetime(year, 2, date, hour, minute, tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            if start <= candidate < end:
                occurrences.append(candidate.isoformat())
        explicit[index] = occurrences
    case = cron_explorer.fixture(root, specs, start.isoformat(), days, 10)
    return (
        lambda app: cron_explorer.run(app, case, explicit),
        f"{count} sparse schedules over {days} UTC days",
        days * count,
    )


def scheduler_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import scheduler_simulator

    count = 512 if large else 32
    case = scheduler_simulator.fixture(
        root, workers=3, capacity=16, generated=scheduler_simulator.generated(88088, count)
    )
    return (
        lambda app: scheduler_simulator.run(app, case),
        f"{count} seeded jobs, three workers and 16 queue slots",
        count,
    )


def redactor_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import log_redactor

    count = 1024 if large else 32
    examples = log_redactor.examples()
    rows = [examples[index % len(examples)] for index in range(count)]
    case = log_redactor.fixture(root, rows)
    return (
        lambda app: log_redactor.run(app, case),
        f"{count} JSONL records, three nested targets and two masking rules",
        count,
    )


def patch_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import json_patch

    count = 128 if large else 8
    before = {
        "items": [{"id": i, "value": i, "tags": ["before", i % 3]} for i in range(count)],
        "keep": {"x": True},
        "remove": "old",
    }
    after = {
        "items": [{"id": i, "value": i + 1, "tags": ["after", i % 3, "new"]} for i in range(count)],
        "keep": {"x": True},
        "added/~世界": "new",
    }
    case = json_patch.fixture(root, "job", before, after)
    report, files = json_patch.expected(case)
    originals = {p.name: p.read_bytes() for p in case.work.iterdir() if p.is_file()}

    def verify(app: Application) -> dict:
        result = app.run(case.work, case.settings("write"), timeout=120)
        assert result.returncode == 0 and not result.stderr, result
        assert json.loads(result.stdout) == report
        json_patch.bundle(case, report, files)
        assert all((case.work / name).read_bytes() == data for name, data in originals.items())
        assert not list(case.work.glob(".json-patch-*"))
        return report

    return verify, f"{count} nested records, {report['changes']} guarded changes and verified undo", count


def cache_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import lru_cache

    count = 1600 if large else 64
    size = 128 if large else 8
    commands = []
    for index in range(count):
        name = f"key-{(index * 17) % (size + 16)}"
        phase = index % 10
        if phase < 5:
            commands.append(lru_cache.command("PUT", name, value={"index": index, "tags": ["世界", index % 7]}))
        elif phase < 8:
            commands.append(lru_cache.command("GET", name))
        elif phase == 8:
            commands.append(lru_cache.command("PEEK", name))
        else:
            commands.append(lru_cache.command("DELETE", name))
    commands.append(lru_cache.command("RESIZE", capacity=size // 2))
    commands.append(lru_cache.command("INSPECT"))
    case = lru_cache.fixture(root, "job", commands, capacity=size)
    return (
        lambda app: lru_cache.success(app, case),
        f"{len(commands)} mixed commands, {size} cache slots",
        len(commands),
    )


def autocomplete_job(
    root: Path, large: bool, *, size: int | None = None, count: int | None = None
) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import autocomplete

    size = (128 if large else 8) if size is None else size
    count = (1024 if large else 32) if count is None else count
    if not 1 <= size <= 128 or count < 0:
        raise ValueError("autocomplete requires 1..128 terms and a nonnegative command count")
    terms = [f"Topic-{i:03d}-世界" for i in range(size)]
    commands = [autocomplete.put(term, i % 11) for i, term in enumerate(terms)]
    for index in range(count):
        term = terms[(index * 17) % size]
        phase = index % 5
        if phase == 0:
            commands.append({"op": "HIT", "term": term.upper(), "amount": 3})
        elif phase == 1:
            commands.append(autocomplete.suggest("TOPIC-", index % 7, 8))
        elif phase == 2:
            commands.append({"op": "GET", "term": term})
        elif phase == 3:
            commands.append({"op": "DELETE", "term": term})
        else:
            commands.append(autocomplete.put(term, index % 13))
    commands.extend([{"op": "EXPORT"}, {"op": "INSPECT"}])
    case = autocomplete.fixture(root, "job", commands, capacity=size)
    return (
        lambda app: autocomplete.success(app, case),
        f"{len(commands)} mixed commands, {size} Unicode terms",
        len(commands),
    )


def converter_job(
    root: Path, large: bool, direction: str = "csv-to-json"
) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import csv_json
    import hashlib

    count = 4096 if large else 64
    columns = [
        csv_json.column("id", "integer"),
        csv_json.column("text"),
        csv_json.column("active", "boolean"),
        csv_json.column("meta", "json"),
    ]
    records = []
    raw_rows = []
    rejected = []
    accepted_rows = []
    for index in range(count):
        record = {
            "id": index,
            "text": f'世界, row {index} "quoted"\r\nnext',
            "active": index % 2 == 0,
            "meta": {"tags": [index % 7, None]},
        }
        raw = (
            [csv_json.encode(record[c["name"]], c["type"]) for c in columns]
            if direction == "csv-to-json"
            else dict(record)
        )
        if index % 17 == 0:
            if direction == "csv-to-json":
                raw[0] = "invalid"
            else:
                raw["id"] = "invalid"
            rejected.append(
                {"row": index + 1, "input": raw, "errors": [{"column": "id", "reason": "invalid integer value"}]}
            )
        else:
            records.append(record)
            accepted_rows.append(index + 1)
        raw_rows.append(raw)
    source = (
        csv_json.csv_text([[c["name"] for c in columns], *raw_rows]).encode()
        if direction == "csv-to-json"
        else json.dumps(raw_rows, ensure_ascii=False).encode()
    )
    case = csv_json.fixture(root, "job", direction, columns, source, select=["meta", "text", "id"])
    data = csv_json.expected_data(case, records)
    filename = "data.json" if direction == "csv-to-json" else "data.csv"
    expected = {
        "direction": direction,
        "columns": case.config["select"],
        "rows": count,
        "accepted": len(records),
        "rejected": len(rejected),
        "accepted_rows": accepted_rows,
        "errors": rejected,
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "data_sha256": hashlib.sha256(data).hexdigest(),
        "data_file": filename,
    }
    original_config = case.settings_path.read_bytes()

    def verify(app: Application) -> dict:
        result = app.run(case.work, case.settings(), timeout=120)
        assert result.returncode == 1 and not result.stderr, result
        assert json.loads(result.stdout) == expected
        assert {p.name for p in case.output.iterdir()} == {filename, "report.json"}
        assert (case.output / filename).read_bytes() == data
        assert json.loads((case.output / "report.json").read_bytes()) == expected
        assert case.input.read_bytes() == source and case.settings_path.read_bytes() == original_config
        assert not list(case.work.glob(".csv-json-*"))
        return expected

    return verify, f"{direction}: {count} typed rows with quoted Unicode fields and rejected records", count


def join_job(root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    from corpus_checks import csv_join

    count = 1024 if large else 32
    header = ["key", "group", "value"]
    left = [header, *[[str(i % (count // 2)), str(i % 3), f'left 世界 {i},"quoted"'] for i in range(count)]]
    right = [header, *[[str(i % (count // 2) + count // 8), str(i % 3), f"right {i}\r\nnext"] for i in range(count)]]
    case = csv_join.fixture(
        root,
        "job",
        left,
        right,
        order="key",
        left={"path": "left.csv", "keys": ["key", "group"], "delimiter": ","},
        right={"path": "right.csv", "keys": ["key", "group"], "delimiter": ";"},
    )
    expected = csv_join.oracle(case)
    before = {p.name: p.read_bytes() for p in case.work.iterdir() if p.is_file()}

    def verify(app: Application) -> dict:
        result = app.run(case.work, case.settings(), timeout=120)
        assert result.returncode == 0 and not result.stderr, result
        assert json.loads(result.stdout) == expected[1]
        csv_join.bundle(case, expected)
        assert all((case.work / name).read_bytes() == data for name, data in before.items())
        assert not list(case.work.glob(".csv-join-*"))
        return expected[1]

    return verify, f"{count} rows per table, composite keys, stable key order and unmatched rows", count


def job(identifier: str, root: Path, large: bool) -> tuple[Callable[[Application], object], str, int]:
    if identifier == "044":
        return join_job(root, large)
    if identifier == "041":
        return converter_job(root, large)
    if identifier == "055":
        return autocomplete_job(root, large)
    if identifier == "051":
        return cache_job(root, large)
    if identifier == "045":
        return patch_job(root, large)
    if identifier == "061":
        return route_job(root, large)
    if identifier == "065":
        return terrain_job(root, large)
    if identifier == "082":
        return cron_job(root, large)
    if identifier == "088":
        return scheduler_job(root, large)
    if identifier == "089":
        return redactor_job(root, large)
    raise ValueError(f"No follow-up performance workload yet for {identifier}")
