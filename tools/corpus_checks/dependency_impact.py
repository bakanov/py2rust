"""Independent transitive closure and path-relaxation oracles for complete dependency audits."""

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
from pathlib import Path

from .common import Application
from .csv_json import canonical


def graph(names: list[str], edges: list[tuple[str, str]]) -> dict:
    return {"version": 1, "modules": names, "edges": [{"module": a, "depends_on": b} for a, b in edges]}


def request(identifier: str, names: list[str]) -> dict:
    return {"id": identifier, "changed": names}


def sample() -> dict:
    return graph(
        ["app", "api", "auth", "cache", "db", "models", "tools", "unused"],
        [
            ("app", "api"),
            ("api", "auth"),
            ("api", "cache"),
            ("auth", "models"),
            ("models", "auth"),
            ("models", "db"),
            ("cache", "db"),
            ("tools", "tools"),
        ],
    )


def jobs() -> list:
    return [
        request("database", ["db"]),
        request("cycle", ["auth"]),
        request("two roots", ["cache", "auth"]),
        request("none", []),
        request("tool", ["tools"]),
    ]


def normalized(value: dict) -> dict:
    return {
        "version": 1,
        "modules": sorted(value["modules"]),
        "edges": sorted(copy.deepcopy(value["edges"]), key=lambda e: (e["module"], e["depends_on"])),
    }


def normalized_jobs(rows: list) -> list:
    return [{"id": row["id"], "changed": sorted(set(row["changed"]))} for row in rows]


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "impact-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config, ensure_ascii=False))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "IMPACT_CONFIG": str(self.path),
            "IMPACT_MODE": mode,
            "IMPACT_FAIL": "",
            "IMPACT_PAUSE": "",
            "IMPACT_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, value: dict, rows: list, **changes: object) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"graph": "graph.json", "requests": "requests.json", "output": "dependency-impact", **changes})
    (work / "graph.json").write_text(json.dumps(value, ensure_ascii=False))
    (work / "requests.json").write_text(json.dumps(rows, ensure_ascii=False))
    fix.save()
    return fix


def oracle(value: dict, rows: list) -> dict:
    names = sorted(value["modules"])
    indices = {name: i for i, name in enumerate(names)}
    edges = {(edge["module"], edge["depends_on"]) for edge in value["edges"]}
    dependencies = {name: {b for a, b in edges if a == name} for name in names}
    dependents = {name: {a for a, b in edges if b == name} for name in names}
    # Reflexive Warshall bit closure, without DFS or the application's component algorithm.
    reach = [(1 << i) | sum(1 << indices[b] for b in dependencies[name] if b != name) for i, name in enumerate(names)]
    for pivot in range(len(names)):
        for source in range(len(names)):
            if reach[source] & (1 << pivot):
                reach[source] |= reach[pivot]
    membership = {}
    components = []
    for module in names:
        if module in membership:
            continue
        members = [
            other
            for other in names
            if reach[indices[module]] & (1 << indices[other]) and reach[indices[other]] & (1 << indices[module])
        ]
        components.append(members)
        for member in members:
            membership[member] = members[0]
    groups = []
    for members in components:
        identifier = members[0]
        groups.append(
            {
                "id": identifier,
                "members": members,
                "cyclic": len(members) > 1 or (identifier, identifier) in edges,
                "dependencies": sorted({membership[b] for a, b in edges if a in members} - {identifier}),
                "dependents": sorted({membership[a] for a, b in edges if b in members} - {identifier}),
            }
        )
    structure = {
        "counts": {
            "modules": len(names),
            "edges": len(edges),
            "groups": len(groups),
            "cyclic_groups": sum(g["cyclic"] for g in groups),
        },
        "modules": [
            {
                "name": name,
                "dependencies": sorted(dependencies[name]),
                "dependents": sorted(dependents[name]),
                "group": membership[name],
            }
            for name in names
        ],
        "groups": groups,
    }
    impacts = []
    for row in normalized_jobs(rows):
        changed = row["changed"]
        affected = [name for name in names if any(reach[indices[name]] & (1 << indices[c]) for c in changed)]
        # Synchronous Bellman-Ford-style relaxation of complete path keys, without a BFS queue.
        best = {name: (0, name, (name,)) for name in changed}
        for _ in range(max(0, len(names) - 1)):
            before = best.copy()
            for module, dependency in edges:
                if dependency in before:
                    hops, root, reverse_path = before[dependency]
                    candidate = (hops + 1, root, (*reverse_path, module))
                    if module not in best or candidate < best[module]:
                        best[module] = candidate
            if best == before:
                break
        assert sorted(best) == affected
        explanations = [
            {
                "module": name,
                "changed": name in changed,
                "root": best[name][1],
                "hops": best[name][0],
                "path": list(reversed(best[name][2])),
            }
            for name in affected
        ]
        impacts.append(
            {
                "id": row["id"],
                "changed": changed,
                "affected": affected,
                "unaffected": sorted(set(names) - set(affected)),
                "groups": sorted({membership[name] for name in affected}),
                "explanations": explanations,
            }
        )
    hashes = {
        filename: hashlib.sha256((canonical(data) + "\n").encode()).hexdigest()
        for filename, data in [("graph.json", normalized(value)), ("requests.json", normalized_jobs(rows))]
    }
    return {"version": 1, "input_sha256": hashes, "structure": structure, "requests": len(rows), "impacts": impacts}


