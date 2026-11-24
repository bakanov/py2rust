"""Independent reachability/longest-path oracle and complete-project publication checks."""

# ruff: noqa: PLR1711 - explicit repository returns

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import random
import selectors
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from .common import Application
from .csv_json import canonical


def graph(names: list[str], edges: list[tuple[str, str]]) -> dict:
    return {
        "version": 1,
        "targets": [{"name": name, "command": ["builder", "--target", name]} for name in names],
        "edges": [{"target": target, "requires": prerequisite} for target, prerequisite in edges],
    }


def request(identifier: str, names: list[str]) -> dict:
    return {"id": identifier, "targets": names}


def sample() -> dict:
    return graph(
        ["package", "app", "left", "right", "generate", "docs", "cycle-a", "cycle-b", "blocked"],
        [
            ("package", "app"),
            ("app", "left"),
            ("app", "right"),
            ("left", "generate"),
            ("right", "generate"),
            ("cycle-a", "cycle-b"),
            ("cycle-b", "cycle-a"),
            ("blocked", "cycle-a"),
        ],
    )


def jobs() -> list:
    return [request("release", ["package", "docs"]), request("bad", ["blocked", "docs"]), request("empty", [])]


def normalized(value: dict) -> dict:
    return {
        "version": 1,
        "targets": sorted(copy.deepcopy(value["targets"]), key=lambda row: row["name"]),
        "edges": sorted(copy.deepcopy(value["edges"]), key=lambda row: (row["target"], row["requires"])),
    }


def normalized_jobs(rows: list) -> list:
    return [{"id": row["id"], "targets": sorted(set(row["targets"]))} for row in rows]


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "build-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "BUILD_CONFIG": str(self.path),
            "BUILD_MODE": mode,
            "BUILD_FAIL": "",
            "BUILD_PAUSE": "",
            "BUILD_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, rows: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"graph": "graph.json", "requests": "requests.json", "output": "build-plan", **changes})
    (work / "graph.json").write_text(json.dumps(value, ensure_ascii=False))
    (work / "requests.json").write_text(json.dumps(rows, ensure_ascii=False))
    fix.save()
    return fix


def oracle(value: dict, requests: list) -> list[dict]:
    """Warshall transitive closure separates blocked nodes; DAG longest paths give minimal layers."""
    names = sorted(row["name"] for row in value["targets"])
    indices = {name: index for index, name in enumerate(names)}
    prerequisites = {name: set() for name in names}
    reachable = [0] * len(names)
    for edge in value["edges"]:
        prerequisites[edge["target"]].add(edge["requires"])
        reachable[indices[edge["target"]]] |= 1 << indices[edge["requires"]]
    for pivot in range(len(names)):
        for source in range(len(names)):
            if reachable[source] & (1 << pivot):
                reachable[source] |= reachable[pivot]
    cycle_bits = sum(1 << index for index in range(len(names)) if reachable[index] & (1 << index))
    results = []
    for row in normalized_jobs(requests):
        selection = 0
        for name in row["targets"]:
            selection |= reachable[indices[name]] | (1 << indices[name])
        selected = {name for name in names if selection & (1 << indices[name])}
        blocked = {name for name in selected if reachable[indices[name]] & cycle_bits}
        completed = selected - blocked

        @cache
        def level(name: str) -> int:
            return 0 if not prerequisites[name] else 1 + max(level(child) for child in prerequisites[name])

        layers = []
        for depth in range(max((level(name) for name in completed), default=-1) + 1):
            layers.append(sorted(name for name in completed if level(name) == depth))
        results.append(
            {
                "id": row["id"],
                "status": "cycle" if blocked else "ready",
                "requested": row["targets"],
                "selected": sorted(selected),
                "prerequisites": sorted(selected - set(row["targets"])),
                "layers": layers,
                "order": list(itertools.chain.from_iterable(layers)),
                "blocked": sorted(blocked),
            }
        )
    return results


