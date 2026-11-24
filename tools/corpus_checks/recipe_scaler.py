"""Whole-project recipe verification against an independent Fraction oracle and real exported sources."""

from __future__ import annotations

import copy
import itertools
import json
import math
import os
import random
import select
import subprocess
from fractions import Fraction
from pathlib import Path

from .common import Application
from .recipe_fixture import (
    UNITS,
    canonical,
    digest,
    document,
    expected,
    ingredient,
    number,
    recipe,
    rendered,
    scaled_source,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "plan", "input": "cookbook.json", "output": "output"}
    save(root / "recipe-job.json", config)
    save(root / "cookbook.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    results = expected(source)
    archive = {"version": 1, "source": source, "results": results}
    counts = {
        "week_start": results["week_start"],
        "selections": len(results["selections"]),
        "shopping_rows": len(results["shopping"]),
    }
    lines = [
        "Weekly shopping: exact quantities, grouped only within compatible units",
        canonical(counts).decode().strip(),
    ]
    lines.extend(row["name"] + ": " + row["quantity"] + " " + row["unit"] for row in results["shopping"])
    files = {
        "archive.json": canonical(archive),
        "cookbook.json": canonical(source),
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "summary": counts, "archive_sha256": digest(canonical(archive))}
        ),
        "shopping.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "plan.json": canonical({"version": 1, "mode": "plan", "input": "cookbook.json", "output": "planned"}),
    }
    for index, entry in enumerate(results["selections"]):
        stem = "scaled-" + str(index)
        files[stem + ".json"] = canonical(scaled_source(results, entry))
        files[stem + "-job.json"] = canonical(
            {"version": 1, "mode": "plan", "input": stem + ".json", "output": stem + "-plan"}
        )
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    directory = root / config["output"]
    assert {p.name for p in directory.iterdir()} == set(files)
    for name, raw in files.items():
        actual = (directory / name).read_bytes()
        assert actual == raw, (directory, name, actual[:2000], raw[:2000])
    if config["mode"] == "verify":
        assert canonical(imported["results"]) == canonical(results)
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "recipe-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"RECIPE_CONFIG": str(root / selected)}, timeout=120)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    report = json.loads((root / config["output"] / "report.json").read_bytes())
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=30)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr
    assert not (root / "output").exists() and not list(root.glob(".recipe-*"))
    return  # noqa: PLR1711


