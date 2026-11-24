"""Exact bills, partition invariance, strict validation, portable replay and guarded publication."""

from __future__ import annotations

import copy
import datetime as dt
import itertools
import json
import os
import random
import select
import subprocess
from fractions import Fraction
from pathlib import Path

from .common import Application
from .tariff_fixture import (
    at,
    canonical,
    digest,
    document,
    expected,
    fixed,
    flat,
    seconds,
    unr,
    utc,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "simulate", "input": "usage.json", "output": "output"}
    save(root / "tariff-job.json", config)
    save(root / "usage.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    results = expected(source)
    archive = {"version": 1, "source": source, "results": results}
    counts = {"tariffs": len(results["bills"]), "ranking": results["ranking"], "cheapest": results["cheapest"]}
    lines = [
        "Fictional electricity tariffs; UTC bands; uniform interval consumption",
        "Exact charges; final total rounded once to two places, ties to even",
        canonical(counts).decode().strip(),
    ]
    for bill in results["bills"]:
        lines.append(
            f'{bill["id"]}: {bill["rounded_total"]} currency units; exact '
            + bill["total"]["numerator"]
            + "/"
            + bill["total"]["denominator"]
        )
    files = {
        "archive.json": canonical(archive),
        "usage.json": canonical(source),
        "report.json": canonical(
            {"version": 1, "mode": config["mode"], "summary": counts, "archive_sha256": digest(canonical(archive))}
        ),
        "report.txt": ("\n".join(lines) + "\n").encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "simulate.json": canonical({"version": 1, "mode": "simulate", "input": "usage.json", "output": "simulated"}),
    }
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


def run(app: Application, root: Path, config: dict, selected: str = "tariff-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"TARIFF_CONFIG": str(root / selected)}, timeout=90)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    report = json.loads((root / config["output"] / "report.json").read_bytes())
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path) -> None:
    result = app.run(root, {}, timeout=20)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert not (root / "output").exists() and not list(root.glob(".tariff-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    exported = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "simulate.json") == archive
    assert files_at(root / "output") == exported
    bills = archive["results"]["bills"]
    assert [unr(row["total"]) for row in bills] == [Fraction(3), Fraction(361, 120), Fraction(3)]
    assert archive["results"]["cheapest"] == ["flat", "twin"]
    assert len(bills[1]["segments"]) == 5
    source = document()
    source["intervals"] = []
    source["tariffs"] = [
        flat("t" + str(i), fee=value) for i, value in enumerate(["0", "0.005", "0.015", "1.005", "1.015"])
    ]
    work = root / "rounding"
    rounded = run(app, work, fixture(work, source))["results"]
    assert [row["rounded_total"] for row in rounded["bills"]] == ["0.00", "0.00", "0.02", "1.00", "1.02"]
    assert rounded["cheapest"] == ["t0"]
    source = document()
    base = dt.datetime(1969, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc)
    source["period"] = {"start": at(0, base), "end": at(3, base)}
    source["intervals"] = [{"start": "1969-12-31T18:59:59-05:00", "end": "1970-01-01T05:00:02+05:00", "kwh": "0"}]
    work = root / "zero-and-offsets"
    result = run(app, work, fixture(work, source))
    assert all(unr(row["energy_charge"]) == 0 for row in result["results"]["bills"])
    assert len(result["results"]["bills"][1]["segments"]) == 2
    return {
        "hand_tariffs": 3,
        "hand_intervals": 3,
        "exact_time_tariff_total": "361/120",
        "rounding_cases": 5,
        "utc_midnight_offsets_and_pre_epoch": True,
        "zero_and_empty_usage": True,
        "exact_ranking_and_ties": True,
        "actual_replay_and_simulation_requests": True,
        "archive_sha256": digest(exported["archive.json"]),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(106)
    archives, partitioned, segments, allocations = [], 0, 0, 0
    denominator_digits = 0
    for batch in range(24):
        source = document()
        source["period"] = {"start": at(0), "end": at(172800)}
        source["intervals"] = []
        cursor = rng.randrange(100)
        for _ in range(32):
            duration = rng.randrange(2, 3500)
            energy = (
                Fraction(duration * rng.randrange(0, 10000), 1000000)
                if batch % 2 == 0
                else Fraction(rng.randrange(10000000), 1000000)
            )
            source["intervals"].append({"start": at(cursor), "end": at(cursor + duration), "kwh": fixed(energy, 6)})
            cursor += duration + rng.randrange(30)
        source["tariffs"] = []
        for index in range(4):
            bands = sorted({0, *[rng.randrange(1, 86400) for _ in range(7)]})
            limits = sorted(rng.sample(range(1, 300), 5))
            source["tariffs"].append(
                {
                    "id": "tariff" + str(index),
                    "fee": fixed(Fraction(rng.randrange(10000), 1000), 3),
                    "bands": [
                        {"start_second": t, "rate": fixed(Fraction(rng.randrange(10000), 1000), 3)} for t in bands
                    ],
                    "tiers": [
                        {"up_to_kwh": str(t), "surcharge": fixed(Fraction(rng.randrange(1000), 1000), 3)}
                        for t in limits
                    ]
                    + [{"up_to_kwh": None, "surcharge": "0.125"}],
                }
            )
        work = root / str(batch)
        archive = run(app, work, fixture(work, source))
        archives.append(digest(canonical(archive)))
        bills = archive["results"]["bills"]
        denominator_digits = max(denominator_digits, *(len(bill["total"]["denominator"]) for bill in bills))
        segments += sum(len(bill["segments"]) for bill in bills)
        allocations += sum(len(segment["allocations"]) for bill in bills for segment in bill["segments"])
        if batch % 2 == 0:
            split = copy.deepcopy(source)
            split["intervals"] = []
            for row in source["intervals"]:
                first, last = seconds(row["start"]), seconds(row["end"])
                cut = rng.randrange(first + 1, last)
                for left, right in [(first, cut), (cut, last)]:
                    energy = Fraction(row["kwh"]) * Fraction(right - left, last - first)
                    assert Fraction(fixed(energy, 6)) == energy
                    split["intervals"].append({"start": utc(left), "end": utc(right), "kwh": fixed(energy, 6)})
            child = root / (str(batch) + "-split")
            changed = run(app, child, fixture(child, split))["results"]
            assert changed["ranking"] == archive["results"]["ranking"]
            for original, revised in zip(bills, changed["bills"]):
                assert {k: v for k, v in original.items() if k != "segments"} == {
                    k: v for k, v in revised.items() if k != "segments"
                }
            partitioned += 1
    assert denominator_digits > 19  # Exact reduced bills exceed the signed 64-bit integer range.
    return {
        "seed": 106,
        "batches": 24,
        "tariffs": 96,
        "intervals": 768,
        "partition_invariance_cases": partitioned,
        "segments_checked": segments,
        "allocations_checked": allocations,
        "independent_fraction_intersection_oracle": True,
        "maximum_denominator_digits": denominator_digits,
        "archives_sha256": digest(canonical(archives)),
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

    for path in [
        ["intervals", 0, "kwh"],
        ["tariffs", 0, "fee"],
        ["tariffs", 0, "bands", 0, "rate"],
        ["tariffs", 0, "tiers", 0, "surcharge"],
    ]:
        for value in [
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
            "01",
            "1.",
            ".1",
            "1e2",
            "nan",
            "inf",
            "１",
            "1.0000001",
            "9999999999",
        ]:
            changed(path, value)
    for path, value in [
        (["version"], True),
        (["version"], 1.0),
        (["version"], 2),
        (["extra"], 1),
        (["period"], None),
        (["intervals"], {}),
        (["tariffs"], []),
        (["tariffs"], document()["tariffs"] * 3),
        (["intervals", 0, "kwh"], "1000000.000001"),
        (["tariffs", 0, "fee"], "1000000.000001"),
        (["tariffs", 0, "bands", 0, "rate"], "1000.000001"),
        (["tariffs", 0, "tiers", 0, "surcharge"], "1000.000001"),
        (["tariffs", 1, "id"], "flat"),
        (["tariffs", 0, "id"], "1bad"),
        (["tariffs", 0, "id"], "a" * 33),
        (["tariffs", 0, "bands"], []),
        (["tariffs", 0, "bands", 0, "start_second"], 1),
        (["tariffs", 0, "bands", 0, "start_second"], False),
        (["tariffs", 1, "bands", 1, "start_second"], 0),
        (["tariffs", 1, "bands", 2, "start_second"], 86400),
        (["tariffs", 0, "tiers"], []),
        (["tariffs", 0, "tiers", 0, "up_to_kwh"], "1"),
        (["tariffs", 1, "tiers", 0, "up_to_kwh"], None),
        (["tariffs", 1, "tiers", 0, "up_to_kwh"], "0"),
        (["tariffs", 1, "tiers", 1, "up_to_kwh"], "1"),
        (["tariffs", 1, "tiers", 1, "up_to_kwh"], "256000000.000001"),
        (["intervals", 0, "start"], at(-1)),
        (["intervals", 0, "end"], at(21599)),
        (["intervals", 1, "start"], at(21601)),
        (["intervals", 2, "end"], at(172801)),
        (["period", "end"], at(0)),
        (["period", "end"], at(2678401)),
        (["intervals", 0, "extra"], 0),
        (["tariffs", 0, "extra"], 0),
        (["tariffs", 0, "bands", 0, "extra"], 0),
        (["tariffs", 0, "tiers", 0, "extra"], 0),
    ]:
        changed(path, value)
    for value in [
        None,
        True,
        "",
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-02-30T00:00:00Z",
        "2026-01-01T00:00:00.000001Z",
        "2026-01-01T00:00:60Z",
        "2026-01-01T00:00:00+24:00",
        "x" * 41,
    ]:
        changed(["intervals", 0, "start"], value)
    cases += [None, [], {}, {"version": 1}]
    for index, source in enumerate(cases):
        work = root / ("source-" + str(index))
        fixture(work)
        save(work / "usage.json", source)
        reject(app, work)
    configs = [
        None,
        [],
        {},
        {"version": 1},
        *[
            {"version": 1, "mode": "simulate", "input": "usage.json", "output": "output", **change}
            for change in [
                {"version": True},
                {"version": 1.0},
                {"version": 2},
                {"mode": "bill"},
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
        save(work / "tariff-job.json", config)
        reject(app, work)
    raw_cases = [
        b"",
        b"{",
        b"[] trailing",
        b' {"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":01}',
        b'{"x":"\xff"}',
        b'{"x":"\\ud800"}',
        b'{"x":true} null',
    ]
    for name in ["tariff-job.json", "usage.json", "archive.json"]:
        for index, raw in enumerate(raw_cases):
            work = root / (name + str(index))
            config = fixture(work)
            if name == "archive.json":
                config.update(mode="verify", input=name)
                save(work / "tariff-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    archive = {"version": 1, "source": document(), "results": expected(document())}
    paths = [
        ["version"],
        ["results", "bills", 0, "total", "numerator"],
        ["results", "bills", 0, "rounded_total"],
        ["results", "ranking"],
        ["results", "cheapest"],
        ["results", "bills", 1, "segments", 0, "band"],
        ["results", "bills", 1, "segments", 0, "allocations", 0, "tier"],
        ["source", "intervals", 0, "kwh"],
    ]
    values = [1.0, "999", "9.99", [], [], 0.0, False, "2"]
    for index, (path, value) in enumerate(zip(paths, values)):
        tampered = copy.deepcopy(archive)
        target = tampered
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        work = root / ("tampered-" + str(index))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "tariff-job.json", config)
        save(work / "archive.json", tampered)
        reject(app, work)
    return {
        "invalid_sources": len(cases),
        "invalid_requests": len(configs),
        "invalid_json_per_input": len(raw_cases),
        "tampered_archives": len(paths),
        "strict_cached_numeric_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    source = document()
    source["period"] = {"start": at(0), "end": at(2678400)}
    source["intervals"] = [{"start": at(i * 10462), "end": at((i + 1) * 10462), "kwh": "1000000"} for i in range(256)]
    source["tariffs"] = [
        {
            "id": "t" + str(i),
            "fee": "1000000",
            "bands": [{"start_second": j * 5400, "rate": "1000"} for j in range(16)],
            "tiers": [{"up_to_kwh": str(j * 32000000), "surcharge": "1000"} for j in range(1, 8)]
            + [{"up_to_kwh": None, "surcharge": "1000"}],
        }
        for i in range(8)
    ]
    work = root / "all-limits"
    result = run(app, work, fixture(work, source))
    assert all(unr(row["total"]) == 512001000000 for row in result["results"]["bills"])
    edges = document()
    edges["period"] = {"start": at(0), "end": at(3)}
    edges["intervals"] = [{"start": at(i), "end": at(i + 1), "kwh": str(value)} for i, value in enumerate([1, 0, 1])]
    edges["tariffs"] = [
        {
            "id": "edge",
            "fee": "0",
            "bands": [{"start_second": 0, "rate": "0"}, {"start_second": 1, "rate": "1"}],
            "tiers": [{"up_to_kwh": "1", "surcharge": "0"}, {"up_to_kwh": None, "surcharge": "2"}],
        }
    ]
    work = root / "exact-tier-boundary"
    edge_bill = run(app, work, fixture(work, edges))["results"]["bills"][0]
    assert unr(edge_bill["total"]) == 3 and edge_bill["segments"][1]["allocations"] == []
    edges["period"] = {"start": at(86398), "end": at(86401)}
    edges["intervals"] = [{"start": at(86398), "end": at(86401), "kwh": "0.000003"}]
    edges["tariffs"][0]["bands"] = [{"start_second": 0, "rate": "0.000001"}, {"start_second": 86399, "rate": "1000"}]
    edges["tariffs"][0]["tiers"] = [{"up_to_kwh": "256000000", "surcharge": "0"}, {"up_to_kwh": None, "surcharge": "0"}]
    work = root / "last-second-and-minimum-decimal"
    edge_bill = run(app, work, fixture(work, edges))["results"]["bills"][0]
    assert unr(edge_bill["total"]) == Fraction("0.001000000002") and len(edge_bill["segments"]) == 3
    for label, path, extra in [
        ("intervals", ["intervals"], source["intervals"][-1]),
        ("bands", ["tariffs", 0, "bands"], {"start_second": 86399, "rate": "0"}),
        ("tiers", ["tariffs", 0, "tiers"], {"up_to_kwh": None, "surcharge": "0"}),
    ]:
        over = copy.deepcopy(source)
        target = over
        for key in path:
            target = target[key]
        target.append(extra)
        work = root / ("over-" + label)
        fixture(work, over)
        reject(app, work)
    for label, start, end in [
        ("first-year", "0001-01-01T00:00:00Z", "0001-01-02T00:00:00Z"),
        ("last-year", "9999-12-30T00:00:00Z", "9999-12-31T23:59:59Z"),
        ("leap-day", "2000-02-28T23:59:59Z", "2000-03-01T00:00:01Z"),
    ]:
        item = document()
        item["period"] = {"start": start, "end": end}
        item["intervals"] = [{"start": start, "end": end, "kwh": "0.000001"}]
        work = root / label
        run(app, work, fixture(work, item))
    work = root / "exact-bytes"
    config = fixture(work)
    for name, size in [("tariff-job.json", 65536), ("usage.json", 2097152)]:
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("tariff-job.json", 65536), ("usage.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "tariff-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "intervals": 256,
        "tariffs": 8,
        "bands": 16,
        "tiers": 8,
        "period_seconds": 2678400,
        "maximum_bill": "512001000000",
        "decimal_places": 6,
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
        "calendar_boundaries": 3,
        "exact_tier_and_last_band_boundaries": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document()
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"TARIFF_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".tariff-*")) and (work / "output").exists() == (stage == "published")
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
            env=app.environment({"TARIFF_PAUSE": stage, "TARIFF_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".tariff-*"))) == (1 if stage == "staged" else 0)
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
                    name = "tariff-job.json" if mutation == "request" else "usage.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".tariff-*"))
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
        ["tariff-job.json", "usage.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "tariff-job.json")
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
        print(app.engine + " tariff simulator " + name + ": passed", flush=True)
    return observations