def validate_report(value: dict, rows: list, observed: dict) -> None:
    expected = oracle(value, rows)
    graph_bytes = (canonical(normalized(value)) + "\n").encode()
    metadata = {key: val for key, val in observed.items() if key != "plans"}
    assert metadata == {
        "version": 1,
        "graph": {
            "targets": len(value["targets"]),
            "edges": len(value["edges"]),
            "sha256": hashlib.sha256(graph_bytes).hexdigest(),
        },
        "requests": len(rows),
        "cyclic": sum(row["status"] == "cycle" for row in expected),
    }
    assert len(observed["plans"]) == len(expected)
    edges = {(row["target"], row["requires"]) for row in value["edges"]}
    for actual, wanted in zip(observed["plans"], expected, strict=True):
        assert {key: val for key, val in actual.items() if key not in ["cycle", "requires_path"]} == wanted
        cycle, path = actual["cycle"], actual["requires_path"]
        if actual["status"] == "ready":
            assert cycle == path == []
        else:
            assert 2 <= len(cycle) <= len(actual["blocked"]) + 1 and cycle[0] == cycle[-1]
            assert len(set(cycle[:-1])) == len(cycle) - 1
            assert set(cycle) <= set(actual["blocked"])
            assert all(edge in edges for edge in itertools.pairwise(cycle))
            assert path and path[0] in actual["requested"] and path[-1] == cycle[0]
            assert len(set(path)) == len(path) and set(path) <= set(actual["blocked"])
            assert all(edge in edges for edge in itertools.pairwise(path))
            assert set(path) & set(cycle) == {cycle[0]}
        ranks = {name: layer for layer, members in enumerate(actual["layers"]) for name in members}
        assert len(ranks) == len(actual["order"])
        for target, prerequisite in edges:
            if target in ranks:
                assert prerequisite in ranks and ranks[prerequisite] < ranks[target]
    return


def text_report(value: dict, report: dict) -> str:
    commands = {row["name"]: row["command"] for row in value["targets"]}
    paragraphs = []
    for result in report["plans"]:
        lines = [f'Request {canonical(result["id"])}: {result["status"]}']
        for number, layer in enumerate(result["layers"], start=1):
            lines.append(f"Layer {number}:")
            lines.extend(f"  {canonical(name)}  argv={canonical(commands[name])}" for name in layer)
        if result["status"] == "cycle":
            lines += [
                "Blocked: " + canonical(result["blocked"]),
                "Request-to-cycle prerequisites: " + canonical(result["requires_path"]),
                "Cycle (target requires next): " + canonical(result["cycle"]),
            ]
        paragraphs.append("\n".join(lines) + "\n")
    return "\n".join(paragraphs)


