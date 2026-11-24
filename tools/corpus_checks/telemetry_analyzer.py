"""Whole-project telemetry verification: independent statistics, prior windows, exact gaps and portable replay."""

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
from .trend_fixture import canonical, digest, document, inspect_series, series


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def fixture(root: Path, source: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "mode": "analyze", "input": "telemetry.json", "output": "output"}
    save(root / "trend-job.json", config)
    save(root / "telemetry.json", document() if source is None else source)
    return config


def inspect(root: Path, config: dict, reasons: dict[str, str] | None = None) -> dict:
    reasons = {} if reasons is None else reasons
    imported = json.loads((root / config["input"]).read_bytes())
    source = imported["source"] if config["mode"] == "verify" else imported
    directory = root / config["output"]
    raw = (directory / "archive.json").read_bytes()
    archive = json.loads(raw)
    assert archive.keys() == {"version", "source", "results"}
    assert type(archive["version"]) is int and archive["version"] == 1
    assert canonical(archive["source"]) == canonical(source) and raw == canonical(archive)
    assert len(archive["results"]) == len(source["series"])
    counts = {"analyzed": 0, "rejected": 0, "samples": 0, "gaps": 0, "outliers": 0}
    lines = []
    for row, result in zip(source["series"], archive["results"]):
        name = row["id"]
        if name in reasons:
            assert result == {"id": name, "status": "rejected", "reason": reasons[name]}, result
            counts["rejected"] += 1
            lines.append(name + ": rejected: " + reasons[name])
        else:
            inspect_series(row, result, source["settings"])
            counts["analyzed"] += 1
            counts["samples"] += result["samples"]
            counts["gaps"] += len(result["gaps"])
            counts["outliers"] += result["outliers"]
            lines.append(
                f'{name}: {result["samples"]} samples; {result["outliers"]} outliers; '
                + str(len(result["gaps"]))
                + " gaps; mean "
                + canonical(result["statistics"]["mean"]).decode().strip()
                + "; variance "
                + canonical(result["statistics"]["population_variance"]).decode().strip()
            )
    report = {"version": 1, "mode": config["mode"], "summary": counts, "archive_sha256": digest(raw)}
    files = {
        "archive.json": raw,
        "telemetry.json": canonical(source),
        "report.json": canonical(report),
        "report.txt": (
            "\n".join(
                [
                    "Telemetry trends: trailing count windows; population variance",
                    canonical(counts).decode().strip(),
                    *lines,
                ]
            )
            + "\n"
        ).encode(),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
        "analyze.json": canonical({"version": 1, "mode": "analyze", "input": "telemetry.json", "output": "analyzed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    if config["mode"] == "verify":
        assert canonical(imported["results"]) == canonical(archive["results"])
    return archive


def run(
    app: Application, root: Path, config: dict, reasons: dict | None = None, selected: str = "trend-job.json"
) -> dict:
    unchanged = {
        root / selected: (root / selected).read_bytes(),
        root / config["input"]: (root / config["input"]).read_bytes(),
    }
    result = app.run(root, {"TREND_CONFIG": str(root / selected)}, timeout=90)
    assert result.returncode == int(bool(reasons)) and not result.stderr, (root, result)
    archive = inspect(root, config, reasons)
    report = json.loads((root / config["output"] / "report.json").read_bytes())
    assert result.stdout == canonical(report["summary"]).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str, reasons: dict | None = None) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), reasons, name)


def reject(app: Application, root: Path, reason: str = "") -> None:
    result = app.run(root, {}, timeout=20)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert reason in result.stderr, (reason, result)
    assert not (root / "output").exists() and not list(root.glob(".trend-*"))
    return  # noqa: PLR1711


