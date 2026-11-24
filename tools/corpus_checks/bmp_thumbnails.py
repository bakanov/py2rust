"""Complete BMP projects: independent pixel rendering, portable exports and atomic publication."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import struct
import subprocess
from pathlib import Path

from .bmp_fixture import (
    bitmap,
    canonical,
    digest,
    inspect_preview,
    pattern,
    read_bitmap,
    reference,
)
from .common import Application


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def layout(**changes: object) -> dict:
    return {
        "box_width": 7,
        "box_height": 5,
        "columns": 2,
        "margin": 2,
        "gap": 3,
        "fit": "contain",
        "background": [19, 37, 83],
    } | changes


def fixture(
    root: Path, sources: list[bytes] | None = None, settings: dict | None = None, names: list[str] | None = None
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    originals = (
        [bitmap(pattern(3, 2)), bitmap(pattern(2, 5, 17), dib=108, top_down=True), bitmap(pattern(5, 3, 81), dib=12)]
        if sources is None
        else sources
    )
    labels = [f"Image {i} — ✓" for i in range(len(originals))] if names is None else names
    images = []
    for i, (raw, name) in enumerate(zip(originals, labels, strict=True)):
        filename = f"source-{i}.bmp"
        (root / filename).write_bytes(raw)
        images.append({"name": name, "path": filename})
    save(
        root / "project.json", {"version": 1, "settings": layout() if settings is None else settings, "images": images}
    )
    config = {"version": 1, "mode": "build", "input": "project.json", "output": "output"}
    save(root / "bmp-job.json", config)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = root / config["input"]
    definition = json.loads(imported.read_bytes())
    if config["mode"] == "verify":
        originals = definition["images"]
    else:
        originals = [
            {"name": p["name"], "source_hex": (imported.parent / p["path"]).read_bytes().hex()}
            for p in definition["images"]
        ]
    thumbnails, sheet, results = reference(originals, definition["settings"])
    expected = {"version": 1, "settings": definition["settings"], "images": originals, "results": results}
    directory = root / config["output"]
    archive = (directory / "archive.json").read_bytes()
    assert archive == canonical(expected), directory
    if config["mode"] == "verify":
        assert canonical(definition) == archive
    report = (directory / "report.json").read_bytes()
    assert canonical(json.loads(report)) == canonical({"version": 1, "mode": config["mode"], "results": results})
    preview = (directory / "index.html").read_bytes()
    inspect_preview(preview, originals)
    files = {"sheet.bmp": sheet, "index.html": preview, "archive.json": archive, "report.json": report}
    for i, (source, thumbnail) in enumerate(zip(originals, thumbnails, strict=True)):
        files[f"source-{i}.bmp"] = bytes.fromhex(source["source_hex"])
        files[f"thumbnail-{i}.bmp"] = thumbnail
    for filename, prefix in [("project.json", "source"), ("thumbnails.json", "thumbnail")]:
        files[filename] = canonical(
            {
                "version": 1,
                "settings": definition["settings"],
                "images": [{"name": p["name"], "path": f"{prefix}-{i}.bmp"} for i, p in enumerate(originals)],
            }
        )
    for filename, mode, source, output in [
        ("rebuild.json", "build", "project.json", "rebuilt"),
        ("retile.json", "build", "thumbnails.json", "retiled"),
        ("replay.json", "verify", "archive.json", "replayed"),
    ]:
        files[filename] = canonical({"version": 1, "mode": mode, "input": source, "output": output})
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    assert len(files) == 10 + 2 * len(originals)
    return expected


def run(app: Application, root: Path, config: dict, selected: str = "bmp-job.json") -> dict:
    imported = root / config["input"]
    paths = [root / selected, imported]
    if config["mode"] == "build":
        paths += [imported.parent / row["path"] for row in json.loads(imported.read_bytes())["images"]]
    unchanged = {p: p.read_bytes() for p in paths}
    result = app.run(root, {"BMP_CONFIG": str(root / selected)}, timeout=180)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    assert (
        result.stdout
        == canonical(
            {
                "images": len(archive["images"]),
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
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".bmp-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, settings: dict, stem: str, reverse: bool = False) -> dict:
    original = files_at(root)
    project = json.loads((root / "project.json").read_bytes())
    project["settings"] = settings
    if reverse:
        project["images"].reverse()
        for image in project["images"]:
            image["name"] += " edited <&>"
    save(root / (stem + "-project.json"), project)
    config = {"version": 1, "mode": "build", "input": stem + "-project.json", "output": stem}
    save(root / (stem + "-job.json"), config)
    found = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return found


def semantics(app: Application, root: Path) -> dict:
    first = run(app, root, fixture(root, names=['<script>"&</script>', "Кошка 🐈", "Кошка 🐈"]))
    assert consume(app, root / "output", "replay.json") == first
    assert consume(app, root / "output", "rebuild.json") == first
    retiled = consume(app, root / "output", "retile.json")
    assert retiled["results"]["sheet_sha256"] == first["results"]["sheet_sha256"]
    variants = []
    for width, dib, top_down in itertools.product(range(1, 9), [12, 40, 108, 124], [False, True]):
        if dib == 12 and top_down:
            continue
        grid = pattern(width, 3, 113)
        raw = bitmap(
            grid,
            dib=dib,
            top_down=top_down,
            pad=0xA5,
            gap=b"opaque",
            tail=b"tail",
            palette=2 if dib != 12 else 0,
            image_size_zero=True,
        )
        work = root / ("variant-" + str(len(variants)))
        found = run(app, work, fixture(work, [raw], layout(box_width=5, box_height=7)))
        variants.append((width, found["results"]["sheet_sha256"]))
    for width in range(1, 9):
        assert len({h for w, h in variants if w == width}) == 1
    # Independently stated center-sampling goldens; ties select the right/bottom source pixel.
    red, green, blue, white = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)
    goldens = [
        ([[red, green, blue, white]], 2, 1, [[green, white]]),
        ([[red, green]], 3, 1, [[red, green, green]]),
        ([[red, green], [blue, white]], 1, 1, [[white]]),
        ([[red], [green], [blue], [white]], 1, 2, [[green], [white]]),
    ]
    for index, (grid, width, height, expected) in enumerate(goldens):
        work = root / f"golden-{index}"
        run(app, work, fixture(work, [bitmap(grid)], layout(box_width=width, box_height=height, fit="stretch")))
        assert read_bitmap((work / "output/thumbnail-0.bmp").read_bytes())[0] == expected
    profiles = 0
    for color, before in itertools.product([0x4C494E4B, 0x4D424544], [False, True]):
        work = root / f"profile-{profiles}"
        raw = bitmap(
            pattern(3, 2), dib=124, color_space=color, profile=b"/nonexistent/profile.icc\0", profile_before=before
        )
        run(app, work, fixture(work, [raw]))
        profiles += 1
    # With a non-profile color-space tag, even absurd profile offsets are ignored.
    raw = bytearray(bitmap(pattern(3, 2), dib=124, color_space=0x73524742))
    struct.pack_into("<II", raw, 126, 0xFFFFFFFF, 0xFFFFFFFF)
    work = root / "ignored-profile"
    run(app, work, fixture(work, [bytes(raw)]))
    work = root / "nested"
    config = fixture(work)
    (work / "nested").mkdir()
    project = json.loads((work / "project.json").read_bytes())
    for row in project["images"]:
        row["path"] = "../" + row["path"]
    save(work / "nested/project.json", project)
    config["input"] = "nested/project.json"
    save(work / "bmp-job.json", config)
    run(app, work, config)
    return {
        "header_orientation_padding_variants": len(variants),
        "manual_pixel_goldens": len(goldens),
        "profile_extents": profiles,
        "ignored_profile_fields": True,
        "nested_project_paths": True,
        "escaped_unicode_and_duplicate_names": True,
        "actual_rebuild_retile_replay": True,
        "archive_sha256": digest(canonical(first)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(113)
    hashes, checked = [], 0
    for i in range(20):
        sources = [
            bitmap(
                pattern(rng.randint(1, 30), rng.randint(1, 30), rng.randrange(256)),
                dib=rng.choice([40, 108, 124]),
                top_down=bool(rng.randrange(2)),
            )
            for _ in range(rng.randint(1, 8))
        ]
        settings = layout(
            box_width=rng.randint(1, 40),
            box_height=rng.randint(1, 40),
            columns=rng.randint(1, 8),
            margin=rng.randint(0, 6),
            gap=rng.randint(0, 6),
            fit="contain" if i % 2 else "stretch",
            background=[rng.randrange(256) for _ in range(3)],
        )
        work = root / str(i)
        first = run(app, work, fixture(work, sources, settings))
        retiled = consume(app, work / "output", "retile.json")
        assert first["results"]["sheet_sha256"] == retiled["results"]["sheet_sha256"]
        edited = edit_export(app, work / "output", layout(fit="stretch", columns=1), "edited", reverse=True)
        assert consume(app, work / "output/edited", "replay.json") == edited
        checked += first["results"]["width"] * first["results"]["height"]
        hashes.extend([digest(canonical(first)), digest(canonical(edited))])
    return {
        "seed": 113,
        "generated_projects": 20,
        "primary_sheet_pixels": checked,
        "retile_idempotence": 20,
        "reordered_renamed_relayout_replays": 20,
        "archives_sha256": digest(canonical(hashes)),
    }


def malformed(app: Application, root: Path) -> dict:
    raw = bitmap(pattern(3, 2))
    bad = [raw[:size] for size in range(len(raw))]
    for offset, fmt, values in [
        (0, "2s", [b"BA", b"ZZ"]),
        (2, "I", [0, len(raw) - 1, len(raw) + 1]),
        (6, "I", [1, 65536]),
        (10, "I", [0, 53, 55, 0xFFFFFFFF]),
        (14, "I", [0, 16, 64, 124]),
        (18, "i", [0, -1, 1025, -2147483648]),
        (22, "i", [0, 1025, -1025, -2147483648]),
        (26, "H", [0, 2]),
        (28, "H", [0, 1, 8, 16, 32]),
        (30, "I", [1, 2, 3, 6]),
        (34, "I", [1, 23, 25]),
        (46, "I", [1, 0xFFFFFFFF]),
    ]:
        for value in values:
            changed = bytearray(raw)
            struct.pack_into("<" + fmt, changed, offset, value)
            bad.append(bytes(changed))
    # Keep bfSize correct while removing the last padding byte: catches row bounds, not file-size disagreement.
    changed = bytearray(raw[:-1])
    struct.pack_into("<I", changed, 2, len(changed))
    bad.append(bytes(changed))
    profile = bitmap(pattern(3, 2), dib=124, color_space=0x4D424544, profile=b"1234")
    for offset, values in [(126, [0, 123, 124, len(profile)]), (130, [0, 5, 0xFFFFFFFF]), (134, [1])]:
        for value in values:
            changed = bytearray(profile)
            struct.pack_into("<I", changed, offset, value)
            bad.append(bytes(changed))
    palette = bytearray(bitmap(pattern(3, 2), dib=108, palette=2))
    struct.pack_into("<I", palette, 10, 14 + 108 + 7)
    bad.append(bytes(palette))
    for i, source in enumerate(bad):
        work = root / str(i)
        fixture(work, [source])
        reject(app, work)
    return {
        "all_proper_prefixes": len(raw),
        "other_malformed_bitmaps": len(bad) - len(raw),
        "truncated_padding_and_palette_bounds": True,
        "profile_overlap_and_extents": True,
    }


def invalid(app: Application, root: Path) -> dict:
    base = root / "base"
    config = fixture(base)
    project = json.loads((base / "project.json").read_bytes())
    cases = []
    for key in config:
        cases.append(("bmp-job.json", {k: v for k, v in config.items() if k != key}))
    cases += [
        ("bmp-job.json", dict(config, **{key: value}))
        for key, values in {
            "version": [True, 1.0, 0],
            "mode": ["parse", None],
            "input": ["", None, 0, "bad\0path"],
            "output": ["", 0, None, "bad\0path"],
            "extra": [1],
        }.items()
        for value in values
    ]
    for key in project:
        cases.append(("project.json", {k: v for k, v in project.items() if k != key}))
    for key, values in {
        "box_width": [0, 257, True, 1.0],
        "box_height": [0, 257, None],
        "columns": [0, 9, False],
        "margin": [-1, 33, 1.0],
        "gap": [-1, 33, True],
        "fit": ["nearest", 1],
        "background": [[], [1, 2], [1, 2, 3, 4], [True, 2, 3], [-1, 2, 3], [256, 2, 3], [1.0, 2, 3], "RGB"],
        "extra": [1],
    }.items():
        for value in values:
            cases.append(("project.json", dict(project, settings=dict(project["settings"], **{key: value}))))
    for key in project["settings"]:
        cases.append(
            ("project.json", dict(project, settings={k: v for k, v in project["settings"].items() if k != key}))
        )
    for name in ["", " ", "a" * 65, "bad\nname", "bad\x7fname", "bad\x9fname", 3, None]:
        cases.append(("project.json", dict(project, images=[{"name": name, "path": "source-0.bmp"}])))
    for images in [
        [],
        [project["images"][0]] * 17,
        {},
        None,
        [{"name": "x"}],
        [{"path": "source-0.bmp"}],
        [{"name": "x", "path": "source-0.bmp", "extra": 1}],
    ]:
        cases.append(("project.json", dict(project, images=images)))
    for i, (name, value) in enumerate(cases):
        work = root / str(i)
        fixture(work)
        save(work / name, value)
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
    for filename in ["bmp-job.json", "project.json", "archive.json"]:
        for i, raw in enumerate(malformed_json):
            work = root / (filename + str(i))
            fixture(work)
            if filename == "archive.json":
                save(work / "bmp-job.json", {"version": 1, "mode": "verify", "input": filename, "output": "output"})
            (work / filename).write_bytes(raw)
            reject(app, work)
    archive = run(app, base, config)
    paths = [
        (("version",), True),
        (("version",), 1.0),
        (("images", 0, "source_hex"), None),
        (("images", 0, "source_hex"), archive["images"][0]["source_hex"].upper()),
        (("images", 0, "source_hex"), " " + archive["images"][0]["source_hex"]),
        (("images", 0, "source_hex"), archive["images"][0]["source_hex"][:-1]),
        (("images", 0, "name"), "tampered"),
        (("settings", "gap"), 4),
        (("results",), None),
        (("results", "width"), float(archive["results"]["width"])),
        (("results", "source_pixels"), True),
        (("results", "sheet_sha256"), "0" * 64),
        (("results", "pixels_sha256"), "0" * 64),
        (("results", "items", 0, "left"), 0),
        (("results", "items", 0, "thumbnail_sha256"), "0" * 64),
        (("results", "items", 0, "source", "top_down"), 0),
        (("results", "items", 0, "source", "source_sha256"), "0" * 64),
        (("results", "items", 0, "source", "stride"), 99),
    ]
    altered = []
    for path, value in paths:
        changed = copy.deepcopy(archive)
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
        save(work / "bmp-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests_projects_and_settings": len(cases),
        "malformed_json_per_input": len(malformed_json),
        "tampered_archives": len(altered),
        "strict_cached_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    # Axis, per-image pixels, aggregate pixels and bytes are independent limits.
    maximum = bitmap(pattern(1024, 256))
    work = root / "maximum-pixels"
    found = run(app, work, fixture(work, [maximum] * 4, layout(box_width=1, box_height=1)))
    assert found["results"]["source_pixels"] == 1048576
    assert consume(app, work / "output", "replay.json") == found
    for label, sources, needle in [
        ("over-total-pixels", [maximum] * 4 + [bitmap(pattern(1, 1))], "combined source pixel limit"),
        ("over-image-pixels", [bitmap(pattern(1024, 257))], "image dimension or pixel limit"),
        ("over-width", [bitmap(pattern(1025, 1))], "image dimension or pixel limit"),
        ("over-height", [bitmap(pattern(1, 1025))], "image dimension or pixel limit"),
    ]:
        work = root / label
        fixture(work, sources, layout(box_width=1, box_height=1))
        reject(app, work, needle)
    work = root / "maximum-height"
    run(app, work, fixture(work, [bitmap(pattern(256, 1024), top_down=True)], layout(box_width=1, box_height=1)))
    small = bitmap(pattern(1, 1))
    padded = bitmap(pattern(1, 1), tail=b"x" * (2097152 - len(small)))
    work = root / "maximum-bytes"
    config = fixture(work, [padded] * 4, layout(box_width=1, box_height=1))
    for filename in ["bmp-job.json", "project.json"]:
        path = work / filename
        path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config)
    assert consume(app, work / "output", "replay.json") == archive
    work = root / "over-combined-bytes"
    fixture(work, [padded] * 4 + [small])
    reject(app, work, "combined source byte limit")
    for name, size in [("bmp-job.json", 65536), ("project.json", 65536), ("source-0.bmp", 2097152)]:
        work = root / ("over-" + name)
        fixture(work, [small])
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work, "input byte limit")
    baseline = root / "baseline"
    archive = run(app, baseline, fixture(baseline, [small]))
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-exact")
        config = fixture(work, [small])
        config.update(mode="verify", input="archive.json")
        save(work / "bmp-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(33554432 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config)
    work = root / "over-hex"
    config = fixture(work, [small])
    config.update(mode="verify", input="archive.json")
    save(work / "bmp-job.json", config)
    changed = copy.deepcopy(archive)
    changed["images"][0]["source_hex"] = "00" * 2097153
    save(work / "archive.json", changed)
    reject(app, work, "image byte limit")
    # Under the image/count/spacing bounds, 7 columns is the largest reachable sheet area.
    work = root / "maximum-sheet-area"
    found = run(
        app,
        work,
        fixture(
            work, [small] * 16, layout(box_width=256, box_height=256, columns=7, margin=32, gap=32), ["🐈" * 64] * 16
        ),
    )
    assert (found["results"]["width"], found["results"]["height"]) == (2048, 896)
    work = root / "exact-sheet-height"
    found = run(app, work, fixture(work, [small] * 16, layout(box_width=1, box_height=256, columns=1, margin=0, gap=0)))
    assert found["results"]["height"] == 4096
    work = root / "over-sheet-height"
    fixture(work, [small] * 16, layout(box_width=1, box_height=255, columns=1, margin=1, gap=1))
    reject(app, work, "sheet dimension or pixel limit")
    return {
        "image_axis": 1024,
        "image_pixels": 262144,
        "combined_pixels": 1048576,
        "source_bytes": 2097152,
        "combined_bytes": 8388608,
        "request_and_project_bytes": 65536,
        "archive_bytes": 33554432,
        "maximum_images": 16,
        "maximum_name_codepoints": 64,
        "maximum_reachable_sheet_pixels": 1835008,
        "sheet_height": 4096,
        "defensive_unreachable_limits": ["sheet_width_4096", "sheet_pixels_2097152", "export_bytes_33554432"],
        "maximum_sources_replayed": True,
    }


def publication(app: Application, root: Path) -> dict:
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work)
        result = app.run(work, {"BMP_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".bmp-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in [
        "request",
        "project",
        "source-0.bmp",
        "source-1.bmp",
        "source-2.bmp",
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
            env=app.environment({"BMP_PAUSE": stage, "BMP_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".bmp-*"))) == (1 if stage == "staged" else 0)
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
                    name = {"request": "bmp-job.json", "project": "project.json"}.get(mutation, mutation)
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".bmp-*"))
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
        ["bmp-job.json", "project.json", "source-0.bmp", "source-1.bmp", "source-2.bmp"],
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
            output.symlink_to(work / "bmp-job.json")
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
        print(app.engine + " BMP thumbnails " + name + ": passed", flush=True)
    return observations
