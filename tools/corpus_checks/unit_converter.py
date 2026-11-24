"""Dimensional and rational-factor acceptance, notebook replay, invalid input and atomic export checks."""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import select
import subprocess
from pathlib import Path

from .common import Application
from .units_fixture import (
    canonical,
    conversion,
    definitions,
    digest,
    dimension_name,
    fixtures,
    inspect_entry,
    inspect_unit,
    parse,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def request(rows: list, output: str = "output", notebook: str | None = None) -> dict:
    return {"version": 1, "mode": "convert", "notebook": notebook, "output": output, "conversions": rows}


def fixture(root: Path, rows: list | None = None, imported: list | None = None, output: str = "output") -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = request(fixtures() if rows is None else rows, output, "previous.json" if imported is not None else None)
    save(root / "units-job.json", config)
    if imported is not None:
        save(root / "previous.json", {"version": 1, "entries": imported})
    return config


def files_at(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}


def inspect(
    root: Path, config: dict, statuses: list[str], previous: list, reasons: dict[int, str] | None = None
) -> tuple[list, dict]:
    output = root / config["output"]
    book_raw = (output / "notebook.json").read_bytes()
    book = json.loads(book_raw)
    assert book.keys() == {"version", "entries"} and type(book["version"]) is int and book["version"] == 1
    assert book_raw == canonical(book)
    entries = book["entries"]
    assert canonical(entries[: len(previous)]) == canonical(previous)
    assert len(entries) == len(previous) + statuses.count("converted")
    assert len({entry["request"]["id"] for entry in entries}) == len(entries) <= 256
    for entry in entries:
        inspect_entry(entry)
    report = json.loads((output / "report.json").read_bytes())
    assert report.keys() == {"version", "mode", "before_entries", "entries", "summary", "notebook_sha256", "outcomes"}
    expected_outcomes = []
    seen = {entry["request"]["id"]: entry["request"] for entry in previous}
    added = []
    rows = config.get("conversions", [])
    assert len(rows) == len(statuses) == len(report["outcomes"])
    for index, (row, status, outcome) in enumerate(zip(rows, statuses, report["outcomes"])):
        if status == "rejected":
            assert outcome.keys() == {"index", "status", "request", "reason"}
            assert isinstance(outcome["reason"], str) and outcome["reason"]
            if reasons is not None and index in reasons:
                assert outcome["reason"] == reasons[index], (row, outcome)
            expected_outcomes.append({"index": index, "status": status, "request": row, "reason": outcome["reason"]})
        else:
            expected_outcomes.append({"index": index, "status": status, "id": row["id"]})
            if status == "duplicate":
                assert row == seen[row["id"]]
            else:
                assert status == "converted" and row["id"] not in seen
                seen[row["id"]] = row
                added.append(row)
    assert [entry["request"] for entry in entries[len(previous) :]] == added
    summary = {key: statuses.count(key) for key in ["converted", "duplicate", "rejected"]}
    expected_report = {
        "version": 1,
        "mode": config["mode"],
        "before_entries": len(previous),
        "entries": len(entries),
        "summary": summary,
        "notebook_sha256": digest(book_raw),
        "outcomes": expected_outcomes,
    }
    assert report == expected_report and (output / "report.json").read_bytes() == canonical(expected_report)
    definitions_raw = (output / "units.json").read_bytes()
    actual_units, expected_units = json.loads(definitions_raw), definitions()
    assert set(actual_units) == set(expected_units)
    for name, unit in expected_units.items():
        inspect_unit(actual_units[name], unit)
    lines = [f"Conversion notebook: {len(entries)} entries; " + canonical(summary).decode().strip()]
    for entry in entries:
        row = entry["request"]
        lines.append(
            row["id"]
            + ": "
            + row["quantity"]
            + " = "
            + canonical(entry["result"]["converted"]).decode().strip()
            + " "
            + row["to"]
        )
    lines.extend(
        "rejected " + str(row["index"]) + ": " + row["reason"]
        for row in expected_outcomes
        if row["status"] == "rejected"
    )
    files = {
        "notebook.json": book_raw,
        "report.json": canonical(expected_report),
        "units.json": canonical(actual_units),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "notebook": "notebook.json", "output": "replayed"}),
        "continue.json": canonical(request([], "continued", "notebook.json")),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(raw), "sha256": digest(raw)} for name, raw in files.items()}
    )
    assert {p.name for p in output.iterdir()} == set(files) and files_at(output) == files
    return entries, report