def invariants(value: dict, report: dict) -> None:
    edges = {(edge["module"], edge["depends_on"]) for edge in value["edges"]}
    groups = report["structure"]["groups"]
    membership = {name: g["id"] for g in groups for name in g["members"]}
    assert sorted(membership) == sorted(value["modules"])
    assert sum(len(g["members"]) for g in groups) == len(membership)
    remaining = {g["id"]: set(g["dependencies"]) for g in groups}
    # The quotient graph must be acyclic even when the source graph is cyclic.
    while remaining:
        ready = {name for name, deps in remaining.items() if not deps}
        assert ready
        remaining = {name: deps - ready for name, deps in remaining.items() if name not in ready}
    for impact in report["impacts"]:
        assert set(impact["affected"]) | set(impact["unaffected"]) == set(value["modules"])
        assert not set(impact["affected"]) & set(impact["unaffected"])
        assert set(impact["changed"]) <= set(impact["affected"])
        for group in groups:
            assert not set(group["members"]) & set(impact["affected"]) or set(group["members"]) <= set(
                impact["affected"]
            )
        for record in impact["explanations"]:
            path = record["path"]
            assert path[0] == record["module"] and path[-1] == record["root"] and record["root"] in impact["changed"]
            assert len(path) == len(set(path)) and len(path) == record["hops"] + 1
            assert all(edge in edges for edge in itertools.pairwise(path))
            assert record["changed"] == (record["module"] in impact["changed"])
    return


def outputs(fix: Fixture, report: dict) -> dict:
    value = json.loads((fix.work / fix.config["graph"]).read_bytes())
    rows = json.loads((fix.work / fix.config["requests"]).read_bytes())
    text = []
    for result in report["impacts"]:
        lines = ["Change " + canonical(result["id"]) + ": " + canonical(result["changed"])]
        lines += [
            canonical(row["module"]) + " depends through " + canonical(row["path"]) for row in result["explanations"]
        ]
        lines.append("Unaffected: " + canonical(result["unaffected"]))
        text.append("\n".join(lines) + "\n")
    expected = {
        "graph.json": (canonical(normalized(value)) + "\n").encode(),
        "requests.json": (canonical(normalized_jobs(rows)) + "\n").encode(),
        "impact.json": (canonical(report) + "\n").encode(),
        "impacts.jsonl": "".join(canonical(r) + "\n" for r in report["impacts"]).encode(),
        "impact.txt": "\n".join(text).encode(),
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
    paths = [fix.path, fix.work / fix.config["graph"], fix.work / fix.config["requests"]]
    original = [p.read_bytes() for p in paths]
    value, rows = json.loads(original[1]), json.loads(original[2])
    result = app.run(fix.work, fix.settings(mode), timeout=180)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    observed = json.loads(result.stdout)
    expected = oracle(value, rows)
    assert observed == expected, (fix.work, observed, expected)
    invariants(value, observed)
    assert result.stdout == canonical(observed) + "\n"
    assert original == [path.read_bytes() for path in paths]
    if mode == "write":
        outputs(fix, observed)
    else:
        assert not fix.output.exists()
    assert not list(fix.work.glob(".dependency-impact-*"))
    return observed


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra), timeout=60)
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        result,
        message,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.work.glob(".dependency-impact-*"))
    return


