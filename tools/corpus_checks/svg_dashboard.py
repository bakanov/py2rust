"""Whole-project numeric, markup, replay and atomic publication acceptance for SVG dashboards."""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .dashboard_fixture import (
    canonical,
    chart,
    dataset,
    digest,
    inspect_html,
    inspect_results,
    inspect_svg,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None, columns: int = 2) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "render", "input": "data.json", "output": "output", "columns": columns}
    save(root / "dashboard-job.json", config)
    save(root / "data.json", dataset() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = (root / config["input"]).read_bytes()
    if config["mode"] == "verify":
        original = json.loads(imported)
        source, columns = bytes.fromhex(original["source_hex"]), original["columns"]
    else:
        source, columns = imported, config["columns"]
    directory = root / config["output"]
    archive = json.loads((directory / "archive.json").read_bytes())
    assert archive.keys() == {"version", "source_hex", "columns", "results"}
    assert type(archive["version"]) is int and archive["version"] == 1
    assert archive["source_hex"] == source.hex() and type(archive["columns"]) is int and archive["columns"] == columns
    results = archive["results"]
    inspect_results(json.loads(source), columns, results)
    if config["mode"] == "verify":
        assert canonical(original) == canonical(archive)
    svg, html, report = [(directory / name).read_bytes() for name in ["dashboard.svg", "index.html", "report.json"]]
    inspect_svg(svg, results)
    inspect_html(html, svg)
    assert canonical(json.loads(report)) == canonical({"version": 1, "mode": config["mode"], "results": results})
    files = {
        "data.json": source,
        "archive.json": canonical(archive),
        "report.json": report,
        "dashboard.svg": svg,
        "index.html": html,
        "render.json": canonical(
            {"version": 1, "mode": "render", "input": "data.json", "output": "rendered", "columns": columns}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "dashboard-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"DASHBOARD_CONFIG": str(root / selected)}, timeout=180)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert result.stdout == canonical({k: archive["results"][k] for k in ["width", "height"]}).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".dashboard-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: dict, columns: int, stem: str) -> dict:
    original = files_at(root)
    config = json.loads((root / "render.json").read_bytes())
    config.update(columns=columns, output=stem, input=stem + "-data.json")
    save(root / config["input"], source)
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    assert consume(app, root / "output", "render.json") == archive
    assert consume(app, root / "output", "replay.json") == archive
    cases = [dataset([])]
    for kind in ["bar", "line"]:
        for values in [[], [0], [-0.0, 0.0], [5], [-5], [5, 5], [-5, -5], [-100, 0, 100], [-9, -7, -2]]:
            cases.append(dataset([chart(kind, values, kind)]))
        for power in [-12, -9, -6, -3, 0, 3, 6, 9, 12]:
            value = float("1e" + str(power))
            cases.append(dataset([chart("magnitude", [-value, value], kind)]))
        for power in [-9, -3, 0, 6, 11]:
            value = float("1e" + str(power))
            for close in [math.nextafter(value, math.inf), value * (1 + 0.9e-12), value * (1 + 1.1e-12)]:
                cases.append(dataset([chart("close", [value, close], kind)]))
    for power in [-11, -5, 0, 5, 10]:
        for factor in [1, 2, 5]:
            boundary = factor * 4 * 10.0**power
            for value in [math.nextafter(boundary, 0), boundary, math.nextafter(boundary, math.inf)]:
                cases.append(dataset([chart("boundary", [0, value])]))
    for i, source in enumerate(cases):
        work = root / str(i)
        run(app, work, fixture(work, source, i % 3 + 1))
    # Hand-calculated axes and pixel coordinates, independent of the numeric checker.
    goldens = [
        ("bar", [-100, 0, 100], (-100.0, 100.0, 50.0), [(246, 304), (391, 204), (536, 104)]),
        ("line", [0, 100], (-50.0, 150.0, 50.0), [(174, 254), (608, 154)]),
        ("line", [5], (4.6000000000000005, 5.4, 0.2), [(391, 204)]),
        ("bar", [0, -0.0], (-1.0, 1.0, 0.5), [(283, 204), (500, 204)]),
    ]
    for i, (kind, values, axis, points) in enumerate(goldens):
        work = root / ("golden-" + str(i))
        result = run(app, work, fixture(work, dataset([chart("golden", values, kind)])))["results"]["charts"][0]
        assert tuple(result[k] for k in ["low", "high", "step"]) == axis, result
        assert [(p["x"], p["y"]) for p in result["points"]] == points
    malicious = '<script>alert("x")</script>&\' 🐍 日本語 е́'
    source = dataset([chart("<id>&\"'", [1, 2, 0], title=malicious, unit="<&\"' 東京")], malicious)
    for point in source["charts"][0]["points"]:
        point["label"] = malicious
    work = root / "escaping"
    run(app, work, fixture(work, source))
    return {
        "numeric_and_degenerate_cases": len(cases),
        "manual_geometry_goldens": len(goldens),
        "xml_html_injection_and_unicode": True,
        "zero_markers_checked": True,
        "actual_render_replay_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(116)
    hashes, total = [], 0
    for i in range(20):
        rows = []
        for j in range(rng.randint(1, 12)):
            values = [rng.randint(-100000, 100000) / 10.0 ** rng.randint(0, 6) for _ in range(rng.randint(0, 128))]
            rows.append(chart("chart-" + str(j), values, rng.choice(["bar", "line"])))
            total += len(values)
        source = dataset(rows)
        columns = i % 3 + 1
        work = root / str(i)
        original = run(app, work, fixture(work, source, columns))
        assert consume(app, work / "output", "replay.json") == original
        changed = json.loads(canonical(source))
        changed["charts"].reverse()
        for row in changed["charts"]:
            row["points"].reverse()
        reversed_archive = edit_export(app, work / "output", changed, 4 - columns, "reversed")
        old = {r["id"]: r for r in original["results"]["charts"]}
        for row in reversed_archive["results"]["charts"]:
            before = old[row["id"]]
            assert all(canonical(row[k]) == canonical(before[k]) for k in ["low", "high", "step", "ticks", "zero_y"])
            assert [p["y"] for p in row["points"]] == [p["y"] for p in reversed(before["points"])]
        restored = edit_export(app, work / "output/reversed", source, columns, "restored")
        assert restored == original
        hashes.append(digest(canonical(original)))
    # Exact decimal decades retain geometry on a fixture away from rounding boundaries.
    simple = dataset([chart("scale", [-80, -20, 0, 40, 80]), chart("line", [20, 40, 80], "line")])
    baseline = root / "scale-base"
    original = run(app, baseline, fixture(baseline, simple))
    for power in [-9, -3, 3, 9]:
        scaled = json.loads(canonical(simple))
        for row in scaled["charts"]:
            for point in row["points"]:
                point["value"] *= 10.0**power
        found = edit_export(app, baseline / "output", scaled, 2, "scaled-" + str(power))
        for before, after in zip(original["results"]["charts"], found["results"]["charts"]):
            assert [(p["x"], p["y"]) for p in before["points"]] == [(p["x"], p["y"]) for p in after["points"]]
    return {
        "seed": 116,
        "generated_projects": 20,
        "source_points": total,
        "reversal_relayout_and_restoration": 20,
        "decimal_scale_covariance": 4,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    base = root / "base"
    config = fixture(base)
    request_cases = [{k: v for k, v in config.items() if k != omitted} for omitted in config]
    for key, values in {
        "version": [True, 1.0, 0],
        "mode": [None, "draw"],
        "input": ["", None, "bad\0path"],
        "output": ["", None, "bad\0path"],
        "columns": [0, 4, True, 1.0, None],
        "extra": [1],
    }.items():
        request_cases.extend(dict(config, **{key: value}) for value in values)
    for i, changed in enumerate(request_cases):
        work = root / ("request-" + str(i))
        fixture(work)
        save(work / "dashboard-job.json", changed)
        reject(app, work)
    source = dataset([chart("first", [1])])
    datasets = []
    for path in [(), ("charts", 0), ("charts", 0, "points", 0)]:
        node = source
        for key in path:
            node = node[key]
        for omitted in [*node, None]:
            changed = json.loads(canonical(source))
            target = changed
            for key in path:
                target = target[key]
            if omitted is None:
                target["extra"] = 1
            else:
                del target[omitted]
            datasets.append(changed)
    bad_fields = [
        (("version",), [False, 1.0, 2]),
        (("title",), [None, "", " ", "x" * 121]),
        (("charts",), [None, {}, [None], source["charts"] * 13, source["charts"] * 2]),
        (("charts", 0, "id"), [None, "", " ", "x" * 33]),
        (("charts", 0, "title"), [None, "", "x" * 121]),
        (("charts", 0, "kind"), [None, "pie", True]),
        (("charts", 0, "unit"), [None, "x" * 33]),
        (("charts", 0, "points"), [None, {}, [None], [{"label": "", "value": 1}] * 129]),
        (("charts", 0, "points", 0, "label"), [None, "x" * 121]),
        (
            ("charts", 0, "points", 0, "value"),
            [
                None,
                True,
                "1",
                [],
                {},
                1e13,
                -1e13,
                1e-13,
                -1e-13,
                math.nextafter(1e12, math.inf),
                math.nextafter(1e-12, 0),
            ],
        ),
    ]
    for path, values in bad_fields:
        for value in values:
            changed = json.loads(canonical(source))
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            datasets.append(changed)
    for code in [0, 9, 10, 13, 31, 127, 128, 159, 0xFFFE, 0xFFFF, 0x1FFFE, 0x10FFFF]:
        for path in [("title",), ("charts", 0, "id"), ("charts", 0, "points", 0, "label")]:
            changed = json.loads(canonical(source))
            target = changed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = "bad" + chr(code)
            datasets.append(changed)
    for i, changed in enumerate(datasets):
        work = root / ("data-" + str(i))
        fixture(work, changed)
        reject(app, work)
    malformed = [
        b"{",
        b"[]",
        b"null",
        b'{"version":1,"version":1}',
        b"{}{}",
        b"\xff",
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":"\\ud800"}',
    ]
    for filename in ["dashboard-job.json", "data.json", "archive.json"]:
        for i, raw in enumerate(malformed):
            work = root / (filename + str(i))
            fixture(work)
            if filename == "archive.json":
                save(
                    work / "dashboard-job.json", {"version": 1, "mode": "verify", "input": filename, "output": "output"}
                )
            (work / filename).write_bytes(raw)
            reject(app, work)
    archive = run(app, base, config)
    paths = [
        (("version",), True),
        (("version",), 1.0),
        (("source_hex",), None),
        (("source_hex",), archive["source_hex"].upper()),
        (("source_hex",), " " + archive["source_hex"]),
        (("source_hex",), archive["source_hex"][:-1]),
        (("columns",), True),
        (("columns",), 4),
        (("results",), None),
        (("results", "width"), 1352.0),
        (("results", "title"), "tampered"),
        (("results", "charts", 0, "low"), -20),
        (("results", "charts", 0, "step"), math.nextafter(50.0, math.inf)),
        (("results", "charts", 0, "ticks", 0, "label"), "wrong"),
        (("results", "charts", 0, "points", 0, "x"), 0),
        (("results", "charts", 0, "points", 0, "value"), -20),
        (("results", "charts", 0, "points", 0, "value"), math.nextafter(-20.0, math.inf)),
        (("results", "charts", 0, "points", 0, "label_visible"), 1),
    ]
    altered = []
    for path, value in paths:
        changed = json.loads(canonical(archive))
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        altered.append(changed)
    altered += [{k: v for k, v in archive.items() if k != omitted} for omitted in archive]
    altered.append(dict(archive, extra=1))
    for i, changed in enumerate(altered):
        work = root / ("tampered-" + str(i))
        fixture(work)
        save(work / "dashboard-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests": len(request_cases),
        "invalid_datasets": len(datasets),
        "malformed_json_per_input": len(malformed),
        "tampered_archives": len(altered),
        "strict_cached_types_and_one_ulp_changes": True,
    }


def limits(app: Application, root: Path) -> dict:
    rows = [
        chart(
            "x" * 30 + str(i),
            [(-1 if j % 2 else 1) * 1e12 for j in range(128)],
            "line" if i % 2 else "bar",
            "東京🐍" * 40,
            "u" * 32,
        )
        for i in range(12)
    ]
    for row in rows:
        for point in row["points"]:
            point["label"] = "日本🌐" * 40
    work = root / "maximum"
    config = fixture(work, dataset(rows, "x" * 120), 3)
    for name, size in [("dashboard-job.json", 65536), ("data.json", 2097152)]:
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size, b" "))
        assert path.stat().st_size == size
    archive = run(app, work, config)
    assert consume(app, work / "output", "replay.json") == archive
    for name, size in [("dashboard-job.json", 65536), ("data.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work, "input byte limit")
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-exact")
        fixture(work)
        config = {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"}
        save(work / "dashboard-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config)
    work = root / "over-hex"
    fixture(work)
    save(work / "dashboard-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
    save(work / "archive.json", dict(archive, source_hex="00" * 2097153))
    reject(app, work, "source byte limit")
    return {
        "charts": 12,
        "points_per_chart": 128,
        "title_and_point_label_characters": 120,
        "unit_characters": 32,
        "columns": 3,
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
        "maximum_replayed": True,
        "defensive_export_limit_bytes": 16777216,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work)
        result = app.run(work, {"DASHBOARD_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".dashboard-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "source", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"DASHBOARD_PAUSE": stage, "DASHBOARD_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".dashboard-*"))) == (1 if stage == "staged" else 0)
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
                    name = "dashboard-job.json" if mutation == "request" else "data.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".dashboard-*"))
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
        ["dashboard-job.json", "data.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "dashboard-job.json")
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
        print(app.engine + " SVG dashboard " + name + ": passed", flush=True)
    return observations