def outputs(fix: Fixture, report: dict) -> dict[str, bytes]:
    value = json.loads((fix.work / fix.config["graph"]).read_bytes())
    rows = json.loads((fix.work / fix.config["requests"]).read_bytes())
    validate_report(value, rows, report)
    expected = {
        "graph.json": (canonical(normalized(value)) + "\n").encode(),
        "requests.json": (canonical(normalized_jobs(rows)) + "\n").encode(),
        "plan.json": (canonical(report) + "\n").encode(),
        "plan.txt": text_report(value, report).encode(),
    }
    manifest = {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in expected.items()
        },
    }
    expected["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    assert sorted(path.name for path in fix.output.iterdir()) == sorted(expected)
    actual = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert actual == expected
    return actual


def success(app: Application, fix: Fixture, mode: str = "write") -> dict:
    paths = [fix.path] + [fix.work / fix.config[key] for key in ["graph", "requests"]]
    original = [path.read_bytes() for path in paths]
    value, rows = json.loads(original[1]), json.loads(original[2])
    result = app.run(fix.work, fix.settings(mode), timeout=120)
    assert result.returncode in [0, 1] and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    validate_report(value, rows, report)
    assert result.returncode == int(report["cyclic"] > 0)
    assert result.stdout == canonical(report) + "\n"
    assert original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".build-plan-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    old = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=120)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        fix.work,
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if old is not None:
        assert fix.output.read_bytes() == old
    assert not list(fix.work.glob(".build-plan-*"))
    return


def graphs(app: Application, directory: Path) -> dict:
    rng = random.Random(62062)
    observations = []
    possibilities = list(itertools.product(["a", "b", "c"], repeat=2))
    requests = [
        request("subset-" + str(bits), [name for index, name in enumerate(["a", "b", "c"]) if bits & (1 << index)])
        for bits in range(8)
    ]
    for bits in range(512):
        value = graph(["a", "b", "c"], [edge for index, edge in enumerate(possibilities) if bits & (1 << index)])
        fix = fixture(directory, "exhaustive-" + str(bits), value, requests)
        report = success(app, fix, "preview")
        observations.append(report)
        if (bits + 1) % 128 == 0:
            print(f"{app.engine} build planner: {bits + 1}/512 exhaustive graphs passed", flush=True)
    cases = [(graph([], []), []), (graph([], []), [request("nothing", [])]), (sample(), jobs())]
    unicode_names = ["🙂", "世界", "é", "e\u0301", "with space", "line\nbreak", 'quote"\\']
    cases.append(
        (graph(unicode_names, list(itertools.pairwise(unicode_names))), [request("Юникод", unicode_names * 2)])
    )
    for trial in range(28):
        count = rng.randint(1, 48)
        names = [f"t{number:02d}" for number in range(count)]
        candidates = list(itertools.product(names, repeat=2))
        if trial % 2 == 0:
            candidates = [(a, b) for a, b in candidates if a > b]
        selected = rng.sample(candidates, min(len(candidates), rng.randint(0, count * 3)))
        value = graph(names, selected)
        rows = [request("q" + str(number), rng.sample(names, rng.randint(0, count))) for number in range(8)]
        cases.append((value, rows))
    for number, (value, rows) in enumerate(cases):
        first = fixture(directory, f"case-{number}", value, rows)
        report = success(app, first)
        observations.append(report)
        shuffled = copy.deepcopy(value)
        rng.shuffle(shuffled["targets"])
        rng.shuffle(shuffled["edges"])
        requests = copy.deepcopy(rows)
        for row in requests:
            rng.shuffle(row["targets"])
        second = fixture(directory, f"permuted-{number}", shuffled, requests)
        assert success(app, second) == report
        assert {p.name: p.read_bytes() for p in first.output.iterdir()} == {
            p.name: p.read_bytes() for p in second.output.iterdir()
        }
    return {
        "exhaustive_graphs": 512,
        "exhaustive_selections": 4096,
        "other_graphs": len(cases),
        "generated_graphs": 28,
        "permutations": len(cases),
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    valid = graph(["a", "b"], [("b", "a")])
    variations = [None, [], {}, {**valid, "extra": 1}]
    variations += [{key: val for key, val in valid.items() if key != missing} for missing in valid]
    variations += [{**valid, "version": val} for val in [0, 2, True, 1.0, "1", None]]
    for field in ["targets", "edges"]:
        variations += [{**valid, field: val} for val in [None, True, "", {}]]
    for target in [None, [], {}, {"name": "a"}, {"command": []}, {"name": "a", "command": [], "extra": 1}]:
        variations.append({**valid, "targets": [target]})
    for name in [None, True, 1, [], {}, "", "a\x00", "x" * 129, "🙂" * 129]:
        variations.append({**valid, "targets": [{"name": name, "command": []}], "edges": []})
    for command in [None, True, "", {}, [None], [True], [1], [[]], [{}], [""], ["x\x00"], ["x" * 1025], ["a"] * 33]:
        variations.append({**valid, "targets": [{"name": "a", "command": command}], "edges": []})
    variations.append({**valid, "targets": valid["targets"] + [valid["targets"][0]]})
    edge_variants = [None, [], {}, {"target": "a"}, {"requires": "a"}, {"target": "a", "requires": "b", "extra": 1}]
    for field in ["target", "requires"]:
        edge_variants += [
            {"target": "b", "requires": "a", field: value}
            for value in [None, True, 1, [], {}, "", "unknown", "x" * 129, "a\x00"]
        ]
    variations += [{**valid, "edges": [edge]} for edge in edge_variants]
    variations += [{**valid, "edges": valid["edges"] * 2}]
    for index, value in enumerate(variations):
        failure(app, fixture(directory, "graph-" + str(index), value, [request("q", [])]))
    count = len(variations)
    rows_variants = [
        None,
        {},
        True,
        "",
        [None],
        [[]],
        [{}],
        [{"id": "x"}],
        [{"targets": []}],
        [{"id": "x", "targets": [], "extra": 1}],
        [request("x", []), request("x", [])],
    ]
    rows_variants += [[request(identifier, [])] for identifier in [None, True, 1, [], {}, "", "x" * 129, "x\x00"]]
    rows_variants += [[request("x", value)] for value in [None, True, 1, {}, "a"]]
    rows_variants += [[request("x", [value])] for value in [None, True, 1, [], {}, "", "x\x00", "x" * 129, "missing"]]
    for index, rows in enumerate(rows_variants):
        failure(app, fixture(directory, "requests-" + str(index), valid, rows))
    count += len(rows_variants)
    for key in ["graph", "requests", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", valid, [])
            changed = {**fix.config, key: value}
            fix.path.write_text(json.dumps(changed))
            failure(app, fix)
            count += 1
        fix = fixture(directory, "missing-" + key, valid, [])
        fix.path.write_text(json.dumps({name: value for name, value in fix.config.items() if name != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", valid, [])
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    count += 1
    fix = fixture(directory, "mode", valid, [])
    failure(app, fix, "invalid planner mode", BUILD_MODE="bad")
    count += 1
    for name in ["graph.json", "requests.json", "build-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", valid, [])
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    names = [f"n{index:03d}" for index in range(256)]
    chain = [(names[index], names[index - 1]) for index in range(1, len(names))]
    fix = fixture(directory, "long-chain", graph(names, chain), [request("all", names)])
    result = success(app, fix)["plans"][0]
    assert result["layers"] == [[name] for name in names]
    cycle = graph(names, [*chain, (names[0], names[-1])])
    fix = fixture(directory, "long-cycle", cycle, [request("last", [names[-1]])])
    assert len(success(app, fix)["plans"][0]["cycle"]) == 257
    fix = fixture(directory, "wide-layer", graph(names, []), [request("all", names)])
    assert success(app, fix)["plans"][0]["layers"] == [names]
    failure(app, fixture(directory, "targets-above", graph([*names, "extra"], []), []), "capacity")
    edges = list(itertools.product(names[:64], repeat=2))
    fix = fixture(directory, "edges-exact", graph(names, edges), [request("all", names)])
    result = success(app, fix)["plans"][0]
    assert len(result["blocked"]) == 64 and len(result["order"]) == 192
    failure(app, fixture(directory, "edges-above", graph(names, [*edges, (names[-1], names[0])]), []), "capacity")
    rows = [request("r" + str(index), [names[-1]]) for index in range(128)]
    success(app, fixture(directory, "requests-exact", graph(names, chain), rows))
    failure(app, fixture(directory, "requests-above", graph(names, chain), [*rows, request("extra", [])]), "count")
    failure(app, fixture(directory, "selection-above", graph(names, []), [request("all", [*names, names[0]])]), "count")
    unicode_name = "🙂" * 128
    value = graph([unicode_name], [])
    value["targets"][0]["command"] = ["🙂" * 1024] * 32
    success(app, fixture(directory, "text-exact", value, [request("🙂" * 128, [unicode_name])]))
    value["targets"][0]["command"] = ["builder", "", "spaces here", "$(never executed)", "a\nline"]
    success(app, fixture(directory, "argv-literals", value, [request("q", [unicode_name])]))
    for name, maximum in [("build-job.json", 65536), ("graph.json", 4194304), ("requests.json", 4194304)]:
        fix = fixture(directory, "bytes-" + name, graph(["a"], []), [request("q", ["a"])])
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    wide_names = [str(index).zfill(3) + "🙂" * 125 for index in range(256)]
    value = graph(wide_names, list(itertools.pairwise(wide_names)))
    fix = fixture(directory, "plans-above", value, [request("r" + str(index), [wide_names[0]]) for index in range(128)])
    failure(app, fix, "plans exceed 16 MiB")
    # Tiny plans can still have oversized human-readable command listings.
    value = graph(names[:96], list(itertools.pairwise(names[:96])))
    for target in value["targets"]:
        target["command"] = ["x" * 1024] * 32
    fix = fixture(directory, "text-report-above", value, [request("r" + str(index), [names[0]]) for index in range(8)])
    assert (fix.work / "graph.json").stat().st_size < 4194304
    failure(app, fix, "report exceeds 16 MiB")
    return {
        "targets": 256,
        "edges": 4096,
        "requests": 128,
        "selection_entries": 256,
        "name_characters": 128,
        "name_bytes": 512,
        "command_arguments": 32,
        "argument_characters": 1024,
        "argument_bytes": 4096,
        "longest_chain_layers": 256,
        "longest_cycle_vertices": 256,
        "config_bytes": 65536,
        "input_bytes": 4194304,
        "report_bytes": 16777216,
    }


def paused(app: Application, fix: Fixture, point: str = "ready") -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(BUILD_PAUSE=point, BUILD_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED " + point + "\n":
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
        "graph.json",
        "requests.json",
        "plan.json",
        "plan.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample(), jobs())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(BUILD_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".build-plan-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["graph", "requests", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, sample(), jobs())
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
            assert not list(fix.work.glob(".build-plan-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", sample(), jobs())
    reference = success(app, fix, "preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".build-plan-*"))
    assert len(abandoned) == 1
    previous = {p.name: p.read_bytes() for p in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 1 and not result.stderr
    outputs(fix, reference)
    assert {p.name: p.read_bytes() for p in abandoned[0].iterdir()} == previous
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    for name in ["file", "directory", "symlink", "dangling", "same-graph", "same-requests", "same-config"]:
        fix = fixture(directory, "destination-" + name, sample(), jobs())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("graph.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = {
                "same-graph": "graph.json",
                "same-requests": "requests.json",
                "same-config": "build-job.json",
            }[name]
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in ["graph.json", "requests.json", "build-job.json"]:
        fix = fixture(directory, "symlink-" + name, sample(), jobs())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", sample(), jobs())
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
    return 11


def check(app: Application, directory: Path) -> dict:
    observations = graphs(app, directory / "graphs")
    print(app.engine + " build planner: reachability, layers, cycle witnesses and permutations passed", flush=True)
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " build planner: input bounds, atomic publication and path checks passed", flush=True)
    return {
        **observations,
        "invalid_inputs": invalid,
        "limits": bounds,
        "publication_cases": faults,
        "path_cases": path_cases,
    }