def scenarios(app: Application, directory: Path) -> dict:
    observations = []
    names = ["a", "b", "c"]
    possibilities = list(itertools.product(names, repeat=2))
    rows = [request(str(mask), [name for i, name in enumerate(names) if mask & (1 << i)]) for mask in range(8)]
    for mask in range(512):
        value = graph(names, [edge for i, edge in enumerate(possibilities) if mask & (1 << i)])
        observations.append(success(app, fixture(directory, "exhaustive-" + str(mask), value, rows)))
    print(app.engine + " dependency impact: 512 graphs and 4,096 change sets passed", flush=True)
    cases = [
        (sample(), jobs()),
        (graph([], []), []),
        (graph([], []), [request("empty", [])]),
        (graph(["a"], []), [request("none", []), request("same", ["a", "a"])]),
        (graph(["a"], [("a", "a")]), [request("self", ["a"])]),
        (
            graph(["é", "e\u0301", "🙂", 'line\n"quote'], [("é", "🙂"), ("🙂", "e\u0301")]),
            [request('id\n"quote', ["🙂"])],
        ),
        (
            graph(["a", "b", "c", "d"], [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]),
            [request("diamond", ["d"]), request("root-tie", ["c", "b"])],
        ),
        (
            graph(
                ["x", "a", "b", "c", "d", "z"], [("x", "a"), ("x", "b"), ("a", "d"), ("b", "c"), ("c", "z"), ("d", "z")]
            ),
            [request("reverse-path-tie", ["z"])],
        ),
    ]
    randomizer = random.Random(66066)
    for index in range(40):
        names = ["n" + str(i).zfill(2) for i in range(randomizer.randint(4, 24))]
        edges = [(a, b) for a in names for b in names if randomizer.random() < [0.02, 0.12, 0.35, 0.8][index % 4]]
        rows = [request(str(i), randomizer.choices(names, k=randomizer.randint(0, len(names)))) for i in range(8)]
        cases.append((graph(names, edges), rows))
    for index, (value, rows) in enumerate(cases):
        fix = fixture(directory, "case-" + str(index), value, rows)
        report = success(app, fix)
        if index == 6:
            assert report["impacts"][0]["explanations"][0]["path"] == ["a", "b", "d"]
            assert report["impacts"][1]["explanations"][0]["root"] == "b"
        if index == 7:
            record = next(r for r in report["impacts"][0]["explanations"] if r["module"] == "x")
            assert record["path"] == ["x", "b", "c", "z"]
        variant = copy.deepcopy(value)
        randomizer.shuffle(variant["modules"])
        randomizer.shuffle(variant["edges"])
        different = [{"id": row["id"], "changed": list(reversed(row["changed"])) + row["changed"][:1]} for row in rows]
        other = fixture(directory, "permuted-" + str(index), variant, different)
        assert success(app, other) == report
        assert outputs(other, report) == outputs(fix, report)
        observations.append(report)
    first = success(app, fixture(directory, "split-first", sample(), jobs()[:2]))
    second = success(app, fixture(directory, "split-second", sample(), jobs()[2:]))
    assert first["impacts"] + second["impacts"] == observations[512]["impacts"]
    return {
        "exhaustive_graphs": 512,
        "exhaustive_change_sets": 4096,
        "other_graphs": len(cases),
        "generated_graphs": 40,
        "normalized_permutations": len(cases),
        "split_batches": 2,
        "reports_sha256": hashlib.sha256(canonical(observations).encode()).hexdigest(),
    }


