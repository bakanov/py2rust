"""Whole-project P6 filtering, exact sample/histogram oracles and portable native exports."""

from __future__ import annotations

import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .ppm_fixture import (
    canonical,
    digest,
    inspect_csv,
    inspect_svg,
    pattern,
    ppm,
    read_ppm,
    reference,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def crop(x: int, y: int, width: int, height: int) -> dict:
    return {"op": "crop", "x": x, "y": y, "width": width, "height": height}


def threshold(value: int, mode: str = "channel") -> dict:
    return {"op": "threshold", "value": value, "mode": mode}


def fixture(root: Path, source: bytes | None = None, pipeline: list[dict] | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "mode": "process",
        "input": "source.ppm",
        "output": "output",
        "pipeline": [crop(1, 1, 3, 2), {"op": "invert"}, threshold(100, "mean")] if pipeline is None else pipeline,
    }
    save(root / "ppm-job.json", config)
    (root / "source.ppm").write_bytes(ppm(pattern(5, 4, seed=17)) if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = (root / config["input"]).read_bytes()
    if config["mode"] == "verify":
        original = json.loads(imported)
        source, pipeline = bytes.fromhex(original["source_hex"]), original["pipeline"]
    else:
        source, pipeline = imported, config["pipeline"]
    before, after, results = reference(source, pipeline)
    archive = {"version": 1, "source_hex": source.hex(), "pipeline": pipeline, "results": results}
    directory = root / config["output"]
    assert (directory / "archive.json").read_bytes() == canonical(archive)
    if config["mode"] == "verify":
        assert canonical(original) == canonical(archive)
    maximum = results["output"]["maxval"]
    filtered = ppm(after, maximum)
    assert (directory / "filtered.ppm").read_bytes() == filtered
    assert read_ppm(filtered)[0] == after
    csv = (directory / "histogram.csv").read_bytes()
    svg = (directory / "preview.svg").read_bytes()
    report = (directory / "report.json").read_bytes()
    inspect_csv(csv, results)
    inspect_svg(svg, before, after, maximum)
    assert canonical(json.loads(report)) == canonical({"version": 1, "mode": config["mode"], "results": results})
    files = {
        "original.ppm": source,
        "filtered.ppm": filtered,
        "archive.json": canonical(archive),
        "report.json": report,
        "preview.svg": svg,
        "histogram.csv": csv,
        "process.json": canonical(
            {"version": 1, "mode": "process", "input": "original.ppm", "pipeline": pipeline, "output": "processed"}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "ppm-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"PPM_CONFIG": str(root / selected)}, timeout=180)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert (
        result.stdout == canonical({k: archive["results"]["output"][k] for k in ["width", "height", "maxval"]}).decode()
    )
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".ppm-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, pipeline: list[dict], stem: str, source: bytes | None = None) -> dict:
    original = files_at(root)
    config = json.loads((root / "process.json").read_bytes())
    config.update(pipeline=pipeline, output=stem)
    if source is not None:
        config["input"] = stem + ".ppm"
        (root / config["input"]).write_bytes(source)
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    assert consume(app, root / "output", "process.json") == archive
    assert consume(app, root / "output", "replay.json") == archive
    cases = []
    for maximum in [1, 2, 15, 255, 256, 257, 1023, 65535]:
        grid = [[(0, maximum // 2, maximum), (maximum, 1, 0)]]
        for pipeline in [[], [{"op": "invert"}], [threshold(maximum // 2)], [threshold(maximum // 2, "mean")]]:
            cases.append((ppm(grid, maximum), pipeline))
    grid = [[(10, 35, 32), (9, 13, 255)]]
    # Every ASCII whitespace as raster delimiter; first raster bytes themselves look like header syntax.
    for separator in b" \t\r\n\v\f":
        cases.append((ppm(grid, header=b"P6\n2 1\n255" + bytes([separator])), []))
    headers = [
        b"P6#magic\r\n2#width\n1\t255#maxval\n",
        b"P6 \v\f#before\r2\t#height\n1\r255\n",
        b"P6\n00002 00001\n00255\n",
        b"P6\n2 1\n255\r",
    ]
    cases += [(ppm(grid, header=header), []) for header in headers]
    # Header ends at CR; LF is the red sample. A conventional CRLF header would add one raster byte and be rejected.
    for i, (source, pipeline) in enumerate(cases):
        work = root / str(i)
        run(app, work, fixture(work, source, pipeline))
    goldens = [
        ([[(2, 3, 4), (3, 3, 2), (4, 4, 1)]], [threshold(3, "mean")], [[(7, 7, 7), (0, 0, 0), (7, 7, 7)]]),
        ([[(2, 3, 4)]], [threshold(3)], [[(0, 7, 7)]]),
        ([[(0, 3, 7)]], [{"op": "invert"}], [[(7, 4, 0)]]),
        ([[(1, 2, 3), (4, 5, 6)], [(7, 0, 1), (2, 3, 4)]], [crop(1, 0, 1, 2)], [[(4, 5, 6)], [(2, 3, 4)]]),
    ]
    for i, (pixels, pipeline, expected) in enumerate(goldens):
        work = root / f"golden-{i}"
        run(app, work, fixture(work, ppm(pixels, 7), pipeline))
        assert read_ppm((work / "output/filtered.ppm").read_bytes())[0] == expected
    values = [[(y * 256 + x,) * 3 for x in range(256)] for y in range(256)]
    for i, pipeline in enumerate([[{"op": "invert"}], [threshold(32768)], [threshold(32768, "mean")]]):
        work = root / f"all-u16-{i}"
        run(app, work, fixture(work, ppm(values, 65535), pipeline))
    return {
        "depth_header_and_boundary_cases": len(cases),
        "manual_pixel_goldens": len(goldens),
        "exhaustive_u16_values_per_channel": 65536,
        "exhaustive_pipelines": 3,
        "exact_histograms_csv_and_svg": True,
        "actual_process_replay_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(114)
    hashes, pixels = [], 0
    for i in range(18):
        width, height, maximum = rng.randint(3, 25), rng.randint(3, 25), rng.choice([15, 255, 256, 1023, 65535])
        source = ppm(pattern(width, height, maximum, rng.randint(0, 255)), maximum)
        pipeline = [
            crop(1, 1, width - 1, height - 1),
            {"op": "invert"},
            threshold(rng.randint(0, maximum), "mean" if i % 2 else "channel"),
        ]
        work = root / str(i)
        first = run(app, work, fixture(work, source, pipeline))
        assert consume(app, work / "output", "replay.json") == first
        # Inversion is an involution; cropping composes; thresholding actual exported output is idempotent.
        double = edit_export(app, work / "output", [{"op": "invert"}] * 2, "double")
        assert double["results"]["input"]["raster_sha256"] == double["results"]["output"]["raster_sha256"]
        once = edit_export(app, work / "output", [crop(2, 2, width - 2, height - 2)], "once")
        twice = edit_export(
            app, work / "output", [crop(1, 1, width - 1, height - 1), crop(1, 1, width - 2, height - 2)], "twice"
        )
        assert once["results"]["output"] == twice["results"]["output"]
        stable = edit_export(
            app, work / "output", [pipeline[-1]], "stable", (work / "output/filtered.ppm").read_bytes()
        )
        assert stable["results"]["output"]["raster_sha256"] == first["results"]["output"]["raster_sha256"]
        pixels += width * height
        hashes.extend([digest(canonical(first)), digest(canonical(once))])
    # Order matters: threshold then invert differs from invert then threshold at the equality boundary.
    work = root / "order"
    base = run(app, work, fixture(work, ppm([[(100, 100, 100)]]), [threshold(100), {"op": "invert"}]))
    reordered = edit_export(app, work / "output", [{"op": "invert"}, threshold(100)], "reordered")
    assert base["results"]["output"]["raster_sha256"] != reordered["results"]["output"]["raster_sha256"]
    return {
        "seed": 114,
        "generated_cases": 18,
        "source_pixels": pixels,
        "inversion_involution": 18,
        "crop_composition": 18,
        "threshold_idempotence": 18,
        "filter_order_checked": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def malformed(app: Application, root: Path) -> dict:
    raw = ppm(pattern(2, 2))
    bad = [raw[:n] for n in range(len(raw))]
    bad += [
        b"P3\n1 1\n255\n\0\0\0",
        b"P61 1\n255\n\0\0\0",
        raw + b" ",
        raw + raw,
        b"P6\n1 1\n255\r\n\0\0\0",
        b"P6\n1 1\n255#unterminated",
        b"P6\n1 1\n255x\0\0\0",
        b"P6\n1 1\n255\n#\0",
        b"P6\n1 1\n256\n\0\1\0\2\0",
        b"P6\n1 1\n1\n\0\1\2",
        b"P6\n1 1\n256\n\x01\x01\0\0\0\0",
        b"P6\n1\xff1\n255\n\0\0\0",
        b"P6\n#end",
    ]
    for field in range(3):
        for token in [b"0", b"-1", b"+1", b"1.0", b"000001", b"999999999999999999999999", b"x", b"\xff"]:
            fields = [b"1", b"1", b"255"]
            fields[field] = token
            bad.append(b"P6\n" + b" ".join(fields) + b"\n\0\0\0")
    for maxval in [b"65536", b"99999"]:
        bad.append(b"P6\n1 1\n" + maxval + b"\n\0\0\0\0\0\0")
    for i, source in enumerate(bad):
        work = root / str(i)
        fixture(work, source, [])
        reject(app, work)
    return {
        "all_proper_prefixes": len(raw),
        "other_malformed_images": len(bad) - len(raw),
        "binary_boundary_and_sample_range_checked": True,
        "multi_image_and_trailing_data_rejected": True,
    }


def invalid(app: Application, root: Path) -> dict:
    base = root / "base"
    config = fixture(base)
    cases = [{k: v for k, v in config.items() if k != omitted} for omitted in config]
    for key, values in {
        "version": [True, 1.0, 0],
        "mode": [None, "filter"],
        "input": ["", None, "bad\0path"],
        "output": ["", None, "bad\0path"],
        "pipeline": [None, {}, "invert", [None], [True], [{"op": "blur"}], [{"op": "invert", "extra": 1}]],
        "extra": [1],
    }.items():
        cases.extend(dict(config, **{key: value}) for value in values)
    operations = [crop(0, 0, 5, 4), threshold(100), {"op": "invert"}]
    for op in operations:
        for key in op:
            cases.append(dict(config, pipeline=[{k: v for k, v in op.items() if k != key}]))
    for key, values in {
        "x": [-1, 5, True, 1.0],
        "y": [-1, 4, False],
        "width": [0, -1, 6, None],
        "height": [0, -1, 5, 1.0],
    }.items():
        cases.extend(dict(config, pipeline=[dict(crop(0, 0, 5, 4), **{key: value})]) for value in values)
    for key, values in {"value": [-1, 256, True, 1.0, None], "mode": ["luma", True, None]}.items():
        cases.extend(dict(config, pipeline=[dict(threshold(100), **{key: value})]) for value in values)
    cases += [
        dict(config, pipeline=[crop(0, 0, 1, 1), crop(1, 0, 1, 1)]),
        dict(config, pipeline=[{"op": "invert"}] * 33),
    ]
    for i, changed in enumerate(cases):
        work = root / str(i)
        fixture(work)
        save(work / "ppm-job.json", changed)
        reject(app, work)
    malformed_json = [
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
    for filename in ["ppm-job.json", "archive.json"]:
        for i, raw in enumerate(malformed_json):
            work = root / (filename + str(i))
            fixture(work)
            if filename == "archive.json":
                save(work / "ppm-job.json", {"version": 1, "mode": "verify", "input": filename, "output": "output"})
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
        (("pipeline", 2, "value"), 101),
        (("results", "processed_pixels"), 0),
        (("results", "input", "width"), 5.0),
        (("results", "input", "histogram", "red", 0), True),
        (("results", "output", "histogram", "blue", 0), 1),
        (("results", "output", "file_sha256"), "0" * 64),
        (("results", "output", "raster_sha256"), "0" * 64),
        (("results", "steps", 0, "filter", "x"), 0),
        (("results", "steps", 1, "raster_sha256"), "0" * 64),
        (("results",), None),
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
        save(work / "ppm-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests_and_filters": len(cases),
        "malformed_json_per_input": len(malformed_json),
        "tampered_archives": len(altered),
        "strict_cached_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    suffix = b"\n1024 256\n65535\n"
    header = b"P6\n#" + b"x" * (65536 - 4 - len(suffix)) + suffix
    maximum = ppm(pattern(1024, 256, 65535), 65535, header)
    assert len(header) == 65536 and len(maximum) == 1638400
    work = root / "maximum-image-header"
    config = fixture(work, maximum, [])
    path = work / "ppm-job.json"
    path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config)
    assert consume(app, work / "output", "replay.json") == archive
    for label, source, needle in [
        ("over-width", b"P6\n1025 1\n255\n", "image dimension limit"),
        ("over-height", b"P6\n1 1025\n255\n", "image dimension limit"),
        ("over-pixels", b"P6\n1024 257\n65535\n", "image pixel limit"),
        ("over-header-comment", maximum[:4] + b"x" + maximum[4:], "header byte limit"),
        ("over-header-space", b"P6\n" + b" " * 65536 + b"1 1\n255\n\0\0\0", "header byte limit"),
    ]:
        work = root / label
        fixture(work, source, [])
        reject(app, work, needle)
    work = root / "maximum-height"
    run(app, work, fixture(work, ppm(pattern(1, 1024)), []))
    work = root / "maximum-steps"
    run(app, work, fixture(work, ppm([[(0, 127, 255)]]), [{"op": "invert"}] * 32))
    source = ppm(pattern(1024, 256))
    work = root / "exact-work"
    found = run(app, work, fixture(work, source, [{"op": "invert"}] * 15))
    assert found["results"]["processed_pixels"] == 4194304
    work = root / "over-work"
    fixture(work, source, [{"op": "invert"}] * 16)
    reject(app, work, "processing pixel budget")
    for name, size in [("ppm-job.json", 65536), ("source.ppm", 2097152)]:
        work = root / ("over-" + name)
        fixture(work, pipeline=[])
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work, "input byte limit")
    baseline = root / "baseline"
    archive = run(app, baseline, fixture(baseline, pipeline=[]))
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-exact")
        fixture(work)
        config = {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"}
        save(work / "ppm-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config)
    work = root / "over-hex"
    fixture(work)
    save(work / "ppm-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
    save(work / "archive.json", dict(archive, source_hex="00" * 2097153))
    reject(app, work, "source byte limit")
    return {
        "image_axis": 1024,
        "image_pixels": 262144,
        "maximum_maxval": 65535,
        "header_bytes": 65536,
        "maximum_valid_source_bytes": 1638400,
        "request_bytes": 65536,
        "archive_bytes": 16777216,
        "pipeline_steps": 32,
        "processed_pixels": 4194304,
        "defensive_unreachable_limits": ["source_bytes_2097152", "export_bytes_16777216"],
        "dimensions_rejected_before_raster_allocation": True,
        "maximum_image_replayed": True,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work)
        result = app.run(work, {"PPM_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".ppm-*")) and (work / "output").exists() == (stage == "published")
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
            env=app.environment({"PPM_PAUSE": stage, "PPM_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".ppm-*"))) == (1 if stage == "staged" else 0)
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
                    name = "ppm-job.json" if mutation == "request" else "source.ppm"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".ppm-*"))
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
        ["ppm-job.json", "source.ppm"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "ppm-job.json")
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
        ("malformed", malformed),
        ("invalid", invalid),
        ("limits", limits),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " PPM filters " + name + ": passed", flush=True)
    return observations
