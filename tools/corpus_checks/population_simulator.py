"""Whole-project growth integration checks with analytic solutions, refinement and actual portable exports."""

from __future__ import annotations

import copy
import itertools
import json
import math
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .population_fixture import (
    analytic,
    canonical,
    case,
    digest,
    document,
    inspect_csv,
    inspect_results,
    inspect_svg,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "simulate", "input": "experiment.json", "output": "output"}
    save(root / "population-job.json", config)
    save(root / "experiment.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    directory = root / config["output"]
    raw = (directory / "archive.json").read_bytes()
    archive = json.loads(raw)
    assert (
        archive.keys() == {"version", "source", "results"}
        and type(archive["version"]) is int
        and archive["version"] == 1
    )
    assert raw == canonical(archive) and canonical(archive["source"]) == canonical(source)
    results = archive["results"]
    inspect_results(source, results)
    plot = (directory / "plot.svg").read_bytes()
    csv = (directory / "series.csv").read_bytes()
    inspect_csv(csv, results)
    inspect_svg(plot, source, results)
    files = {
        "archive.json": raw,
        "experiment.json": canonical(source),
        "series.json": canonical(results),
        "series.csv": csv,
        "plot.svg": plot,
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "summary": results["summary"], "archive_sha256": digest(raw)}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "simulate.json": canonical(
            {"version": 1, "mode": "simulate", "input": "experiment.json", "output": "simulated"}
        ),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    if config["mode"] == "verify":
        assert canonical(imported["results"]) == canonical(results)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "population-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"POPULATION_CONFIG": str(root / selected)}, timeout=120)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert result.stdout == canonical(archive["results"]["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=30)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".population-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: dict, stem: str) -> dict:
    original = files_at(root)
    config = json.loads((root / "simulate.json").read_bytes())
    config.update(input=stem + "-experiment.json", output=stem)
    save(root / config["input"], source)
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    original = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "simulate.json") == archive
    assert files_at(root / "output") == original
    hand = [
        document([case("zero", 0, 0.2), case("constant", 123.25, 0), case("equilibrium", 100, 0.25, 100)]),
        document([case("decay", 10, -0.25), case("logistic_decay", 10, -0.25, 100)]),
        document([case("above", 150, 0.25, 100)], steps=128),
        document([case("reverse_above", 105, -0.25, 100)], steps=32),
        document([case("a", 0, 0), case("b", 0, -1000, 1e-9)], timestep=1e-9, steps=0),
        document([case("tiny", 1e-9, 0), case("large", 1e12, 0, 1e-9)], timestep=1e6, steps=1),
        document([case("escaped", 1, 0, name="A < B & \"C\" 'D' 😀")], title=' Café\t<plot>& "comparison"\n '),
        document([case("Z" + "x" * 31, 1, 0, name="😀" * 60)], title="😀" * 100, steps=0),
    ]
    for index, source in enumerate(hand):
        work = root / ("hand-" + str(index))
        run(app, work, fixture(work, source))
    rows = [
        case("grow", 100, 0.25),
        case("decay", 100, -0.25),
        case("below", 100, 0.25, 1000),
        case("above", 1500, 0.25, 1000),
    ]
    coarse = document(rows, timestep=0.125, steps=64)
    fine = dict(coarse, timestep=0.0625, steps=128)
    first = run(app, root / "coarse", fixture(root / "coarse", coarse))
    second = run(app, root / "fine", fixture(root / "fine", fine))
    ratios = []
    for params, left, right in zip(rows, first["results"]["series"], second["results"]["series"]):
        exact = analytic(params, 0.125, 64)
        a = abs(left["final"] - exact)
        b = abs(right["final"] - exact)
        assert a > 1e-10 and 10 < a / b < 24, (params, a, b)
        ratios.append(a / b)
    return {
        "hand_experiments": 1 + len(hand),
        "closed_form_decimal_precision": 70,
        "analytic_relative_tolerance": 2e-5,
        "analytic_initial_scale_tolerance": 1e-13,
        "analytic_absolute_floor": 1e-110,
        "refined_series": 4,
        "refinement_reduces_error_by_more_than_ten": True,
        "all_states_compared_to_closed_form": True,
        "constant_zero_equilibrium_and_above_capacity": True,
        "escaped_and_degenerate_svg": True,
        "actual_replay_and_simulate_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(110)
    hashes = []
    points = 0
    for batch in range(24):
        rows = []
        for index in range(4):
            initial = 10.0 ** rng.randint(-3, 6) * rng.uniform(1, 4)
            rate = rng.choice([-0.25, -0.1, 0.1, 0.25])
            capacity = initial * rng.uniform(2, 5) if index % 2 else None
            rows.append(case("case_" + str(index), initial, rate, capacity, "Comparison <" + str(index) + "> & 😀"))
        source = document(rows, steps=48 + 16 * (batch % 5))
        work = root / str(batch)
        first = run(app, work, fixture(work, source))
        points += len(rows) * (source["steps"] + 1)
        shuffled = dict(source, cases=list(reversed(rows)))
        other = run(app, work / "reordered", fixture(work / "reordered", shuffled))
        assert [r["values"] for r in other["results"]["series"]] == [
            r["values"] for r in reversed(first["results"]["series"])
        ]
        scaled = copy.deepcopy(source)
        for row in scaled["cases"]:
            row["initial"] *= 10
            if row["capacity"] is not None:
                row["capacity"] *= 10
        changed = edit_export(app, work / "output", scaled, "scaled")
        for left, right in zip(first["results"]["series"], changed["results"]["series"]):
            for a, b in zip(left["values"], right["values"]):
                assert math.isclose(a * 10, b, rel_tol=5e-14, abs_tol=1e-100)
        assert consume(app, work / "output/scaled", "replay.json") == changed
        # A second run starts from the actual exported midpoint; it must reproduce the suffix exactly.
        split = source["steps"] // 2
        prefix = dict(source, steps=split)
        head = edit_export(app, work / "output", prefix, "prefix")
        suffix = copy.deepcopy(source)
        suffix["steps"] -= split
        for row, ended in zip(suffix["cases"], head["results"]["series"]):
            row["initial"] = ended["final"]
        tail = edit_export(app, work / "output/prefix", suffix, "suffix")
        assert [r["values"] for r in tail["results"]["series"]] == [
            r["values"][split:] for r in first["results"]["series"]
        ]
        hashes.extend([digest(canonical(first)), digest(canonical(changed)), digest(canonical(tail))])
    return {
        "seed": 110,
        "experiments": 24,
        "series": 96,
        "primary_points": points,
        "reordered_experiments": 24,
        "scaled_exports_replayed": 24,
        "split_experiments_reproduced": 24,
        "analytic_checks_all_points": True,
        "csv_and_svg_all_points": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    sources = []
    for field, values in [
        ("version", [0, 2, True, 1.0, "1", None]),
        (
            "title",
            [None, 1, False, [], {}, "", " \n\t ", "x" * 101, "\ufb01" * 51, "x\0y", "x\x7fy", "x\x80y", "x\x9fy"],
        ),
        ("timestep", [None, True, "0.1", [], {}, 0, -1, 1e-10, 1000001]),
        ("steps", [None, True, "1", 1.0, -1, 2049]),
        ("cases", [None, True, 1, {}, "x", [], [None], [[]], [1], [False]]),
    ]:
        for value in values:
            source = document()
            source[field] = value
            sources.append(source)
    for field, values in [
        ("id", [None, 1, True, "", "1x", "x y", "x" * 33, "😀", "a\n"]),
        ("name", [None, 1, False, "", " " * 3, "x" * 61, "\ufb01" * 31, "x\0y", "x\x7fy"]),
        ("model", [None, 1, True, "", "Exponential", "linear"]),
        ("initial", [None, True, "100", -1, 1e-10, 1e12 + 1, [], {}]),
        ("rate", [None, False, "0.1", 1e-13, -1e-13, 1001, -1001, [], {}]),
        ("capacity", [False, 0, 1, 1000, "1000", [], {}]),
    ]:
        for value in values:
            source = document()
            source["cases"][0][field] = value
            sources.append(source)
    for value in [None, True, "100", 0, -1, 1e-10, 1e12 + 1, [], {}]:
        source = document()
        source["cases"][1]["capacity"] = value
        sources.append(source)
    for field in ["version", "title", "timestep", "steps", "cases"]:
        source = document()
        del source[field]
        sources.append(source)
    for field in ["id", "name", "model", "initial", "rate", "capacity"]:
        source = document()
        del source["cases"][0][field]
        sources.append(source)
    source = document()
    source["cases"][1]["id"] = source["cases"][0]["id"]
    sources.append(source)
    source = document()
    source["cases"][0]["extra"] = True
    sources.append(source)
    sources += [None, [], 42, True, {}, dict(document(), extra=True)]
    sources += [
        document([case("unstable", 1, 1)], timestep=0.051),
        document([case("large_ratio", 2, -1, 1)], timestep=0.025),
        document([case("eventual_pole", 110, -0.25, 100)], timestep=0.01, steps=1200),
    ]
    for index, source in enumerate(sources):
        work = root / ("source-" + str(index))
        fixture(work)
        save(work / "experiment.json", source)
        reject(app, work)
    valid = {"version": 1, "mode": "simulate", "input": "experiment.json", "output": "output"}
    configs = [
        dict(valid, **{key: value})
        for key, value in [
            ("version", True),
            ("version", 1.0),
            ("version", 2),
            ("mode", "unknown"),
            ("mode", 1),
            ("input", None),
            ("input", ""),
            ("input", "missing"),
            ("output", None),
            ("output", ""),
        ]
    ]
    configs += [{key: value for key, value in valid.items() if key != "mode"}, dict(valid, extra=True)]
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "population-job.json", config)
        reject(app, work)
    malformed = [
        b"",
        b"{",
        b"{}{}",
        b"[] trailing",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e9999}',
        b"\xff",
        b'{"x":"\\ud800"}',
    ]
    for slot in ["request", "source", "archive"]:
        for index, raw in enumerate(malformed):
            work = root / (slot + "-json-" + str(index))
            config = fixture(work)
            name = "population-job.json" if slot == "request" else "experiment.json"
            if slot == "archive":
                name = "archive.json"
                config.update(mode="verify", input=name)
                save(work / "population-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "valid-archive"
    archive = run(app, work, fixture(work))
    changes = [
        (("version",), 1.0),
        (("results", "summary", "steps"), 160.0),
        (("results", "times", 0), 0),
        (("results", "times", 1), True),
        (
            (
                "results",
                "method",
            ),
            "euler",
        ),
        (("results", "series", 0, "initial"), 100),
        (("results", "series", 0, "final"), 1.0),
        (("results", "series", 1, "difference_from_first"), 0.0),
        (("results", "series", 0, "values", 1), math.nextafter(archive["results"]["series"][0]["values"][1], math.inf)),
        (("results", "series", 0, "minimum"), -1.0),
        (("results", "series", 0, "name"), "changed"),
        (("results", "series", 0, "values"), []),
        (("results", "series", 0, "maximum"), None),
        (("source", "cases", 0, "rate"), 0.09),
    ]
    for index, (path, value) in enumerate(changes):
        changed = copy.deepcopy(archive)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "population-job.json", config)
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_sources": len(sources),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(malformed),
        "tampered_archives": len(changes),
        "one_ulp_series_tampering_rejected": True,
        "strict_cached_numeric_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    rows = [
        case("limit_" + str(i), float(i + 1), 0.25 if i % 2 else -0.25, None if i % 4 < 2 else 100.0, name="😀" * 60)
        for i in range(16)
    ]
    source = document(rows, timestep=0.125, steps=2048, title="😀" * 100)
    work = root / "maximum"
    archive = run(app, work, fixture(work, source))
    assert archive["results"]["summary"]["points"] == 32784
    maximum_bytes = len((work / "output/archive.json").read_bytes())
    assert consume(app, work / "output", "replay.json") == archive
    assert consume(app, work / "output", "simulate.json") == archive
    work = root / "over-cases"
    fixture(work, document(rows + [case("extra")]))
    reject(app, work)
    boundaries = [
        document([case("exact", 1, 1)], timestep=0.05, steps=2048),
        document([case("decay", 1, -1)], timestep=0.05, steps=2048),
        document([case("fast", 1e-9, 1000)], timestep=1e-9, steps=1),
        document([case("slow", 1e12, -1e-12, 1e12)], timestep=1e6, steps=1),
        document([case("tiny", 0, 0, 1e-9)], timestep=1e-9, steps=0),
    ]
    for index, source in enumerate(boundaries):
        work = root / ("numeric-" + str(index))
        run(app, work, fixture(work, source))
    work = root / "just-over-stage-bound"
    fixture(work, document([case("limit", 1, 1)], timestep=math.nextafter(0.05, math.inf)))
    reject(app, work, "timestep too large")
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("population-job.json", 65536), ("experiment.json", 2097152)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("population-job.json", 65536), ("experiment.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "population-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "cases": 16,
        "steps": 2048,
        "points": 32784,
        "title_characters": 100,
        "name_characters": 60,
        "maximum_archive_bytes": maximum_bytes,
        "maximum_stage_factor": 0.05,
        "numeric_boundary_experiments": len(boundaries),
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document()
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"POPULATION_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".population-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "source", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment(
                {"POPULATION_PAUSE": stage, "POPULATION_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            assert select.select([process.stdout], [], [], 10)[0]
            assert process.stdout.readline() == "PAUSED " + stage + "\n"
            if mutation.startswith("kill"):
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9 and (work / "output").exists() == (stage == "published")
                assert len(list(work.glob(".population-*"))) == (1 if stage == "staged" else 0)
                if stage == "published":
                    inspect(work, config)
                config["output"] = "retry"
                save(work / "retry.json", config)
                run(app, work, config, selected="retry.json")
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = "population-job.json" if mutation == "request" else "experiment.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".population-*"))
                if mutation == "competitor":
                    assert (work / "output/keep").read_text() == "original"
                else:
                    assert not (work / "output").exists()
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            process.stdout.close()
            process.stderr.close()
    return {
        "caught_faults": 2,
        "hard_kills": 2,
        "input_output_races": 3,
        "retry_after_hard_kill": True,
        "complete_or_absent_final_bundle": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["population-job.json", "experiment.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work)
        path = work / name
        raw = path.read_bytes()
        path.unlink()
        target = work / "target"
        target.write_bytes(raw)
        if kind == "symlink":
            path.symlink_to(target)
        elif kind == "hardlink":
            os.link(target, path)
        elif kind == "fifo":
            os.mkfifo(path)
        elif kind == "directory":
            path.mkdir()
        else:
            path.write_bytes(raw)
            path.chmod(0)
        try:
            reject(app, work)
            assert target.read_bytes() == raw
        finally:
            if kind == "unreadable":
                path.chmod(0o600)
        count += 1
    for kind in ["file", "directory", "symlink", "permission"]:
        work = root / str(count)
        fixture(work)
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "population-job.json")
        else:
            work.chmod(0o500)
        try:
            result = app.run(work, {})
            assert result.returncode == 2 and result.stderr and not result.stdout
            if kind == "file":
                assert output.read_text() == "keep"
            elif kind == "directory":
                assert not list(output.iterdir())
            elif kind == "symlink":
                assert output.is_symlink()
            else:
                assert not output.exists()
        finally:
            work.chmod(0o700)
        count += 1
    return {"guarded_paths_and_permissions": count}


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " population simulator " + name + ": passed", flush=True)
    return observations