def invalid_inputs(app: Application, directory: Path) -> int:
    base = graph(["a"], [])
    variants = [None, [], {}, True, {**base, "extra": 1}]
    variants += [{key: value for key, value in base.items() if key != missing} for missing in base]
    for key, values in {
        "version": [0, 2, True, 1.0, "1", None],
        "modules": [None, {}, True, "", ["a", "a"]],
        "edges": [None, {}, True, ""],
    }.items():
        variants += [{**base, key: value} for value in values]
    malformed_names = ["", "a\x00", "x" * 129, "🙂" * 129, None, True, 1, [], {}]
    variants += [{**base, "modules": [value]} for value in malformed_names]
    edge = {"module": "a", "depends_on": "a"}
    malformed_edges = [None, [], {}, True, {**edge, "extra": 1}, {"module": "a"}, {"depends_on": "a"}]
    for field in edge:
        malformed_edges += [{**edge, field: value} for value in [*malformed_names, "unknown"]]
    variants += [{**base, "edges": [value]} for value in malformed_edges]
    variants.append({**base, "edges": [edge, edge]})
    for index, value in enumerate(variants):
        failure(app, fixture(directory, "graph-" + str(index), value, []))
    row = request("q", ["a"])
    bad_jobs = [
        None,
        {},
        True,
        "",
        [None],
        [[]],
        [{}],
        [{**row, "extra": 1}],
        [row, row],
        [{"id": "q"}],
        [{"changed": []}],
    ]
    bad_jobs += [[{**row, "id": value}] for value in malformed_names]
    bad_jobs += [[{**row, "changed": value}] for value in [None, {}, True, ""]]
    bad_jobs += [[{**row, "changed": [value]}] for value in [*malformed_names, "unknown"]]
    for index, value in enumerate(bad_jobs):
        failure(app, fixture(directory, "requests-" + str(index), base, value))
    count = len(variants) + len(bad_jobs)
    for key in ["graph", "requests", "output"]:
        for index, value in enumerate(["", "\x00", None, True, 1, [], {}]):
            fix = fixture(directory, f"config-{key}-{index}", base, [])
            fix.path.write_text(json.dumps({**fix.config, key: value}))
            failure(app, fix)
            count += 1
        fix = fixture(directory, "missing-" + key, base, [])
        fix.path.write_text(json.dumps({k: v for k, v in fix.config.items() if k != key}))
        failure(app, fix)
        count += 1
    fix = fixture(directory, "extra-config", base, [])
    fix.path.write_text(json.dumps({**fix.config, "extra": 1}))
    failure(app, fix)
    failure(app, fixture(directory, "mode", base, []), "invalid impact mode", IMPACT_MODE="bad")
    count += 2
    for name in ["graph.json", "requests.json", "impact-job.json"]:
        for index, raw in enumerate([b"\xff", b"{", b"[] trailing", b"[NaN]", b"[Infinity]", b'{"a":1,"a":2}']):
            fix = fixture(directory, f"raw-{name}-{index}", base, [])
            (fix.work / name).write_bytes(raw)
            failure(app, fix)
            count += 1
    return count