def run(
    app: Application,
    root: Path,
    config: dict,
    statuses: list[str],
    previous: list | None = None,
    selected: str = "units-job.json",
    reasons: dict[int, str] | None = None,
) -> tuple[list, dict]:
    preserved = {root / selected: (root / selected).read_bytes()}
    if config["notebook"] is not None:
        path = root / config["notebook"]
        preserved[path] = path.read_bytes()
    result = app.run(root, {"UNITS_CONFIG": str(root / selected)}, timeout=30)
    assert result.returncode == int("rejected" in statuses) and not result.stderr, (root, result)
    entries, report = inspect(root, config, statuses, [] if previous is None else previous, reasons)
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    return entries, report


def consume(
    app: Application, root: Path, name: str, previous: list, statuses: list[str] | None = None
) -> tuple[list, dict]:
    config = json.loads((root / name).read_bytes())
    return run(app, root, config, [] if statuses is None else statuses, previous, name)


def reject(app: Application, root: Path, reason: str = "") -> None:
    result = app.run(root, {}, timeout=10)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert reason in result.stderr, (reason, result)
    assert not (root / "output").exists() and not list(root.glob(".units-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    rows = fixtures()
    work = root / "hand"
    config = fixture(work, rows)
    entries, _ = run(app, work, config, ["converted"] * len(rows))
    original = files_at(work / "output")
    replayed, _ = consume(app, work / "output", "replay.json", entries)
    continued, _ = consume(app, work / "output", "continue.json", entries)
    assert replayed == continued == entries and files_at(work / "output") == original
    # Golden physical identities do not depend on the application's unit catalog or numeric implementation.
    expected = {
        "length": 1,
        "speed": 25,
        "volume": 2000,
        "pressure": 101.325,
        "energy": 7200,
        "electric": 3,
        "charge": 14400,
        "molar": 2000,
        "celsius": 273.15,
        "fahrenheit": 0,
        "cold": -40,
        "kelvin": 32,
        "dimensionless": 2000000,
    }
    for row in entries:
        if row["request"]["id"] in expected:
            assert abs(float(inspect_entry(row)) - expected[row["request"]["id"]]) <= 1e-12
    all_units = definitions()
    catalog_rows = [
        conversion("unit" + str(i), "1 " + name, dimension_name(unit.powers))
        for i, (name, unit) in enumerate(sorted(all_units.items()))
    ]
    work = root / "every-unit"
    book, _ = run(app, work, fixture(work, catalog_rows), ["converted"] * len(catalog_rows))
    # Rejected IDs are not persisted; conflicts preserve the original successful request.
    cases = [
        conversion("fix", "1 m", "s"),
        conversion("fix", "1 m", "cm"),
        conversion("fix", "1 m", "cm"),
        conversion("fix", "2 m", "cm"),
    ]
    work = root / "identities"
    ids, _ = run(
        app,
        work,
        fixture(work, cases),
        ["rejected", "converted", "duplicate", "rejected"],
        reasons={0: "incompatible dimensions", 3: "conversion identifier conflicts"},
    )
    assert len(ids) == 1
    work = root / "imported-identities"
    run(
        app,
        work,
        fixture(work, [cases[1], cases[3]], ids),
        ["duplicate", "rejected"],
        ids,
        reasons={1: "conversion identifier conflicts"},
    )
    return {
        "hand_conversions": len(rows),
        "golden_identities": len(expected),
        "catalog_units": len(all_units),
        "replay_and_empty_continuation": True,
        "rejected_ids_reusable": True,
        "idempotent_import": True,
        "hand_notebook_sha256": digest(original["notebook.json"]),
        "catalog_notebook_sha256": digest(canonical({"version": 1, "entries": book})),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(103)
    choices = [name for name in definitions() if name not in {"degC", "degF"}]
    hashes = []
    total = 0
    for batch in range(12):
        rows = []
        for index in range(32):
            left, right = rng.sample(choices, 2)
            a, b = rng.choice([-3, -2, -1, 1, 2, 3]), rng.choice([-3, -2, -1, 1, 2, 3])
            expression = f"({left}^{a})/({right}^{b})"
            unit = parse(expression)
            # The target uses only SI bases; split powers above the grammar's per-power limit if needed.
            target = (
                "*".join(
                    name + "^" + str(p) for name, p in zip(["m", "kg", "s", "A", "K", "mol", "cd"], unit.powers) if p
                )
                or "1"
            )
            if any(abs(p) > 8 for p in unit.powers):
                target = expression
            rows.append(
                conversion(f"b{batch}_{index}", str(rng.randint(-10000, 10000) / 100) + " " + expression, target)
            )
        work = root / str(batch)
        entries, _ = run(app, work, fixture(work, rows), ["converted"] * len(rows))
        # Reverse conversions use actual exported result values, not regenerated equivalents.
        reverse = [
            conversion(
                "reverse" + str(i),
                canonical(row["result"]["converted"]).decode().strip() + " " + row["request"]["to"],
                row["result"]["source_unit"],
            )
            for i, row in enumerate(entries)
        ]
        reverse_root = work / "reverse"
        returned, _ = run(app, reverse_root, fixture(reverse_root, reverse), ["converted"] * len(reverse))
        for initial, back in zip(entries, returned):
            left, right = initial["result"]["value"], back["result"]["converted"]
            assert abs(left - right) <= max(1e-12, abs(left) * 1e-12)
        hashes.append(digest(canonical([entries, returned])))
        total += len(rows)
    return {
        "seed": 103,
        "batches": 12,
        "compound_conversions": total,
        "reverse_conversions": total,
        "rational_factor_and_dimension_oracle": True,
        "artifacts_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    unit_texts = [
        "",
        " ",
        "unknown",
        "M",
        "m2",
        "μm",
        "m+s",
        "m-s",
        "2*m",
        "m s",
        "m//s",
        "m**2",
        "m/",
        "*m",
        "()",
        "(m",
        "m)",
        "m^",
        "m^+",
        "m^1.5",
        "m^999",
        "m^9",
        "m^-9",
        "m^2^2",
        "m\n",
        "m\x00",
        "degC/s",
        "degF^1",
        "(degC)",
        "degC^0",
        "m/degF",
        "(" * 9 + "m" + ")" * 9,
        "m^8*m^8*m^8*m^8*m",
        "nm^8*nm^8",
        "nm^-8*nm^-8",
    ]
    rows = [conversion("u" + str(i), "1 " + value, "m") for i, value in enumerate(unit_texts)]
    rows += [
        conversion("q" + str(i), value, "m")
        for i, value in enumerate(
            [
                "",
                "1",
                "m",
                "1m",
                "1 2 m",
                "nan m",
                "inf m",
                "1e309 m",
                "1e-9999 m",
                "1e-101 m",
                "1.1e100 m",
                "1__0 m",
                "_1 m",
                "1e_2 m",
                "1,5 m",
                "0x1p2 m",
                "１ m",
                "١ m",
                "−1 m",
                "1\nm",
                "1 m\n",
                ". m",
                "+ m",
                "1\x00 m",
                "1.0f m",
            ]
        )
    ]
    rows += [
        conversion("dimension", "1e100 km^8", "s"),
        conversion("result_large", "1e100 km", "m"),
        conversion("result_small", "1e-100 m", "km"),
    ]
    assert len(rows) <= 64
    reasons = {
        len(rows) - 3: "incompatible dimensions",
        len(rows) - 2: "result out of range",
        len(rows) - 1: "result out of range",
    }
    work = root / "grammar"
    entries, _ = run(app, work, fixture(work, rows), ["rejected"] * len(rows), reasons=reasons)
    assert not entries
    malformed_rows = [None, [], True, "x", {}, {"id": "missing"}, {**conversion("extra", "1 m", "m"), "extra": 1}]
    for key, values in {
        "id": [True, 1, "", "bad!", "x" * 33],
        "quantity": [None, 1, True],
        "to": [None, [], 1],
    }.items():
        malformed_rows += [{**conversion("bad", "1 m", "m"), key: value} for value in values]
    work = root / "row-shapes"
    run(app, work, fixture(work, malformed_rows), ["rejected"] * len(malformed_rows))
    configs = []
    base = request([])
    for key, values in {
        "version": [False, 1.0, 2],
        "mode": [None, "other"],
        "notebook": [False, "", "missing.json"],
        "output": ["", None, 1],
        "conversions": [None, {}, "x"],
    }.items():
        configs += [{**base, key: value} for value in values]
    configs += [
        {**base, "extra": 1},
        {k: v for k, v in base.items() if k != "notebook"},
        {"version": 1, "mode": "verify", "notebook": None, "output": "output"},
    ]
    for index, config in enumerate(configs):
        work = root / f"config-{index}"
        fixture(work, [])
        save(work / "units-job.json", config)
        reject(app, work)
    raw_errors = [
        b"",
        b"{}{}",
        b'{"version":1,"version":1}',
        b"[]",
        b"null",
        b"\xff",
        b"[NaN]",
        b"[9223372036854775808]",
        b'"\\ud800"',
        b"[" * 66 + b"0" + b"]" * 66,
    ]
    for name, raw in itertools.product(["units-job.json", "previous.json"], raw_errors):
        work = root / f"encoding-{name}-{digest(raw)[:10]}"
        fixture(work, [], [])
        (work / name).write_bytes(raw)
        reject(app, work)
    work = root / "seed"
    seed, _ = run(app, work, fixture(work, [conversion("sample", "2 km", "m")]), ["converted"])
    book = {"version": 1, "entries": seed}
    changed = []
    for path, value in [
        (("version",), True),
        (("version",), 1.0),
        (("extra",), 1),
        (("entries",), {}),
        (("entries", 0, "extra"), 1),
        (("entries", 0, "request", "quantity"), "3 km"),
        (("entries", 0, "request", "to"), "s"),
        (("entries", 0, "result", "converted"), 2000),
        (("entries", 0, "result", "converted"), 2001.0),
        (("entries", 0, "result", "value"), True),
        (("entries", 0, "result", "source", "factor"), 999.0),
        (("entries", 0, "result", "source", "dimensions", 0), 1.0),
        (("entries", 0, "result", "target", "base_unit"), "s"),
        (("entries", 0, "result", "base_value"), 2000),
        (("entries", 0, "result", "round_trip", "error"), 1.0),
        (("entries", 0, "result", "round_trip", "tolerance"), 1.0),
    ]:
        altered = copy.deepcopy(book)
        node = altered
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value
        changed.append(altered)
    changed.append({"version": 1, "entries": seed * 2})
    for index, altered in enumerate(changed):
        work = root / f"tamper-{index}"
        fixture(work, [], [])
        save(work / "previous.json", altered)
        before = (work / "previous.json").read_bytes()
        reject(app, work)
        assert (work / "previous.json").read_bytes() == before
    return {
        "invalid_grammar_and_numeric_rows": len(rows),
        "malformed_rows": len(malformed_rows),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(raw_errors),
        "tampered_notebooks": len(changed),
        "incompatible_dimensions_rejected_before_values": True,
        "cached_numeric_types_checked": True,
    }


def limits(app: Application, root: Path) -> dict:
    rows = [
        conversion("depth", "1 " + "(" * 8 + "m" + ")" * 8, "m"),
        conversion("tokens", "1 " + "*".join(["1"] * 47) + "^+0", "1"),
        conversion("dimension", "1 m^8*m^8*m^8*m^8", "(m^8)^4"),
        conversion("negative", "1 m^-8*m^-8*m^-8*m^-8", "(m^-8)^4"),
        conversion("leading_power", "1 m^+08", "m^8"),
        conversion("zero_power", "1 m^-00", "1"),
        conversion("expression_length", "1 m", "m" + " " * 127),
        conversion("quantity_length", "1" + " " * 254 + "m", "m"),
        conversion("n" * 32, "1e100 m", "m"),
        conversion("minimum", "1e-100 m", "m"),
    ]
    work = root / "exact"
    run(app, work, fixture(work, rows), ["converted"] * len(rows))
    over = [
        conversion("tokens", "1 " + "*".join(["1"] * 49), "1"),
        conversion("expression", "1 m", "m" + " " * 128),
        conversion("quantity", "1" + " " * 255 + "m", "m"),
        conversion("x" * 33, "1 m", "m"),
    ]
    work = root / "over"
    run(app, work, fixture(work, over), ["rejected"] * len(over))
    previous = None
    work = root / "notebook-capacity"
    for batch in range(4):
        rows = [conversion(f"b{batch}_{i}", str(i + 1) + " cm", "m") for i in range(64)]
        config = fixture(work, rows, previous, output=f"batch-{batch}")
        previous, _ = run(app, work, config, ["converted"] * 64, previous)
    config = fixture(work, [conversion("over", "1 m", "cm"), previous[0]["request"]], previous, output="full")
    final, report = run(app, work, config, ["rejected", "duplicate"], previous, reasons={0: "notebook entry limit"})
    assert final == previous and report["entries"] == 256
    for rows, imported in [
        ([conversion("x" + str(i), "1 m", "m") for i in range(65)], None),
        ([], previous + previous[:1]),
    ]:
        work = root / ("too-many-conversions" if rows else "too-many-imported-entries")
        fixture(work, rows, imported)
        reject(app, work)
    work = root / "exact-bytes"
    config = fixture(work, [], previous)
    for name, size in [("units-job.json", 65536), ("previous.json", 1048576)]:
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size, b" "))
    run(app, work, config, [], previous)
    for name, size in [("units-job.json", 65536), ("previous.json", 1048576)]:
        work = root / ("over-" + name)
        fixture(work, [], [])
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    return {
        "quantity_characters": 256,
        "expression_characters": 128,
        "tokens": 96,
        "parenthesis_depth": 8,
        "power_magnitude": 8,
        "dimension_magnitude": 32,
        "quantity_magnitude": "0 or 1e-100..1e100",
        "batch_conversions": 64,
        "notebook_entries": 256,
        "request_bytes": 65536,
        "notebook_bytes": 1048576,
        "duplicate_allowed_at_capacity": True,
        "imported_raw_bytes_preserved": True,
    }


def publication(app: Application, root: Path) -> dict:
    seed_root = root / "seed"
    seed, _ = run(app, seed_root, fixture(seed_root, [conversion("seed", "1 m", "cm")]), ["converted"])
    rows = [conversion("next", "2 km", "m")]
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows, seed)
        result = app.run(work, {"UNITS_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".units-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config, ["converted"], seed)
        assert json.loads((work / "previous.json").read_bytes())["entries"] == seed
    for mutation in ["request", "notebook", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows, seed)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"UNITS_PAUSE": stage, "UNITS_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert process.returncode == -9
                assert (work / "output").exists() == (stage == "published")
                assert len(list(work.glob(".units-*"))) == (1 if stage == "staged" else 0)
                if stage == "published":
                    inspect(work, config, ["converted"], seed)
                retry = {**config, "output": "retry"}
                save(work / "retry.json", retry)
                run(app, work, retry, ["converted"], seed, "retry.json")
            else:
                if mutation == "competitor":
                    (work / "output").mkdir()
                    (work / "output/keep").write_text("original")
                else:
                    name = "units-job.json" if mutation == "request" else "previous.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout
                assert not list(work.glob(".units-*"))
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
        "input_output_races": 3,
        "hard_kills": 2,
        "retry_after_hard_kill": True,
        "complete_or_absent_final_bundle": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    count = 0
    for name, kind in itertools.product(
        ["units-job.json", "previous.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
    ):
        work = root / str(count)
        fixture(work, [], [])
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
        fixture(work, [])
        output = work / "output"
        if kind == "file":
            output.write_text("keep")
        elif kind == "directory":
            output.mkdir()
        elif kind == "symlink":
            output.symlink_to(work / "units-job.json")
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
        print(app.engine + " unit converter " + name + ": passed", flush=True)
    return observations
