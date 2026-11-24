"""Bellman-Ford/Dijkstra references, path/statistics audits and ASCII bundle checks."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import hashlib
import heapq
import itertools
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical

LEGEND = "S=start G=goal @=start-and-goal *=path X=blocked-endpoint #=wall\n"


def query(identifier: str, start: tuple[int, int], goal: tuple[int, int]) -> dict:
    return {"id": identifier, "start": list(start), "goal": list(goal)}


def sample() -> str:
    return ".........\n.###~###.\n...#~#...\n.~...~...\n.#######.\n.........\n#########\n...#.....\n"


def jobs() -> list:
    return [
        query("across", (0, 0), (0, 8)),
        query("weighted", (2, 0), (2, 8)),
        query("unreachable", (0, 0), (7, 0)),
        query("blocked", (1, 1), (0, 0)),
        query("same", (3, 4), (3, 4)),
    ]


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "terrain-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "TERRAIN_CONFIG": str(self.path),
            "TERRAIN_MODE": mode,
            "TERRAIN_FAIL": "",
            "TERRAIN_PAUSE": "",
            "TERRAIN_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, grid: str | bytes, costs: dict, requests: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(
        work,
        {
            "grid": "grid.txt",
            "terrain": "terrain.json",
            "requests": "requests.json",
            "output": "terrain-routes",
            **changes,
        },
    )
    (work / "grid.txt").write_bytes(grid.encode() if isinstance(grid, str) else grid)
    (work / "terrain.json").write_text(json.dumps({"version": 1, "costs": costs}, ensure_ascii=False))
    (work / "requests.json").write_text(json.dumps(requests, ensure_ascii=False))
    fix.save()
    return fix


def inputs(fix: Fixture) -> tuple[list[str], dict, list]:
    raw = (fix.work / fix.config["grid"]).read_bytes().decode().replace("\r\n", "\n")
    rows = raw.removesuffix("\n").split("\n")
    costs = json.loads((fix.work / fix.config["terrain"]).read_bytes())["costs"]
    requests = json.loads((fix.work / fix.config["requests"]).read_bytes())
    return rows, costs, requests


def adjacency(rows: list[str], costs: dict) -> dict:
    graph = {}
    for row, line in enumerate(rows):
        for column, symbol in enumerate(line):
            if symbol == "#":
                continue
            graph[row, column] = {}
            for y, x in [(row, column + 1), (row + 1, column), (row, column - 1), (row - 1, column)]:
                if 0 <= y < len(rows) and 0 <= x < len(line) and rows[y][x] != "#":
                    graph[row, column][y, x] = costs[rows[y][x]]
    return graph


def shortest(graph: dict, start: tuple, goal: tuple) -> tuple[int | None, int]:
    distances = {start: 0}
    if len(graph) <= 6:
        # Tiny exhaustive grid families use relaxation, independently of any priority queue.
        for _ in range(max(0, len(graph) - 1)):
            before = distances.copy()
            for source, destinations in graph.items():
                if source not in before:
                    continue
                for target, cost in destinations.items():
                    candidate = before[source] + cost
                    if target not in distances or candidate < distances[target]:
                        distances[target] = candidate
            if distances == before:
                break
    else:
        # Larger grids use ordinary Dijkstra without the application's A* heuristic or tie rules.
        queue = [(0, start)]
        while queue:
            distance, source = heapq.heappop(queue)
            if distance != distances[source]:
                continue
            for target, cost in graph[source].items():
                candidate = distance + cost
                if target not in distances or candidate < distances[target]:
                    distances[target] = candidate
                    heapq.heappush(queue, (candidate, target))
    return distances.get(goal), len(distances)


def validate(fix: Fixture, report: dict) -> None:
    rows, costs, requests = inputs(fix)
    graph = adjacency(rows, costs)
    metadata = {
        "width": len(rows[0]),
        "height": len(rows),
        "passable": len(graph),
        "minimum_cost": min((costs[rows[y][x]] for y, x in graph), default=0),
    }
    hashes = {
        name: hashlib.sha256(raw).hexdigest()
        for name, raw in {
            "grid.txt": ("\n".join(rows) + "\n").encode(),
            "terrain.json": (canonical({"version": 1, "costs": costs}) + "\n").encode(),
            "requests.json": (canonical(requests) + "\n").encode(),
        }.items()
    }
    assert set(report) == {"version", "grid", "input_sha256", "queries", "counts", "routes"}
    assert report["version"] == 1 and report["grid"] == metadata and report["input_sha256"] == hashes
    assert report["queries"] == len(requests) == len(report["routes"])
    counts = {"found": 0, "unreachable": 0, "blocked": 0}
    fields = {"pushed", "popped", "expanded", "stale", "discovered", "frontier_peak", "frontier_remaining"}
    for request, result in zip(requests, report["routes"], strict=True):
        assert set(result) == {"id", "start", "goal", "status", "blocked", "cost", "steps", "path", "stats"}
        assert {key: result[key] for key in request} == request
        start, goal = tuple(request["start"]), tuple(request["goal"])
        blocked = [label for label, point in [("start", start), ("goal", goal)] if point not in graph]
        assert result["blocked"] == blocked
        statistics = result["stats"]
        assert set(statistics) == fields and all(type(n) is int and n >= 0 for n in statistics.values())
        if blocked:
            assert (
                result["status"] == "blocked"
                and result["cost"] is None
                and result["path"] == []
                and result["steps"] == 0
            )
            assert all(n == 0 for n in statistics.values())
        else:
            cost, reachable = shortest(graph, start, goal)
            assert result["cost"] == cost and result["status"] == ("found" if cost is not None else "unreachable")
            assert 1 <= statistics["expanded"] <= statistics["discovered"] <= len(graph)
            assert statistics["discovered"] <= statistics["pushed"] <= 1 + 4 * statistics["expanded"]
            assert statistics["popped"] == statistics["expanded"] + statistics["stale"]
            assert statistics["pushed"] - statistics["popped"] == statistics["frontier_remaining"]
            assert 1 <= statistics["frontier_peak"] <= statistics["pushed"]
            assert statistics["frontier_remaining"] <= statistics["frontier_peak"]
            if cost is None:
                assert result["path"] == [] and result["steps"] == 0
                assert statistics["expanded"] == statistics["discovered"] == reachable
                assert statistics["frontier_remaining"] == 0
            else:
                path = [tuple(point) for point in result["path"]]
                assert path[0] == start and path[-1] == goal and len(path) == len(set(path))
                assert all(len(point) == 2 and all(type(n) is int for n in point) for point in path)
                assert set(path) <= set(graph) and result["steps"] == len(path) - 1
                assert all(second in graph[first] for first, second in itertools.pairwise(path))
                assert sum(graph[first][second] for first, second in itertools.pairwise(path)) == cost
                assert len(path) <= statistics["expanded"]
                if start == goal:
                    assert statistics == {
                        "pushed": 1,
                        "popped": 1,
                        "expanded": 1,
                        "stale": 0,
                        "discovered": 1,
                        "frontier_peak": 1,
                        "frontier_remaining": 0,
                    }
        counts[result["status"]] += 1
    assert report["counts"] == counts
    return


def picture(rows: list[str], result: dict) -> str:
    marked = {tuple(point) for point in result["path"]}
    start, goal = tuple(result["start"]), tuple(result["goal"])
    lines = ["Route " + canonical(result["id"]) + ": " + result["status"] + " cost=" + canonical(result["cost"])]
    for y, row in enumerate(rows):
        line = []
        for x, symbol in enumerate(row):
            position = (y, x)
            paint = "*" if position in marked else symbol
            if position in [start, goal]:
                paint = "X" if symbol == "#" else "@" if start == goal else "S" if position == start else "G"
            line.append(paint)
        lines.append("".join(line))
    return "\n".join(lines) + "\n"


def outputs(fix: Fixture, report: dict) -> dict:
    rows, costs, requests = inputs(fix)
    expected = {
        "grid.txt": ("\n".join(rows) + "\n").encode(),
        "terrain.json": (canonical({"version": 1, "costs": costs}) + "\n").encode(),
        "requests.json": (canonical(requests) + "\n").encode(),
        "routes.json": (canonical(report) + "\n").encode(),
        "paths.jsonl": "".join(canonical(row) + "\n" for row in report["routes"]).encode(),
        "routes.txt": "\n".join([LEGEND, *[picture(rows, row) for row in report["routes"]]]).encode(),
    }
    manifest = {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in expected.items()
        },
    }
    expected["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert actual == expected
    return actual


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    paths = [fix.path] + [fix.work / fix.config[key] for key in ["grid", "terrain", "requests"]]
    original = [path.read_bytes() for path in paths]
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    validate(fix, report)
    assert result.returncode == int(report["counts"]["blocked"] + report["counts"]["unreachable"] > 0)
    assert result.stdout == canonical(report) + "\n"
    assert original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".terrain-routes-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=30)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".terrain-routes-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    observations = []
    exhaustive = 0
    queries = 0
    for symbols in itertools.product("#.~", repeat=4):
        grid = "".join(symbols[:2]) + "\n" + "".join(symbols[2:]) + "\n"
        points = list(itertools.product(range(2), repeat=2))
        requests = [query(str(i), a, b) for i, (a, b) in enumerate(itertools.product(points, repeat=2))]
        for costs in [{".": 1, "~": 5}, {".": 0, "~": 2}]:
            fix = fixture(directory, "exhaustive-" + str(exhaustive), grid, costs, requests)
            observations.append(success(app, fix))
            exhaustive += 1
            queries += len(requests)
    for symbols in itertools.product("#.", repeat=6):
        grid = "".join(symbols[:3]) + "\n" + "".join(symbols[3:]) + "\n"
        points = list(itertools.product(range(2), range(3)))
        requests = [query(str(i), a, b) for i, (a, b) in enumerate(itertools.product(points, repeat=2))]
        fix = fixture(directory, "exhaustive-" + str(exhaustive), grid, {".": 1}, requests)
        observations.append(success(app, fix))
        exhaustive += 1
        queries += len(requests)
    print(app.engine + " terrain routes: exhaustive small-grid costs and reachability passed", flush=True)
    cases = [
        (sample(), {".": 1, "~": 5}, jobs()),
        (".\n", {".": 0}, []),
        ("##\n##\n", {}, [query("walls", (0, 0), (1, 1))]),
        (" .\n..\n", {" ": 3, ".": 1}, [query("space", (1, 1), (0, 0))]),
        (".~.\n...\n", {".": 1, "~": 50}, [query("detour", (0, 0), (0, 2))]),
        ("~.\n", {".": 1, "~": 100}, [query("excluded start", (0, 0), (0, 1))]),
        ("....\n....\n....\n....\n", {".": 2}, [query("stats", (0, 0), (0, 3))]),
        ("..\n", {".": 1}, [query('id\nwith"escapes', (0, 0), (0, 1))]),
    ]
    randomizer = random.Random(65065)
    for index in range(40):
        height, width = randomizer.randint(2, 12), randomizer.randint(2, 12)
        grid = (
            "\n".join("".join(randomizer.choices("#.~+", weights=[2, 5, 2, 1], k=width)) for _ in range(height)) + "\n"
        )
        costs = {".": index % 2, "~": 3, "+": 11}
        requests = [
            query(
                str(i),
                (randomizer.randrange(height), randomizer.randrange(width)),
                (randomizer.randrange(height), randomizer.randrange(width)),
            )
            for i in range(8)
        ]
        cases.append((grid, costs, requests))
    # The isolated goal makes the search drain improved, now-stale heap entries too.
    for index in range(12):
        rows = [list("".join(randomizer.choices("123456789", k=8))) for _ in range(8)]
        rows[6][7] = rows[7][6] = "#"
        cases.append(
            (
                "\n".join("".join(row) for row in rows) + "\n",
                {str(n): n for n in range(1, 10)},
                [query("drain", (0, 0), (7, 7))],
            )
        )
    maximum_stale = 0
    for index, (grid, costs, requests) in enumerate(cases):
        fix = fixture(directory, "case-" + str(index), grid, costs, requests)
        report = success(app, fix)
        maximum_stale = max(maximum_stale, max((r["stats"]["stale"] for r in report["routes"]), default=0))
        if index == 4:
            assert report["routes"][0]["cost"] == report["routes"][0]["steps"] == 4
        if index == 5:
            assert report["routes"][0]["cost"] == 1
        if index == 6:
            assert report["routes"][0]["stats"] == {
                "pushed": 7,
                "popped": 4,
                "expanded": 4,
                "stale": 0,
                "discovered": 7,
                "frontier_peak": 4,
                "frontier_remaining": 3,
            }
        variant = grid.removesuffix("\n") if index % 2 else grid.replace("\n", "\r\n")
        other = fixture(directory, "permuted-" + str(index), variant, dict(reversed(list(costs.items()))), requests)
        assert success(app, other) == report
        assert outputs(other, report) == outputs(fix, report)
        observations.append(report)
    assert maximum_stale > 0
    fix = fixture(directory, "unused-zero", "....\n....\n....\n....\n", {".": 2, "~": 0}, cases[6][2])
    report = success(app, fix)
    assert report["grid"]["minimum_cost"] == 2 and report["routes"] == observations[exhaustive + 6]["routes"]
    return {
        "exhaustive_grids": exhaustive,
        "exhaustive_queries": queries,
        "other_grids": len(cases),
        "generated_grids": 52,
        "normalized_permutations": len(cases),
        "maximum_stale_entries": maximum_stale,
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = {"version": 1, "costs": {".": 1}}
    terrains = [None, [], {}, True, {**base, "extra": 0}, {"version": 1}, {"costs": {".": 1}}]
    terrains += [{**base, "version": value} for value in [0, 2, True, 1.0, "1", None]]
    terrains += [{**base, "costs": value} for value in [None, [], 1, True, ""]]
    terrains += [
        {**base, "costs": {symbol: 1}}
        for symbol in ["", "..", "#", "S", "G", "*", "@", "X", "\t", "\n", "\r", "\x00", "é", "🙂", "\x7f"]
    ]
    terrains += [{**base, "costs": {".": value}} for value in [-1, 10**9 + 1, True, 1.0, "1", None, [], {}]]
    for index, value in enumerate(terrains):
        fix = fixture(directory, "terrain-" + str(index), ".\n", {".": 1}, [])
        (fix.work / "terrain.json").write_text(json.dumps(value, ensure_ascii=False))
        failure(app, fix)
    grids = [
        "",
        "\n",
        "..\n.\n",
        ".\n\n",
        ".\r.\n",
        "." * 65,
        ".\n" * 65,
        "?\n",
        "\t\n",
        "é\n",
        "\ufeff.\n",
        ".\x00\n",
        b"\xff",
    ]
    for index, value in enumerate(grids):
        failure(app, fixture(directory, "grid-" + str(index), value, {".": 1}, []))
    row = query("q", (0, 0), (0, 0))
    requests = [None, {}, True, "", [None], [[]], [{}], [{**row, "extra": 1}], [row, row]]
    requests += [[{key: value for key, value in row.items() if key != missing}] for missing in row]
    requests += [[{**row, "id": value}] for value in ["", "a\x00", "x" * 65, "🙂" * 65, None, True, 1, [], {}]]
    for name in ["start", "goal"]:
        requests += [
            [{**row, name: value}]
            for value in [
                None,
                {},
                "0,0",
                True,
                [],
                [0],
                [0, 0, 0],
                [True, 0],
                [0, False],
                [0.0, 0],
                [0, 0.0],
                [None, 0],
                [0, "0"],
                [-1, 0],
                [0, -1],
                [1, 0],
                [0, 1],
            ]
        ]
    for index, value in enumerate(requests):
        failure(app, fixture(directory, "request-" + str(index), ".\n", {".": 1}, value))
    count = len(terrains) + len(grids) + len(requests)
    for key in ["grid", "terrain", "requests", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", ".\n", {".": 1}, [])
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
        fix = fixture(directory, "missing-" + key, ".\n", {".": 1}, [])
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", ".\n", {".": 1}, [])
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", ".\n", {".": 1}, []), "invalid terrain mode", TERRAIN_MODE="bad")
    count += 2
    for name in ["terrain.json", "requests.json", "terrain-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", ".\n", {".": 1}, [])
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    fix = fixture(
        directory, "largest-grid", ("." * 64 + "\r\n") * 64, {".": 10**9}, [query("🙂" * 64, (0, 0), (63, 63))]
    )
    report = success(app, fix)
    assert report["routes"][0]["cost"] == 126 * 10**9 and report["grid"]["passable"] == 4096
    rows = []
    for y in range(64):
        if y % 2 == 0:
            rows.append("." * 64)
        elif y == 63:
            rows.append("#" * 64)
        else:
            connector = 63 if (y // 2) % 2 == 0 else 0
            rows.append("#" * connector + "." + "#" * (63 - connector))
    requests = [query(str(i), (0, 0), (62, 0)) for i in range(64)]
    fix = fixture(directory, "long-maze", "\n".join(rows) + "\n", {".": 10**9}, requests)
    report = success(app, fix)
    assert all(r["cost"] == 2078 * 10**9 and r["steps"] == 2078 for r in report["routes"])
    failure(
        app,
        fixture(directory, "queries-above", ".\n", {".": 1}, [query(str(i), (0, 0), (0, 0)) for i in range(65)]),
        "query count",
    )
    symbols = "abcdefghijklmnop"
    success(
        app,
        fixture(
            directory,
            "terrain-exact",
            symbols + "\n",
            {s: i for i, s in enumerate(symbols)},
            [query("all", (0, 0), (0, 15))],
        ),
    )
    failure(app, fixture(directory, "terrain-above", ".\n", {s: 1 for s in symbols + "."}, []), "terrain count")
    failure(app, fixture(directory, "grid-bytes-above", b"." * 8193, {".": 1}, []), "byte limit")
    for name, maximum in [("terrain-job.json", 65536), ("terrain.json", 65536), ("requests.json", 1048576)]:
        fix = fixture(directory, "bytes-" + name, sample(), {".": 1, "~": 5}, jobs())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "width": 64,
        "height": 64,
        "cells": 4096,
        "queries": 64,
        "terrain_types": 16,
        "id_characters": 64,
        "id_bytes": 256,
        "maximum_cell_cost": 10**9,
        "long_path_steps": 2078,
        "long_path_cost": 2078 * 10**9,
        "config_bytes": 65536,
        "grid_byte_limit": 8192,
        "terrain_bytes": 65536,
        "requests_bytes": 1048576,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(TERRAIN_PAUSE="ready", TERRAIN_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    points = [
        "validated",
        "stage",
        "grid.txt",
        "terrain.json",
        "requests.json",
        "routes.json",
        "paths.jsonl",
        "routes.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample(), {".": 1, "~": 5}, jobs())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(TERRAIN_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".terrain-routes-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["grid", "terrain", "requests", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), {".": 1, "~": 5}, jobs())
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = fix.path if name == "config" else fix.work / fix.config[name]
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output
            assert not list(fix.work.glob(".terrain-routes-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample(), {".": 1, "~": 5}, jobs())
    reference = success(app, fix, "preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".terrain-routes-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 6


def paths(app: Application, directory: Path) -> int:
    names = ["grid.txt", "terrain.json", "requests.json", "terrain-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample(), {".": 1, "~": 5}, jobs())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("grid.txt" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
        fix = fixture(directory, "symlink-" + name, sample(), {".": 1, "~": 5}, jobs())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", sample(), {".": 1, "~": 5}, jobs())
    parent = fix.work / "readonly"
    parent.mkdir()
    fix.config["output"] = "readonly/result"
    fix.save()
    parent.chmod(0o500)
    try:
        failure(app, fix)
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)
    return 13


def check(app: Application, directory: Path) -> dict:
    cases = scenarios(app, directory / "scenarios")
    print(app.engine + " terrain routes: independent costs, paths, statistics and normalization passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " terrain routes: validation, limits, publication and path checks passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