def limits(app: Application, directory: Path) -> dict:
    names = ["n" + str(i).zfill(3) for i in range(256)]
    edges = list(itertools.pairwise(names))
    value = graph(names, edges)
    report = success(
        app,
        fixture(
            directory,
            "long-chain",
            value,
            [
                request("tail", [names[-1]]),
                request("head", [names[0]]),
                request("middle", [names[128]]),
                request("empty", []),
            ],
        ),
    )
    assert report["impacts"][0]["explanations"][0]["hops"] == 255
    assert report["impacts"][0]["explanations"][0]["path"] == names
    assert report["structure"]["counts"]["groups"] == 256
    value = graph(names, [*edges, (names[-1], names[0])])
    report = success(app, fixture(directory, "long-cycle", value, [request("one", [names[-1]])]))
    assert report["structure"]["groups"] == [
        {"id": names[0], "members": names, "cyclic": True, "dependencies": [], "dependents": []}
    ]
    dense = graph(names, list(itertools.product(names[:64], repeat=2)))
    rows = [request(str(i), names) for i in range(64)]
    report = success(app, fixture(directory, "combined-capacity", dense, rows))
    assert report["structure"]["counts"] == {"modules": 256, "edges": 4096, "groups": 193, "cyclic_groups": 1}
    assert len(report["impacts"]) == 64 and all(len(r["affected"]) == 256 for r in report["impacts"])
    failure(app, fixture(directory, "modules-above", graph([*names, "extra"], []), []), "graph capacity")
    failure(
        app,
        fixture(
            directory,
            "edges-above",
            graph(names, [*((e["module"], e["depends_on"]) for e in dense["edges"]), (names[64], names[65])]),
            [],
        ),
        "graph capacity",
    )
    failure(
        app,
        fixture(directory, "requests-above", graph(["a"], []), [request(str(i), []) for i in range(65)]),
        "request count",
    )
    failure(app, fixture(directory, "changes-above", graph(["a"], []), [request("q", ["a"] * 257)]), "change count")
    report = success(app, fixture(directory, "duplicates-exact", graph(["a"], []), [request("q", ["a"] * 256)]))
    assert report["impacts"][0]["changed"] == ["a"]
    success(app, fixture(directory, "names-exact", graph(["🙂" * 128], []), [request("🙂" * 128, ["🙂" * 128])]))
    for count, length, requests in [(256, 125, 1), (128, 48, 8)]:
        long_names = [str(i).zfill(3) + "🙂" * length for i in range(count)]
        value = graph(long_names, list(itertools.pairwise(long_names)))
        rows = [request(str(i), [long_names[-1]]) for i in range(requests)]
        failure(app, fixture(directory, "explanations-above-" + str(count), value, rows), "explanations exceed 8 MiB")
    for name, maximum in [("impact-job.json", 65536), ("graph.json", 4194304), ("requests.json", 4194304)]:
        fix = fixture(directory, "bytes-" + name, sample(), jobs())
        path = fix.work / name
        raw = path.read_bytes()
        path.write_bytes(raw + b" " * (maximum - len(raw)))
        success(app, fix, "preview")
        path.write_bytes(raw + b" " * (maximum + 1 - len(raw)))
        failure(app, fix, "byte limit")
        path.write_bytes(raw)
    return {
        "modules": 256,
        "edges": 4096,
        "requests": 64,
        "change_entries": 256,
        "name_characters": 128,
        "name_bytes": 512,
        "longest_chain_hops": 255,
        "config_bytes": 65536,
        "graph_bytes": 4194304,
        "requests_bytes": 4194304,
        "explanations_bytes": 8388608,
        "single_and_cumulative_output_rejection": True,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(IMPACT_PAUSE="ready", IMPACT_CONTINUE=str(fix.work / "continue"))),
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
        "graph.json",
        "requests.json",
        "impact.json",
        "impacts.jsonl",
        "impact.txt",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, sample(), jobs())
        reference = success(app, fix, "preview")
        result = app.run(fix.work, fix.settings(IMPACT_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".dependency-impact-*"))
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
            assert not list(fix.work.glob(".dependency-impact-*"))
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
    abandoned = list(fix.work.glob(".dependency-impact-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    names = ["graph.json", "requests.json", "impact-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, sample(), jobs())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("graph.json" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
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
    cases = scenarios(app, directory / "scenarios")
    print(
        app.engine + " dependency impact: independent components, reachability and shortest witnesses passed",
        flush=True,
    )
    invalid = invalid_inputs(app, directory / "invalid")
    bounds = limits(app, directory / "limits")
    faults = publication(app, directory / "publication")
    path_cases = paths(app, directory / "paths")
    print(app.engine + " dependency impact: validation, limits, publication and path checks passed", flush=True)
    return {**cases, "invalid_inputs": invalid, "limits": bounds, "publication_cases": faults, "path_cases": path_cases}