def semantics(app: Application, root: Path) -> dict:
    config = fixture(root)
    archive = run(app, root, config)
    original = files_at(root / "output")
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "analyze.json") == archive
    assert files_at(root / "output") == original
    by_name = {row["id"]: row for row in archive["results"]}
    assert by_name["latency"]["points"][4]["decision"]["status"] == "outlier"
    assert by_name["latency"]["points"][6]["baseline"]["statistics"]["count"] == 0
    assert by_name["constant"]["points"][4]["decision"]["status"] == "constant_shift"
    assert by_name["large_offset"]["points"][1]["window"]["statistics"]["population_variance"] == 1.0
    assert by_name["large_offset"]["points"][4]["decision"]["deviation"] == 7.0
    assert by_name["cancellation"]["statistics"]["mean"] == 1 / 6
    assert [row["timestamp_us"] for row in by_name["offsets"]["points"]] == [0, 1, 3000001, 6000003]
    assert [row["after_index"] for row in by_name["offsets"]["gaps"]] == [3]
    work = root / "thresholds"
    source = document(
        [
            series("tie_up", [1, 3, 5]),
            series("above", [1, 3, math.nextafter(5.0, math.inf)]),
            series("tie_down", [1, 3, -1]),
            series("rounded_below", [1, 3, math.nextafter(-1.0, -math.inf)]),
            series("below", [1, 3, -1.000000000000001]),
        ],
        window=2,
        warmup=2,
    )
    boundaries = run(app, work, fixture(work, source))
    assert [row["points"][2]["decision"]["status"] for row in boundaries["results"]] == [
        "within",
        "outlier",
        "within",
        "within",
        "outlier",
    ]
    work = root / "no-series"
    assert run(app, work, fixture(work, document([])))["results"] == []
    return {
        "hand_series": 8,
        "hand_samples": sum(row["samples"] for row in archive["results"]),
        "threshold_boundaries": 5,
        "empty_and_constant_series": True,
        "large_offset_variance": True,
        "microsecond_gap_and_offset_normalization": True,
        "current_sample_excluded_from_baseline": True,
        "actual_replay_and_reanalysis_requests": True,
        "archive_sha256": digest(original["archive.json"]),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(105)
    hashes, gap_count, outlier_count = [], 0, 0
    for batch in range(16):
        rows = []
        window = rng.randrange(2, 17)
        for pair in range(4):
            pattern = (batch + pair) % 8
            ticks, values, now = [], [], 0
            for index in range(32):
                now += 20 if index in [11, 22] else rng.randrange(1, 4)
                ticks.append(now)
                if pattern == 0:
                    value = 3.25
                elif pattern == 1:
                    value = 1e16 + 2 * rng.randrange(-20, 21)
                elif pattern == 2:
                    value = rng.randrange(1, 101) * 1e-95
                elif pattern == 3:
                    value = [1e95, 1.0, -1e95][index % 3]
                elif pattern == 4:
                    value = float(rng.randrange(0, 30) if index % 9 else 1000)
                elif pattern == 5:
                    value = -1e10 + rng.randrange(-20, 21) / 8
                elif pattern == 6:
                    value = float(rng.choice([-1, 1])) * 10.0 ** rng.randrange(-95, 96)
                else:
                    value = rng.choice([0.0, 0.0, 1e90, -1e90])
                values.append(value)
            rows.extend(
                [
                    series("base" + str(pair), values, ticks),
                    series("scaled" + str(pair), [2 * v for v in values], ticks),
                ]
            )
        source = document(
            rows, window=window, warmup=min(window, 3), gap_us=12000000, sigma=rng.choice([1.5, 2.0, 3.0])
        )
        work = root / str(batch)
        archive = run(app, work, fixture(work, source))
        for first, second in zip(archive["results"][::2], archive["results"][1::2]):
            assert first["gaps"] == second["gaps"] and first["outliers"] == second["outliers"]
            for a, b in zip(first["points"], second["points"]):
                assert a["decision"]["status"] == b["decision"]["status"]
                for key, scale in [
                    ("mean", 2),
                    ("minimum", 2),
                    ("maximum", 2),
                    ("population_variance", 4),
                    ("standard_deviation", 2),
                ]:
                    assert (a["window"]["statistics"][key] * scale).hex() == b["window"]["statistics"][key].hex()
        gap_count += sum(len(row["gaps"]) for row in archive["results"])
        outlier_count += sum(row["outliers"] for row in archive["results"])
        hashes.append(digest(canonical(archive)))
    return {
        "seed": 105,
        "batches": 16,
        "series": 128,
        "samples": 4096,
        "scaling_pairs": 64,
        "gaps": gap_count,
        "outliers": outlier_count,
        "exact_rational_and_decimal_oracle": True,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid_series() -> list[tuple[dict, str]]:
    rows = []
    for value in [None, {}, "samples", 2]:
        rows.append(({"id": "bad" + str(len(rows)), "samples": value}, "expected sample array"))
    for value in [
        None,
        1,
        [],
        {},
        {"at": "2026-01-01T00:00:00Z"},
        {"at": "2026-01-01T00:00:00Z", "value": 1, "extra": 2},
    ]:
        rows.append(
            (
                {"id": "bad" + str(len(rows)), "samples": [value]},
                "unexpected fields" if isinstance(value, dict) else "expected object",
            )
        )
    for at in [
        None,
        True,
        [],
        "",
        "2026-01-01",
        "2026-01-01T00:00:00",
        "2026-02-30T00:00:00Z",
        "2026-01-01T24:00:00Z",
        "2026-01-01T00:00:60Z",
        "2026-01-01T00:00:00.0000001Z",
        "2026-01-01T00:00:00+24:00",
        "2026-01-01T00:00:00+00:60",
        "0001-01-01T00:00:00+01:00",
        "9999-12-31T23:59:59-01:00",
        "x" * 41,
    ]:
        rows.append(
            ({"id": "bad" + str(len(rows)), "samples": [{"at": at, "value": 1}]}, "invalid timestamp at sample 0")
        )
    for value in [
        True,
        None,
        [],
        {},
        "",
        "nan",
        "inf",
        "1e309",
        "1e101",
        "1e-101",
        "1e-999",
        "-1e-999",
        "1__2",
        "0x1p0",
        "１",
        " 1",
        "0" * 65,
        1e101,
        1e-101,
    ]:
        rows.append(
            (
                series("bad" + str(len(rows)), [value]),
                "expected zero or finite numeric value with magnitude 1e-100..1e100",
            )
        )
    for times in [[0, 0], [1, 0]]:
        rows.append(
            (series("bad" + str(len(rows)), [1, 2], times), "timestamps must be strictly increasing at sample 1")
        )
    rows.append(
        (
            {
                "id": "bad" + str(len(rows)),
                "samples": [
                    {"at": "1970-01-01T00:00:00Z", "value": 1},
                    {"at": "1970-01-01T05:00:00+05:00", "value": 2},
                ],
            },
            "timestamps must be strictly increasing at sample 1",
        )
    )
    return rows


def invalid(app: Application, root: Path) -> dict:
    bad = invalid_series()
    for index in range(0, len(bad), 7):
        selected = bad[index : index + 7]
        source = document([row for row, _ in selected] + [series("after_errors", [1, 2, 3])])
        reasons = {row["id"]: reason for row, reason in selected}
        work = root / ("series-" + str(index))
        archive = run(app, work, fixture(work, source), reasons)
        assert consume(app, work / "output", "replay.json", reasons) == archive
    changes = [
        {"window": 1},
        {"window": 257},
        {"window": True},
        {"window": 4.0},
        {"warmup": 1},
        {"warmup": 5},
        {"gap_us": 0},
        {"gap_us": 86400000001},
        {"gap_us": 1.0},
        {"gap_us": False},
        {"sigma": 0.09},
        {"sigma": 20.01},
        {"sigma": True},
        {"extra": 1},
    ]
    for index, change in enumerate(changes):
        work = root / ("settings-" + str(index))
        fixture(work, document([], **change))
        reject(app, work)
    invalid_docs = [
        None,
        [],
        {},
        {**document([]), "version": True},
        {**document([]), "version": 1.0},
        {**document([]), "version": 2},
        {**document([]), "extra": 1},
        {**document([]), "series": {}},
        document([series("same", []), series("same", [])]),
        document([series("1bad", [])]),
        document([series("a" * 33, [])]),
        document([None]),
        document([{"id": "missing"}]),
        {**document([]), "settings": None},
    ]
    for index, value in enumerate(invalid_docs):
        work = root / ("source-" + str(index))
        fixture(work)
        save(work / "telemetry.json", value)
        reject(app, work)
    invalid_requests = [
        None,
        [],
        {},
        {"version": True},
        {"version": 1.0},
        {"version": 2},
        {"mode": "unknown"},
        {"input": ""},
        {"output": ""},
        {"input": None},
        {"output": []},
        {"extra": 1},
    ]
    for index, value in enumerate(invalid_requests):
        work = root / ("request-" + str(index))
        config = fixture(work)
        save(work / "trend-job.json", {**config, **value} if isinstance(value, dict) and value else value)
        reject(app, work)
    raw_bad = [
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e999}',
        b'{"x":9223372036854775808}',
        b'{"x":"\\ud800"}',
        b"{} {}",
        b'{"x":1,}',
        b"\xff",
        b"",
    ]
    for index, raw in enumerate(raw_bad):
        for name in ["trend-job.json", "telemetry.json"]:
            work = root / ("raw-" + str(index) + name)
            fixture(work)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "seed"
    archive = run(app, work, fixture(work))
    for mutation in range(18):
        altered = copy.deepcopy(archive)
        row = altered["results"][0]
        point = row["points"][4]
        if mutation == 0:
            altered["version"] = True
        elif mutation == 1:
            altered["extra"] = 1
        elif mutation == 2:
            altered["source"]["series"][0]["samples"][4]["value"] = 10
        elif mutation == 3:
            row["statistics"]["mean"] = 100.0
        elif mutation == 4:
            point["window"]["statistics"]["population_variance"] = 0.0
        elif mutation == 5:
            point["baseline"]["start_index"] = 1
        elif mutation == 6:
            point["baseline"]["statistics"]["count"] = 4.0
        elif mutation == 7:
            point["baseline"]["statistics"]["mean"] = 10
        elif mutation == 8:
            point["timestamp_us"] = float(point["timestamp_us"])
        elif mutation == 9:
            point["decision"]["status"] = "within"
        elif mutation == 10:
            point["decision"]["z_score"] = 0.0
        elif mutation == 11:
            row["gaps"][0]["elapsed_us"] += 1
        elif mutation == 12:
            row["outliers"] += 1
        elif mutation == 13:
            row["points"].reverse()
        elif mutation == 14:
            row["points"].pop()
        elif mutation == 15:
            point["utc"] = "1970-01-01T00:00:00.000000+00:00"
        elif mutation == 16:
            point["baseline"]["statistics"]["center"]["mean_offset"] = 1.0
        else:
            altered["results"] = []
        work = root / ("tampered-" + str(mutation))
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "trend-job.json", config)
        save(work / "archive.json", altered)
        reject(app, work)
    return {
        "invalid_series": len(bad),
        "later_series_continue": True,
        "rejected_series_replay": True,
        "invalid_settings": len(changes),
        "invalid_documents": len(invalid_docs),
        "invalid_requests": len(invalid_requests),
        "invalid_json_per_input": len(raw_bad),
        "tampered_archives": 18,
        "strict_cached_numeric_types": True,
    }


