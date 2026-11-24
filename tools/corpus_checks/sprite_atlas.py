"""Whole-project sprite packing, exact original-pixel extraction and durable portable bundles."""

from __future__ import annotations

import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .atlas_fixture import (
    canonical,
    digest,
    inspect_extraction,
    inspect_svg,
    pattern,
    ppm,
    reference,
)
from .common import Application


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def settings(**changes: object) -> dict:
    return {"width": 10, "max_height": 32, "padding": 1, "order": "height", "background": [19, 37, 83]} | changes


def fixture(
    root: Path, sources: list[bytes] | None = None, layout: dict | None = None, names: list[str] | None = None
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    sources = (
        [ppm(pattern(4, 3, seed=1)), ppm(pattern(2, 5, seed=2)), ppm(pattern(2, 2, seed=3))]
        if sources is None
        else sources
    )
    names = [f"Sprite {i} — ✓" for i in range(len(sources))] if names is None else names
    sprites = []
    for i, (raw, name) in enumerate(zip(sources, names, strict=True)):
        filename = f"source-{i}.ppm"
        (root / filename).write_bytes(raw)
        sprites.append({"name": name, "path": filename})
    save(
        root / "sprites.json", {"version": 1, "settings": settings() if layout is None else layout, "sprites": sprites}
    )
    config = {"version": 1, "mode": "pack", "input": "sprites.json", "output": "output"}
    save(root / "atlas-job.json", config)
    return config


def inspect(root: Path, config: dict) -> dict:
    path = root / config["input"]
    definition = json.loads(path.read_bytes())
    sprites = (
        definition["sprites"]
        if config["mode"] == "verify"
        else [
            {"name": p["name"], "source_hex": (path.parent / p["path"]).read_bytes().hex()}
            for p in definition["sprites"]
        ]
    )
    atlas, results, extracted = reference(sprites, definition["settings"])
    archive = {"version": 1, "settings": definition["settings"], "sprites": sprites, "results": results}
    output = root / config["output"]
    assert (output / "archive.json").read_bytes() == canonical(archive)
    if config["mode"] == "verify":
        assert canonical(definition) == canonical(archive)
    assert (output / "atlas.ppm").read_bytes() == atlas
    actual_extracted = [(output / f"extracted-{i}.ppm").read_bytes() for i in range(len(sprites))]
    assert actual_extracted == extracted
    inspect_extraction(atlas, sprites, results, actual_extracted)
    svg, report = (output / "preview.svg").read_bytes(), (output / "report.json").read_bytes()
    inspect_svg(svg, atlas, results)
    assert canonical(json.loads(report)) == canonical({"version": 1, "mode": config["mode"], "results": results})
    files = {
        "atlas.ppm": atlas,
        "coordinates.json": canonical(results),
        "preview.svg": svg,
        "archive.json": canonical(archive),
        "report.json": report,
    }
    for i, original in enumerate(sprites):
        files[f"original-{i}.ppm"] = bytes.fromhex(original["source_hex"])
        files[f"extracted-{i}.ppm"] = extracted[i]
    for filename, prefix in [("sprites.json", "original"), ("extracted.json", "extracted")]:
        files[filename] = canonical(
            {
                "version": 1,
                "settings": definition["settings"],
                "sprites": [{"name": p["name"], "path": f"{prefix}-{i}.ppm"} for i, p in enumerate(sprites)],
            }
        )
    for filename, mode, source, destination in [
        ("repack.json", "pack", "sprites.json", "repacked"),
        ("pack-extracted.json", "pack", "extracted.json", "extracted"),
        ("replay.json", "verify", "archive.json", "replayed"),
    ]:
        files[filename] = canonical({"version": 1, "mode": mode, "input": source, "output": destination})
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    assert len(files) == 11 + 2 * len(sprites)
    assert files_at(output) == files and {p.name for p in output.iterdir()} == set(files)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "atlas-job.json") -> dict:
    imported = root / config["input"]
    paths = [root / selected, imported]
    if config["mode"] == "pack":
        paths += [imported.parent / row["path"] for row in json.loads(imported.read_bytes())["sprites"]]
    unchanged = {p: p.read_bytes() for p in paths}
    result = app.run(root, {"ATLAS_CONFIG": str(root / selected)}, timeout=240)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert (
        result.stdout
        == canonical(
            {
                "sprites": len(archive["sprites"]),
                "width": archive["results"]["width"],
                "height": archive["results"]["height"],
            }
        ).decode()
    )
    assert all(p.read_bytes() == raw for p, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=120)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".atlas-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, layout: dict, stem: str, reverse: bool = False) -> dict:
    unchanged = files_at(root)
    project = json.loads((root / "sprites.json").read_bytes())
    project["settings"] = layout
    if reverse:
        project["sprites"].reverse()
    save(root / (stem + "-sprites.json"), project)
    config = {"version": 1, "mode": "pack", "input": stem + "-sprites.json", "output": stem}
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in unchanged.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root, names=['A <&" title', "B 🐈", "C ✓"]))
    assert [(p["index"], p["x"], p["y"]) for p in archive["results"]["items"]] == [(1, 1, 1), (0, 5, 1), (2, 1, 8)]
    assert archive["results"]["height"] == 11
    assert consume(app, root / "output", "repack.json") == archive
    assert consume(app, root / "output", "replay.json") == archive
    extracted = consume(app, root / "output", "pack-extracted.json")
    assert extracted["results"]["atlas_sha256"] == archive["results"]["atlas_sha256"]
    original_order = edit_export(app, root / "output", settings(order="input"), "input-order")
    assert [(p["index"], p["x"], p["y"]) for p in original_order["results"]["items"]] == [
        (0, 1, 1),
        (1, 1, 6),
        (2, 7, 1),
    ]
    assert original_order["results"]["height"] == 12
    reversed_order = edit_export(app, root / "output", settings(), "reversed", reverse=True)
    assert reversed_order["results"]["atlas_sha256"] == archive["results"]["atlas_sha256"]
    cases = 0
    for maximum, padding, order in itertools.product([1, 2, 255, 256, 1023, 65535], [0, 2], ["input", "height"]):
        work = root / str(cases)
        sources = [ppm(pattern(3, 2, maximum, 1), maximum), ppm(pattern(2, 4, maximum, 2), maximum)]
        run(
            app,
            work,
            fixture(work, sources, settings(width=16, padding=padding, order=order, background=[maximum, 0, maximum])),
        )
        cases += 1
    tie = root / "ties"
    found = run(app, tie, fixture(tie, [ppm(pattern(2, 2))] * 4, settings(width=16, padding=0), ["é", "a", "Z", "🐈"]))
    assert [p["name"] for p in found["results"]["items"]] == ["Z", "a", "é", "🐈"]
    boundary = root / "raster-boundary"
    for i, first in enumerate([0, 9, 10, 11, 12, 13, 32, 35, 255]):
        work = boundary / str(i)
        run(
            app, work, fixture(work, [ppm([[(first, 35, 10)]], header=b"P6#name\r\n1 1\n255#end\n")], settings(width=3))
        )
    nested = root / "nested"
    config = fixture(nested)
    project = json.loads((nested / "sprites.json").read_bytes())
    for row in project["sprites"]:
        row["path"] = "../" + row["path"]
    (nested / "inner").mkdir()
    save(nested / "inner/sprites.json", project)
    config["input"] = "inner/sprites.json"
    save(nested / "atlas-job.json", config)
    run(app, nested, config)
    return {
        "manual_layouts": 2,
        "depth_padding_order_cases": cases,
        "raster_start_bytes": 9,
        "unicode_sort_and_escaping": True,
        "height_sort_permutation_invariance": True,
        "nested_manifest_paths": True,
        "actual_repack_extraction_replay": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(115)
    hashes, count = [], 0
    for i in range(20):
        maximum = rng.choice([15, 255, 256, 1023, 65535])
        sources = [
            ppm(pattern(rng.randint(1, 20), rng.randint(1, 24), maximum, rng.randrange(256)), maximum)
            for _ in range(rng.randint(1, 12))
        ]
        layout = settings(
            width=64,
            max_height=512,
            padding=rng.randint(0, 4),
            order="height" if i % 2 else "input",
            background=[rng.randint(0, maximum) for _ in range(3)],
        )
        work = root / str(i)
        first = run(app, work, fixture(work, sources, layout))
        assert consume(app, work / "output", "replay.json") == first
        extracted = consume(app, work / "output", "pack-extracted.json")
        assert extracted["results"]["atlas_sha256"] == first["results"]["atlas_sha256"]
        revised = edit_export(app, work / "output", dict(layout, order="height", width=80), "revised", reverse=True)
        assert consume(app, work / "output/revised", "replay.json") == revised
        ordered = edit_export(app, work / "output", dict(layout, order="height", width=80), "ordered")
        assert ordered["results"]["atlas_sha256"] == revised["results"]["atlas_sha256"]
        count += len(sources)
        hashes.extend([digest(canonical(first)), digest(canonical(revised))])
    return {
        "seed": 115,
        "generated_projects": 20,
        "primary_sprites": count,
        "extracted_pixels_repacked": 20,
        "reordered_relayout_replays": 20,
        "permutation_invariance_checks": 20,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    base = root / "base"
    config = fixture(base)
    project = json.loads((base / "sprites.json").read_bytes())
    cases = [("atlas-job.json", {k: v for k, v in config.items() if k != omitted}) for omitted in config]
    for key, values in {
        "version": [True, 1.0, 0],
        "mode": [None, "build"],
        "input": ["", None, "bad\0path"],
        "output": ["", None, "bad\0path"],
        "extra": [1],
    }.items():
        cases += [("atlas-job.json", dict(config, **{key: value})) for value in values]
    cases += [("sprites.json", {k: v for k, v in project.items() if k != omitted}) for omitted in project]
    for key, values in {
        "width": [0, 1025, True, 1.0],
        "max_height": [0, 1025, None],
        "padding": [-1, 17, False, 1.0],
        "order": ["optimal", True, None],
        "background": [[], [1, 2], [1, 2, 3, 4], [True, 2, 3], [-1, 2, 3], [256, 2, 3], [1.0, 2, 3], None],
        "extra": [1],
    }.items():
        cases += [
            ("sprites.json", dict(project, settings=dict(project["settings"], **{key: value}))) for value in values
        ]
    for omitted in project["settings"]:
        cases.append(
            ("sprites.json", dict(project, settings={k: v for k, v in project["settings"].items() if k != omitted}))
        )
    for name in ["", " ", "a" * 65, "bad\nname", "bad\x7fname", "bad\x9fname", None, 1]:
        cases.append(("sprites.json", dict(project, sprites=[{"name": name, "path": "source-0.ppm"}])))
    for sprites in [
        [],
        None,
        {},
        [project["sprites"][0]] * 65,
        [project["sprites"][0]] * 2,
        [{"name": "x"}],
        [{"path": "source-0.ppm"}],
        [{"name": "x", "path": "source-0.ppm", "extra": 1}],
    ]:
        cases.append(("sprites.json", dict(project, sprites=sprites)))
    for i, (filename, changed) in enumerate(cases):
        work = root / str(i)
        fixture(work)
        save(work / filename, changed)
        reject(app, work)
    packing_failures = [
        ([ppm(pattern(9, 3))], settings(width=4, max_height=16, padding=0), "sprite wider than atlas"),
        (
            [ppm(pattern(4, 4)), ppm(pattern(2, 2)), ppm(pattern(2, 2))],
            settings(width=6, max_height=4, padding=0),
            "shelf packing exceeds height",
        ),
        (
            [ppm(pattern(1, 1, 1), 1), ppm(pattern(1, 1, 2), 2)],
            settings(background=[0, 0, 0]),
            "sprite Maxval mismatch",
        ),
    ]
    for i, (sources, layout, needle) in enumerate(packing_failures):
        work = root / f"packing-{i}"
        fixture(work, sources, layout)
        reject(app, work, needle)
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
    for filename in ["atlas-job.json", "sprites.json", "archive.json"]:
        for i, raw in enumerate(malformed_json):
            work = root / (filename + str(i))
            fixture(work)
            if filename == "archive.json":
                save(work / "atlas-job.json", {"version": 1, "mode": "verify", "input": filename, "output": "output"})
            (work / filename).write_bytes(raw)
            reject(app, work)
    archive = run(app, base, config)
    paths = [
        (("version",), True),
        (("version",), 1.0),
        (("sprites", 0, "source_hex"), None),
        (("sprites", 0, "source_hex"), archive["sprites"][0]["source_hex"].upper()),
        (("sprites", 0, "source_hex"), " " + archive["sprites"][0]["source_hex"]),
        (("sprites", 0, "source_hex"), archive["sprites"][0]["source_hex"][:-1]),
        (("sprites", 0, "name"), "tampered"),
        (("settings", "padding"), 0),
        (("results", "width"), 10.0),
        (("results", "source_pixels"), True),
        (("results", "atlas_sha256"), "0" * 64),
        (("results", "raster_sha256"), "0" * 64),
        (("results", "background_pixels"), 0),
        (("results", "shelves", 0, "used_width"), 0),
        (("results", "items", 0, "x"), 0),
        (("results", "items", 0, "shelf"), 1),
        (("results", "items", 0, "extracted_sha256"), "0" * 64),
        (("results", "items", 0, "source_sha256"), "0" * 64),
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
        save(work / "atlas-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests_manifests_settings": len(cases),
        "packing_policy_failures": len(packing_failures),
        "malformed_json_per_input": len(malformed_json),
        "tampered_archives": len(altered),
        "strict_cached_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    maximum = ppm(pattern(256, 256, 65535), 65535)
    work = root / "maximum-area-pixels"
    found = run(app, work, fixture(work, [maximum] * 16, settings(width=1024, max_height=1024, padding=0)))
    assert found["results"]["width"] == found["results"]["height"] == 1024
    assert found["results"]["source_pixels"] == 1048576 and found["results"]["background_pixels"] == 0
    work = root / "maximum-padding"
    run(app, work, fixture(work, [ppm(pattern(224, 224))] * 16, settings(width=1024, max_height=1024, padding=16)))
    work = root / "over-pixels"
    fixture(work, [maximum] * 16 + [ppm([[(1, 2, 3)]], 65535)], settings(width=1024, max_height=1024, padding=0))
    reject(app, work, "combined source pixel limit")
    for axis, header in [("width", b"P6\n257 1\n255\n"), ("height", b"P6\n1 257\n255\n")]:
        work = root / ("over-" + axis)
        fixture(work, [header])
        reject(app, work, "image dimension limit")

    # Exact combined byte budget from independently sized valid P6 headers, without exhausting pixel budget.
    def padded(width: int, height: int, header_bytes: int) -> bytes:
        suffix = f"\n{width} {height}\n65535\n".encode()
        header = b"P6\n#" + b"x" * (header_bytes - 4 - len(suffix)) + suffix
        return ppm(pattern(width, height, 65535), 65535, header)

    sources = [padded(128, 171, 65536)] * 32 + [padded(1, 1, 65536)] * 31 + [padded(1, 1, 57152)]
    assert sum(map(len, sources)) == 8388608
    work = root / "maximum-bytes-count"
    config = fixture(
        work,
        sources,
        settings(width=1024, max_height=1024, padding=0),
        [str(i).zfill(2) + "🐈" * 62 for i in range(64)],
    )
    for filename in ["atlas-job.json", "sprites.json"]:
        path = work / filename
        path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config)
    assert consume(app, work / "output", "replay.json") == archive
    work = root / "over-combined-bytes"
    fixture(work, sources[:-1] + [padded(1, 1, 57153)], settings(width=1024, max_height=1024, padding=0))
    reject(app, work, "combined source byte limit")
    work = root / "maximum-source"
    raw = padded(256, 256, 65536)
    assert len(raw) == 458752
    run(app, work, fixture(work, [raw], settings(width=256, max_height=256, padding=0)))
    work = root / "over-header"
    fixture(work, [padded(1, 1, 65537)])
    reject(app, work, "header byte limit")
    for name, size in [("atlas-job.json", 65536), ("sprites.json", 65536), ("source-0.ppm", 524288)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work, "input byte limit")
    baseline = root / "baseline"
    archive = run(app, baseline, fixture(baseline))
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-exact")
        fixture(work)
        config = {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"}
        save(work / "atlas-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(33554432 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config)
    work = root / "over-hex"
    fixture(work)
    save(work / "atlas-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
    archive["sprites"][0]["source_hex"] = "00" * 524289
    save(work / "archive.json", archive)
    reject(app, work, "image byte limit")
    return {
        "sprite_axis": 256,
        "sprite_pixels": 65536,
        "combined_pixels": 1048576,
        "atlas_axis": 1024,
        "padding": 16,
        "sprites": 64,
        "name_codepoints": 64,
        "header_bytes": 65536,
        "maximum_valid_source_bytes": 458752,
        "combined_source_bytes": 8388608,
        "request_manifest_bytes": 65536,
        "archive_bytes": 33554432,
        "defensive_unreachable_limits": ["source_bytes_524288", "export_bytes_33554432"],
        "maximum_bundle_replayed": True,
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
        fixture(work, [source])
        reject(app, work)
    return {
        "all_proper_prefixes": len(raw),
        "other_malformed_images": len(bad) - len(raw),
        "binary_boundary_and_sample_range_checked": True,
        "multi_image_and_trailing_data_rejected": True,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work)
        result = app.run(work, {"ATLAS_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".atlas-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in [
        "request",
        "project",
        "source-0.ppm",
        "source-1.ppm",
        "source-2.ppm",
        "competitor",
        "kill-staged",
        "kill-published",
    ]:
        work = root / mutation
        config = fixture(work)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"ATLAS_PAUSE": stage, "ATLAS_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".atlas-*"))) == (1 if stage == "staged" else 0)
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
                    name = {"request": "atlas-job.json", "project": "sprites.json"}.get(mutation, mutation)
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".atlas-*"))
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
        "input_output_races": 6,
        "retry_after_hard_kill": True,
        "complete_or_absent_final_bundle": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["atlas-job.json", "sprites.json", "source-0.ppm", "source-1.ppm", "source-2.ppm"],
        ["symlink", "hardlink", "fifo", "directory", "unreadable"],
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
            output.symlink_to(work / "atlas-job.json")
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
        print(app.engine + " sprite atlas " + name + ": passed", flush=True)
    return observations