def restore_yield(app: Application, exported: Path, archive: dict, index: int) -> dict:
    name = "scaled-" + str(index)
    source = json.loads((exported / (name + ".json")).read_bytes())
    entry = archive["results"]["selections"][index]
    source["plan"][0]["portions"] = entry["original_servings"]
    save(exported / (name + "-restore.json"), source)
    config = json.loads((exported / (name + "-job.json")).read_bytes())
    config.update(input=name + "-restore.json", output=name + "-restored")
    save(exported / (name + "-restore-job.json"), config)
    restored = run(app, exported, config, selected=name + "-restore-job.json")
    original = next(row for row in archive["source"]["recipes"] if row["id"] == entry["recipe"])
    rows = restored["results"]["selections"][0]["ingredients"]
    assert [row["quantity"] for row in rows] == [rendered(number(row["quantity"])) for row in original["ingredients"]]
    assert [row["name"] for row in rows] == [row["name"] for row in original["ingredients"]]
    assert [row["unit"] for row in rows] == [row["unit"] for row in original["ingredients"]]
    return restored


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    exported = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "plan.json") == archive
    assert files_at(root / "output") == exported
    totals = {(row["identity"], row["unit"]): row["quantity"] for row in archive["results"]["shopping"]}
    assert totals == {
        ("egg", "piece"): "7/2",
        ("flour", "g"): "875",
        ("milk", "g"): "1/3",
        ("milk", "mL"): "1625/6",
        ("salt", "g"): "1/6",
        ("strasse", "g"): "1/3",
        ("water", "mL"): "2/3",
    }
    for index in range(4):
        stable = consume(app, root / "output", "scaled-" + str(index) + "-job.json")
        assert stable["results"]["selections"][0]["factor"] == "1"
        restore_yield(app, root / "output", archive, index)
    assert all((root / "output" / name).read_bytes() == raw for name, raw in exported.items())
    for label, source in [
        ("empty", {"version": 1, "week_start": "2026-10-19", "recipes": [], "plan": []}),
        (
            "empty-recipe",
            {
                "version": 1,
                "week_start": "2026-10-19",
                "recipes": [recipe("empty", "1", [])],
                "plan": [{"day": 6, "recipe": "empty", "portions": "3/7"}],
            },
        ),
    ]:
        work = root / label
        assert run(app, work, fixture(work, source))["results"]["shopping"] == []
    return {
        "recipes": 3,
        "selections": 4,
        "shopping_rows": 7,
        "contributions": 16,
        "restored_exported_recipes": 4,
        "all_eight_units": True,
        "unicode_grouping_and_incompatible_units": True,
        "zero_quantities_and_empty_plans": True,
        "original_names_units_and_order_preserved": True,
        "actual_replay_plan_and_scaled_requests": True,
        "archive_sha256": digest(exported["archive.json"]),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(107)
    hashes, contributions, restored = [], 0, 0
    names = ["Flour", " flour ", "MILK", "ｍｉｌｋ", "Straße", "STRASSE", "Salt", "water", "糖", "Café", "Café"]
    units = list(UNITS)
    for batch in range(16):
        source = {"version": 1, "week_start": "2000-02-27" if batch % 2 else "2026-12-28", "recipes": [], "plan": []}
        for index in range(8):
            items = [
                ingredient(
                    rng.choice(names),
                    rendered(Fraction(rng.randrange(100), rng.randrange(1, 32))),
                    units[(j + index) % 8],
                )
                for j in range(8)
            ]
            source["recipes"].append(
                recipe("r" + str(index), rendered(Fraction(rng.randrange(1, 20), rng.randrange(1, 10))), items)
            )
        for _ in range(16):
            source["plan"].append(
                {
                    "day": rng.randrange(7),
                    "recipe": "r" + str(rng.randrange(8)),
                    "portions": rendered(Fraction(rng.randrange(1, 20), rng.randrange(1, 10))),
                }
            )
        work = root / str(batch)
        archive = run(app, work, fixture(work, source))
        hashes.append(digest(canonical(archive)))
        contributions += sum(len(row["contributions"]) for row in archive["results"]["shopping"])
        for index in [0, 7, 15]:
            restore_yield(app, work / "output", archive, index)
            restored += 1
        split = copy.deepcopy(source)
        choice = split["plan"].pop(0)
        split["plan"] = [
            {**choice, "portions": rendered(number(choice["portions"]) / 3)},
            {**choice, "portions": rendered(number(choice["portions"]) * Fraction(2, 3))},
            *split["plan"],
        ]
        child = root / (str(batch) + "-split")
        altered = run(app, child, fixture(child, split))

        def shopping_quantities(results: dict) -> dict:
            return {(row["identity"], row["unit"]): row["quantity"] for row in results["shopping"]}

        assert shopping_quantities(altered["results"]) == shopping_quantities(archive["results"])
    return {
        "seed": 107,
        "batches": 16,
        "recipes": 128,
        "plan_selections": 256,
        "contributions_checked": contributions,
        "restored_exported_recipes": restored,
        "split_selection_invariance": 16,
        "independent_fraction_oracle": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    cases = []

    def changed(path: list, value: object) -> None:
        source = document()
        target = source
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        cases.append(source)
        return  # noqa: PLR1711

    malformed = [
        None,
        True,
        1,
        1.0,
        {},
        [],
        "",
        "-1",
        "+1",
        " 1",
        "1 ",
        ".5",
        "1.",
        "1e2",
        "1_0",
        "nan",
        "inf",
        "１",
        "1/0",
        "1/00",
        "1/-2",
        "1 /2",
        "1/ 2",
        "1//2",
        "1/2/3",
        "1 2/2",
        "1 3/2",
        "1  1/2",
        "1\t1/2",
        "1\n",
    ]
    for path in [["recipes", 0, "servings"], ["recipes", 0, "ingredients", 0, "quantity"], ["plan", 0, "portions"]]:
        for value in malformed:
            changed(path, value)
    for path in [["recipes", 0, "servings"], ["plan", 0, "portions"]]:
        for value in ["0", "0/2", "0.000", "0 0/2"]:
            changed(path, value)
    for path, value in [
        (["version"], True),
        (["version"], 1.0),
        (["version"], 2),
        (["extra"], 1),
        (["recipes"], {}),
        (["plan"], {}),
        (["recipes", 1, "id"], "pancakes"),
        (["recipes", 0, "id"], "1bad"),
        (["recipes", 0, "id"], "a" * 33),
        (["recipes", 0, "ingredients"], None),
        (["recipes", 0, "ingredients", 0, "unit"], "ml"),
        (["recipes", 0, "ingredients", 0, "unit"], "pinch"),
        (["recipes", 0, "ingredients", 0, "unit"], True),
        (["plan", 0, "day"], -1),
        (["plan", 0, "day"], 7),
        (["plan", 0, "day"], True),
        (["plan", 0, "day"], 0.0),
        (["plan", 0, "recipe"], "missing"),
        (["plan", 0, "recipe"], 1),
        (["plan", 0, "extra"], 1),
        (["recipes", 0, "extra"], 1),
        (["recipes", 0, "ingredients", 0, "extra"], 1),
    ]:
        changed(path, value)
    for value in [None, True, "", "2026-1-01", "2026-01-01Z", "2026-02-29", "1900-02-29", "0000-01-01", "9999-12-26"]:
        changed(["week_start"], value)
    for path in [["recipes", 0, "title"], ["recipes", 0, "ingredients", 0, "name"]]:
        for value in [None, 1, "", " \t\n", "a" * 101, "x\x00y", "x\x1by", "x\x7fy", "x\x80y", "㍿" * 26]:
            changed(path, value)
    cases += [None, [], {}, {"version": 1}]
    for index, source in enumerate(cases):
        work = root / ("source-" + str(index))
        fixture(work)
        save(work / "cookbook.json", source)
        reject(app, work)
    configs = [
        None,
        [],
        {},
        {"version": 1},
        *[
            {"version": 1, "mode": "plan", "input": "cookbook.json", "output": "output", **change}
            for change in [
                {"version": True},
                {"version": 1.0},
                {"version": 2},
                {"mode": "scale"},
                {"input": "missing"},
                {"input": ""},
                {"output": ""},
                {"extra": 1},
            ]
        ],
    ]
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "recipe-job.json", config)
        reject(app, work)
    raw_cases = [
        b"",
        b"{",
        b"[] trailing",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":01}',
        b'{"x":"\xff"}',
        b'{"x":"\\ud800"}',
        b'{"x":true} null',
    ]
    for name in ["recipe-job.json", "cookbook.json", "archive.json"]:
        for index, raw in enumerate(raw_cases):
            work = root / (name + str(index))
            config = fixture(work)
            if name == "archive.json":
                config.update(mode="verify", input=name)
                save(work / "recipe-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    archive = {"version": 1, "source": document(), "results": expected(document())}
    paths = [
        ["version"],
        ["results", "shopping", 0, "quantity"],
        ["results", "shopping", 0, "unit"],
        ["results", "shopping", 0, "contributions", 0, "ingredient"],
        ["results", "shopping", 0, "contributions", 0, "selection"],
        ["results", "selections", 0, "day"],
        ["results", "selections", 0, "ingredients", 0, "quantity"],
        ["results", "selections", 0, "date"],
        ["results", "selections"],
        ["source", "plan", 0, "portions"],
    ]
    values = [1.0, "999", "g", 2.0, False, False, "1", "2026-10-20", [], "3"]
    for index, (path, value) in enumerate(zip(paths, values)):
        tampered = copy.deepcopy(archive)
        target = tampered
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "recipe-job.json", config)
        save(work / "archive.json", tampered)
        reject(app, work)
    return {
        "invalid_sources": len(cases),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(raw_cases),
        "tampered_archives": len(paths),
        "strict_cached_numeric_types": True,
    }


def small(rows: list[dict], servings: str = "1", portions: str = "1") -> dict:
    return {
        "version": 1,
        "week_start": "2026-10-19",
        "recipes": [recipe("r", servings, rows)],
        "plan": [{"day": 0, "recipe": "r", "portions": portions}],
    }


def limits(app: Application, root: Path) -> dict:
    source = {"version": 1, "week_start": "2026-10-19", "recipes": [], "plan": []}
    for index in range(32):
        source["recipes"].append(
            recipe("r" + str(index), "1", [ingredient("Ingredient " + str(j), "1", "g") for j in range(8)])
        )
    source["plan"] = [{"day": i % 7, "recipe": "r" + str(i % 32), "portions": "1"} for i in range(64)]
    work = root / "all-record-limits"
    run(app, work, fixture(work, source))
    for label in ["recipes", "ingredients", "plan"]:
        over = copy.deepcopy(source)
        if label == "ingredients":
            over["recipes"][0]["ingredients"].append(ingredient("extra", "1", "g"))
        elif label == "recipes":
            over["recipes"].append(recipe("extra", "1", []))
        else:
            over["plan"].append(over["plan"][0])
        work = root / ("over-" + label)
        fixture(work, over)
        reject(app, work)
    source = small([ingredient("same", "1", "g") for _ in range(256)])
    source["plan"] = [source["plan"][0] for _ in range(64)]
    work = root / "maximum-contributions"
    result = run(app, work, fixture(work, source))
    assert result["results"]["shopping"][0]["quantity"] == "16384"
    assert len(result["results"]["shopping"][0]["contributions"]) == 16384
    rows = [ingredient("same", "0" * 255 + "1", "g") for _ in range(31)] + [ingredient("same", "0" * 253 + "1", "g")]
    work = root / "numeric-characters"
    run(app, work, fixture(work, small(rows)))
    for label, changed in [
        ("individual", [ingredient("same", "0" * 256 + "1", "g")]),
        ("aggregate", rows[:-1] + [ingredient("same", "0" * 254 + "1", "g")]),
    ]:
        work = root / ("over-characters-" + label)
        fixture(work, small(changed))
        reject(app, work, "character limit")
    denominators, candidate = [], 10**29 + 1
    while len(denominators) < 255:
        if all(math.gcd(candidate, earlier) == 1 for earlier in denominators):
            denominators.append(candidate)
        candidate += 2
    work = root / "large-exact-total"
    source = small([ingredient("same", "1/" + str(n), "g") for n in denominators])
    result = run(app, work, fixture(work, source))
    total_text = result["results"]["shopping"][0]["quantity"]
    assert len(total_text.split("/")[1]) > 7000
    # Successful exports must be importable; both individual and aggregate output bounds are enforced.
    work = root / "export-quantity-limit"
    source = small([ingredient("same", "1/1" + "0" * 127, "g")], "1" + "0" * 127, "1/1" + "0" * 127)
    fixture(work, source)
    reject(app, work, "quantity character limit")
    work = root / "export-aggregate-limit"
    source = small([ingredient("same", "1" + "0" * 99, "g") for _ in range(64)], "9" * 100)
    fixture(work, source)
    reject(app, work, "total quantity character limit")
    for index, start in enumerate(["0001-01-01", "9999-12-25", "2000-02-27", "1900-02-27"]):
        work = root / ("calendar-" + str(index))
        source = small([ingredient("😀" * 100, "0", "piece")])
        source["week_start"] = start
        source["plan"][0]["day"] = 6
        run(app, work, fixture(work, source))
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("recipe-job.json", 65536), ("cookbook.json", 2097152)]:
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("recipe-job.json", 65536), ("cookbook.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "recipe-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "recipes": 32,
        "ingredients": 256,
        "plan_entries": 64,
        "contributions": 16384,
        "quantity_characters": 256,
        "total_quantity_characters": 8192,
        "name_characters": 100,
        "exact_total_denominator_digits": len(total_text.split("/")[1]),
        "unusable_exports_rejected": 2,
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
        "calendar_boundaries": 4,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document()
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"RECIPE_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".recipe-*")) and (work / "output").exists() == (stage == "published")
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
            env=app.environment({"RECIPE_PAUSE": stage, "RECIPE_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".recipe-*"))) == (1 if stage == "staged" else 0)
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
                    name = "recipe-job.json" if mutation == "request" else "cookbook.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".recipe-*"))
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
        ["recipe-job.json", "cookbook.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "recipe-job.json")
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
        print(app.engine + " recipe scaler " + name + ": passed", flush=True)
    return observations