def limits(app: Application, root: Path) -> dict:
    work = root / "full"
    source = document(
        [series("a" * 32, [1e16 + 2 * (i % 7) for i in range(4096)])],
        window=256,
        warmup=256,
        gap_us=86400000000,
        sigma=20,
    )
    archive = run(app, work, fixture(work, source))
    assert archive["results"][0]["points"][255]["decision"]["status"] == "warming"
    assert archive["results"][0]["points"][256]["decision"]["status"] == "within"
    for label, source in [
        ("samples", document([series("many", [1] * 4097)])),
        ("series", document([series("s" + str(i), []) for i in range(9)])),
    ]:
        work = root / ("over-" + label)
        fixture(work, source)
        reject(app, work)
    rows = [
        series("minimum", [0, 1e-100, -1e-100]),
        series("maximum", [1e100, -1e100, 0]),
        series("spelling", ["0" * 63 + "1"]),
        {
            "id": "calendar",
            "samples": [{"at": "0001-01-01T00:00:00Z", "value": 0}, {"at": "9999-12-31T23:59:59.999999Z", "value": 1}],
        },
    ]
    work = root / "values"
    run(app, work, fixture(work, document(rows, window=2, warmup=2, gap_us=1, sigma=0.1)))
    work = root / "exact-bytes"
    config = fixture(work, document([series("small", [1, 2, 3])]))
    for name, size in [("trend-job.json", 65536), ("telemetry.json", 2097152)]:
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size, b" "))
    archive = run(app, work, config)
    for name, size in [("trend-job.json", 65536), ("telemetry.json", 2097152)]:
        work = root / ("over-" + name)
        fixture(work, document([]))
        p = work / name
        p.write_bytes(p.read_bytes().ljust(size + 1, b" "))
        reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        config = fixture(work)
        config.update(mode="verify", input="archive.json")
        save(work / "trend-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work)
        else:
            run(app, work, config)
    return {
        "samples_total": 4096,
        "series": 8,
        "window": 256,
        "warmup_boundary": True,
        "gap_microseconds": [1, 86400000000],
        "sigma": [0.1, 20],
        "numeric_spelling_characters": 64,
        "value_magnitude": "0 or 1e-100..1e100",
        "request_bytes": 65536,
        "source_bytes": 2097152,
        "archive_bytes": 16777216,
        "full_supported_calendar": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = document([series("seed", [1, 3, 5])])
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"TREND_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".trend-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "network", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"TREND_PAUSE": stage, "TREND_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".trend-*"))) == (1 if stage == "staged" else 0)
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
                    name = "trend-job.json" if mutation == "request" else "telemetry.json"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".trend-*"))
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
        ["trend-job.json", "telemetry.json"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "trend-job.json")
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
        print(app.engine + " telemetry analyzer " + name + ": passed", flush=True)
    return observations
