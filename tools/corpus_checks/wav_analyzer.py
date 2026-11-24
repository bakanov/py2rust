"""Whole-project mono PCM processing, exact independent samples and portable native exports."""

from __future__ import annotations

import copy
import itertools
import json
import math
import os
import random
import select
import struct
import subprocess
from pathlib import Path

from .common import Application
from .wav_fixture import (
    canonical,
    chunks,
    digest,
    inspect_csv,
    inspect_results,
    inspect_svg,
    parts_of,
    pcm_wave,
    read_wave,
)


def save(path: Path, value: object) -> None:
    path.write_bytes(canonical(value))
    return  # noqa: PLR1711


def files_at(path: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}


def gain(numerator: int, denominator: int = 1) -> dict:
    return {"method": "gain", "numerator": numerator, "denominator": denominator}


def fixture(
    root: Path,
    samples: list[int] | None = None,
    settings: dict | None = None,
    rate: int = 8000,
    source: bytes | None = None,
) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "mode": "process",
        "input": "source.wav",
        "output": "output",
        "settings": gain(3, 2) if settings is None else settings,
    }
    save(root / "wav-job.json", config)
    values = [-32768, -20000, -3, -2, -1, 0, 1, 2, 3, 20000, 32767] if samples is None else samples
    (root / "source.wav").write_bytes(pcm_wave(values, rate) if source is None else source)
    return config


def inspect(root: Path, config: dict) -> dict:
    imported = (root / config["input"]).read_bytes()
    if config["mode"] == "verify":
        original = json.loads(imported)
        source, settings = bytes.fromhex(original["source_hex"]), original["settings"]
    else:
        source, settings = imported, config["settings"]
    directory = root / config["output"]
    raw = (directory / "archive.json").read_bytes()
    archive = json.loads(raw)
    assert archive.keys() == {"version", "source_hex", "settings", "results"}
    assert type(archive["version"]) is int and archive["version"] == 1
    assert raw == canonical(archive) and archive["source_hex"] == source.hex()
    assert canonical(archive["settings"]) == canonical(settings)
    results = archive["results"]
    before, after = inspect_results(source, settings, results)
    normalized = (directory / "normalized.wav").read_bytes()
    assert normalized == pcm_wave(after, results["sample_rate"])
    assert read_wave(normalized) == (results["sample_rate"], after)
    csv = (directory / "samples.csv").read_bytes()
    svg = (directory / "waveform.svg").read_bytes()
    report = (directory / "report.json").read_bytes()
    inspect_csv(csv, before, after)
    inspect_svg(svg, results)
    assert canonical(json.loads(report)) == canonical({"version": 1, "mode": config["mode"], "results": results})
    files = {
        "original.wav": source,
        "normalized.wav": normalized,
        "archive.json": raw,
        "report.json": report,
        "waveform.svg": svg,
        "samples.csv": csv,
        "process.json": canonical(
            {"version": 1, "mode": "process", "input": "original.wav", "settings": settings, "output": "processed"}
        ),
        "replay.json": canonical({"version": 1, "mode": "verify", "input": "archive.json", "output": "replayed"}),
    }
    files["manifest.json"] = canonical(
        {name: {"bytes": len(data), "sha256": digest(data)} for name, data in files.items()}
    )
    assert files_at(directory) == files and {p.name for p in directory.iterdir()} == set(files)
    if config["mode"] == "verify":
        assert canonical(original) == raw
    return archive


def run(app: Application, root: Path, config: dict, selected: str = "wav-job.json") -> dict:
    unchanged = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"WAV_CONFIG": str(root / selected)}, timeout=120)
    assert result.returncode == 0 and not result.stderr, (root, result)
    archive = inspect(root, config)
    rows = archive["results"]
    summary = {
        "samples": rows["input"]["samples"],
        "clipped_low": rows["clipped_low"],
        "clipped_high": rows["clipped_high"],
    }
    assert result.stdout == canonical(summary).decode()
    assert all(path.read_bytes() == raw for path, raw in unchanged.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr, (needle, result)
    assert not (root / "output").exists() and not list(root.glob(".wav-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, settings: dict, stem: str, source: bytes | None = None) -> dict:
    original = files_at(root)
    config = json.loads((root / "process.json").read_bytes())
    config.update(settings=settings, output=stem)
    if source is not None:
        config["input"] = stem + ".wav"
        (root / config["input"]).write_bytes(source)
    save(root / (stem + "-job.json"), config)
    archive = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    return archive


def semantics(app: Application, root: Path) -> dict:
    archive = run(app, root, fixture(root))
    assert archive["results"]["clipped_low"] == archive["results"]["clipped_high"] == 1
    assert consume(app, root / "output", "replay.json") == archive
    assert consume(app, root / "output", "process.json") == archive
    cases = [
        ([], {"method": "peak", "target": 32767}, 1),
        ([0] * 17, {"method": "peak", "target": 32767}, 384000),
        ([-32768], {"method": "peak", "target": 32767}, 44100),
        ([32767], {"method": "peak", "target": 1}, 48000),
        ([100, 200, 300], {"method": "peak", "target": 32767}, 22050),
        ([-100, -200, -300], {"method": "peak", "target": 32767}, 22050),
        ([-3, -2, -1, 0, 1, 2, 3], gain(1, 2), 8000),
        ([-9, -3, 3, 9], gain(1, 6), 8000),
        ([-32768, 32767], gain(0, 1000000), 8000),
        ([-32768, 32767], gain(1000000), 8000),
        ([-32768, 32767], gain(1, 1000000), 8000),
        (list(range(-128, 129)), gain(1), 32000),
    ]
    for index, (samples, settings, rate) in enumerate(cases):
        work = root / str(index)
        run(app, work, fixture(work, samples, settings, rate))
    parts = parts_of(pcm_wave([-32768, -1, 0, 1, 32767]))
    extended = (b"fmt ", parts[0][1] + b"\xff\xff")
    variants = [
        [(b"JUNK", b"odd"), parts[0], (b"LIST", b"INFOtitle"), parts[1], (b"tail", b"x")],
        [parts[1], (b"\xff\0\1\2", b"opaque"), parts[0]],
        [extended, parts[1]],
    ]
    for index, variant in enumerate(variants):
        work = root / ("chunks-" + str(index))
        found = run(app, work, fixture(work, source=chunks(variant, pad=b"\xa5")))
        assert len(found["results"]["chunks"]) == len(variant)
    # Exercise every signed16 input value under exact half ties, clipping and peak normalization.
    all_samples = list(range(-32768, 32768))
    exhaustive = [gain(1), gain(1, 2), gain(1, 6), gain(3, 2), {"method": "peak", "target": 32767}]
    for index, settings in enumerate(exhaustive):
        work = root / ("signed16-" + str(index))
        run(app, work, fixture(work, all_samples, settings))
    return {
        "hand_cases": len(cases) + 1,
        "chunk_layout_variants": len(variants),
        "exhaustive_signed16_inputs": 65536,
        "exhaustive_gain_cases": len(exhaustive),
        "decimal_rounding_precision": 50,
        "rms_decimal_precision": 70,
        "all_samples_csv_and_waveform_checked": True,
        "actual_replay_and_processing_requests": True,
        "archive_sha256": digest(canonical(archive)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(112)
    hashes = []
    samples_checked = 0
    for index in range(24):
        count = rng.choice([2, 255, 256, 257, 511, 1025, 4097])
        samples = [rng.randint(-32768, 32767) for _ in range(count)]
        settings = (
            {"method": "peak", "target": rng.randint(1, 32767)}
            if index % 2
            else gain(rng.randint(0, 1000000), rng.randint(1, 1000000))
        )
        rate = rng.choice([1, 8000, 44100, 48000, 384000])
        work = root / str(index)
        first = run(app, work, fixture(work, samples, settings, rate))
        reverse = edit_export(app, work / "output", settings, "reverse", pcm_wave(list(reversed(samples)), rate))
        assert first["results"]["input"] == reverse["results"]["input"]
        assert first["results"]["output"] == reverse["results"]["output"]
        assert read_wave((work / "output/reverse/normalized.wav").read_bytes())[1] == list(
            reversed(read_wave((work / "output/normalized.wav").read_bytes())[1])
        )
        normalized = edit_export(app, work / "output", {"method": "peak", "target": 30000}, "peak")
        stable = edit_export(
            app,
            work / "output/peak",
            {"method": "peak", "target": 30000},
            "again",
            (work / "output/peak/normalized.wav").read_bytes(),
        )
        assert (work / "output/peak/normalized.wav").read_bytes() == (
            work / "output/peak/again/normalized.wav"
        ).read_bytes()
        assert stable["results"]["changed_samples"] == 0
        assert consume(app, work / "output/peak", "replay.json") == normalized
        samples_checked += count
        hashes.extend(
            [
                digest(canonical(first)),
                digest(canonical(reverse)),
                digest(canonical(normalized)),
                digest(canonical(stable)),
            ]
        )
    return {
        "seed": 112,
        "generated_cases": 24,
        "primary_samples": samples_checked,
        "reversed_cases": 24,
        "peak_idempotence_cases": 24,
        "edited_exports_replayed": 24,
        "archives_sha256": digest(canonical(hashes)),
    }


def invalid(app: Application, root: Path) -> dict:
    configs = []
    default = {"version": 1, "mode": "process", "input": "source.wav", "output": "output", "settings": gain(1)}
    for key, values in [
        ("version", [None, 0, 2, True, 1.0, "1"]),
        ("mode", [None, False, 1, "", "normalize"]),
        ("input", [None, 1, "", "missing", "x\0y"]),
        ("output", [None, 1, "", "source.wav", "missing/parent/out", "x\0y"]),
    ]:
        configs.extend(dict(default, **{key: value}) for value in values)
    configs.extend({key: value for key, value in default.items() if key != omitted} for omitted in default)
    configs.append(dict(default, extra=1))
    bad_settings = [
        None,
        True,
        [],
        1,
        {},
        {"method": "other"},
        {"method": "peak"},
        {"method": "gain"},
        dict(gain(1), extra=1),
    ]
    for target in [None, True, 1.0, "1", 0, -1, 32768]:
        bad_settings.append({"method": "peak", "target": target})
    for key, values in [
        ("numerator", [None, True, 1.0, "1", -1, 1000001]),
        ("denominator", [None, True, 1.0, "1", 0, -1, 1000001]),
    ]:
        bad_settings.extend(dict(gain(1), **{key: value}) for value in values)
    configs.extend(dict(default, settings=value) for value in bad_settings)
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "wav-job.json", config)
        reject(app, work)
    malformed = [
        b"",
        b"{}{}",
        b"[] trailing",
        b'{"version":1,"version":1}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":1e9999}',
        b"\xff",
        b'{"x":"\\ud800"}',
    ]
    for slot in ["request", "archive"]:
        for index, raw in enumerate(malformed):
            work = root / (slot + "-json-" + str(index))
            config = fixture(work)
            name = "wav-job.json"
            if slot == "archive":
                name = "archive.json"
                config = {"version": 1, "mode": "verify", "input": name, "output": "output"}
                save(work / "wav-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "baseline"
    archive = run(app, work, fixture(work))
    paths = [
        (("version",), 1.0),
        (("version",), True),
        (("source_hex",), None),
        (("source_hex",), archive["source_hex"].upper()),
        (("source_hex",), " " + archive["source_hex"]),
        (("source_hex",), archive["source_hex"][:-1]),
        (("source_hex",), "00" + archive["source_hex"][2:]),
        (("settings", "numerator"), 4),
        (("results", "sample_rate"), 8000.0),
        (("results", "changed_samples"), True),
        (("results", "input", "rms"), math.nextafter(archive["results"]["input"]["rms"], math.inf)),
        (("results", "input", "mean"), 0),
        (("results", "output", "sum_squares"), 1),
        (("results", "chunks", 0, "offset"), 13),
        (("results", "chunks", 0, "sha256"), "0" * 64),
        (("results", "gain", "denominator"), 3),
        (("results", "waveform", 0, "start"), 1),
        (("results", "clipped_low"), 0),
        (("results", "normalized_sha256"), "0" * 64),
        (("results",), None),
    ]
    altered = []
    for path, value in paths:
        changed = copy.deepcopy(archive)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        altered.append(changed)
    altered.extend({key: value for key, value in archive.items() if key != omitted} for omitted in archive)
    altered.append(dict(archive, extra=1))
    for index, changed in enumerate(altered):
        work = root / ("tampered-" + str(index))
        fixture(work)
        save(work / "wav-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests_and_settings": len(configs),
        "malformed_json_per_input": len(malformed),
        "tampered_archives": len(altered),
        "one_ulp_rms_and_strict_cached_types": True,
    }


def malformed(app: Application, root: Path) -> dict:
    raw = pcm_wave([-32768, 0, 32767])
    basic = parts_of(raw)
    bad = [(raw[:size], "") for size in range(len(raw))]
    bad.extend(
        [
            (b"RIFX" + raw[4:], "expected RIFF/WAVE"),
            (raw[:8] + b"AVI " + raw[12:], "expected RIFF/WAVE"),
            (raw + b"x", "RIFF length"),
            (raw[:4] + struct.pack("<I", 1) + raw[8:], "RIFF length"),
            (chunks([basic[0]]), "format and data"),
            (chunks([basic[1]]), "format and data"),
            (chunks([basic[0], *basic]), "duplicate"),
            (chunks([*basic, basic[1]]), "duplicate"),
            (chunks([basic[0], (b"data", b"x")]), "sample alignment"),
            (chunks([(b"fmt ", basic[0][1] + b"x"), basic[1]]), "format chunk"),
            (chunks([(b"fmt ", b""), basic[1]]), "format chunk"),
        ]
    )
    for offset, fmt, values, needle in [
        (0, "H", [0, 3, 0xFFFE], "integer PCM"),
        (2, "H", [0, 2], "mono signed16"),
        (14, "H", [0, 8, 24, 32], "mono signed16"),
        (4, "I", [0, 384001], "sample rate range"),
        (8, "I", [0, 1, 16001], "byte rate or alignment"),
        (12, "H", [0, 1, 4], "byte rate or alignment"),
    ]:
        for value in values:
            changed = bytearray(basic[0][1])
            struct.pack_into("<" + fmt, changed, offset, value)
            bad.append((chunks([(b"fmt ", bytes(changed)), basic[1]]), needle))
    # Preserve the outer length while damaging the inner framing; missing odd padding is independently detected.
    for tail, needle in [
        (b"x", "truncated chunk header"),
        (b"JUNK" + struct.pack("<I", 0xFFFFFFFF), "truncated chunk or padding"),
        (b"JUNK" + struct.pack("<I", 1) + b"x", "truncated chunk or padding"),
    ]:
        body = raw[8:] + tail
        bad.append((b"RIFF" + struct.pack("<I", len(body)) + body, needle))
    for index, (source, needle) in enumerate(bad):
        work = root / str(index)
        fixture(work, source=source)
        reject(app, work, needle)
    return {
        "all_proper_prefixes": len(raw),
        "other_malformed_wave_cases": len(bad) - len(raw),
        "bad_inputs_publish_nothing": True,
    }


def limits(app: Application, root: Path) -> dict:
    samples = [(-32768 if i % 2 == 0 else 32767) for i in range(262144)]
    work = root / "maximum-samples"
    archive = run(app, work, fixture(work, samples, gain(2), 384000))
    assert archive["results"]["clipped_low"] == archive["results"]["clipped_high"] == 131072
    assert consume(app, work / "output", "replay.json") == archive
    work = root / "over-samples"
    fixture(work, samples + [0])
    reject(app, work, "sample alignment or count limit")
    basic = parts_of(pcm_wave([0]))
    for count in [1024, 1025]:
        work = root / ("chunks-" + str(count))
        config = fixture(work, source=chunks([basic[0], *[(b"JUNK", b"")] * (count - 2), basic[1]]))
        if count == 1024:
            found = run(app, work, config)
            assert len(found["results"]["chunks"]) == count
        else:
            reject(app, work, "chunk count limit")
    work = root / "exact-bytes"
    amount = 2097152 - len(pcm_wave([0])) - 8
    source = chunks([basic[0], (b"JUNK", b"x" * amount), basic[1]])
    assert len(source) == 2097152
    config = fixture(work, source=source)
    path = work / "wav-job.json"
    path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config)
    assert consume(app, work / "output", "replay.json") == archive
    for name, size in [("wav-job.json", 65536), ("source.wav", 2097152)]:
        work = root / ("over-" + name)
        fixture(work)
        path = work / name
        path.write_bytes(path.read_bytes().ljust(size + 1, b" "))
        reject(app, work, "input byte limit")
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        fixture(work)
        config = {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"}
        save(work / "wav-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(16777216 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config)
    work = root / "over-hex"
    fixture(work)
    save(work / "wav-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
    save(work / "archive.json", dict(archive, source_hex="00" * 2097153))
    reject(app, work, "source byte limit")
    return {
        "samples": 262144,
        "waveform_buckets": 256,
        "chunks": 1024,
        "source_bytes": 2097152,
        "request_bytes": 65536,
        "archive_bytes": 16777216,
        "clipped_samples_at_maximum": 262144,
        "each_limit_exceeded_separately": True,
        "maximum_samples_and_source_replayed": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = pcm_wave([-32768, -1, 0, 1, 32767])
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, source=rows)
        result = app.run(work, {"WAV_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".wav-*")) and (work / "output").exists() == (stage == "published")
        if stage == "published":
            inspect(work, config)
    for mutation in ["request", "source", "competitor", "kill-staged", "kill-published"]:
        work = root / mutation
        config = fixture(work, source=rows)
        release = work / "release"
        stage = "published" if mutation == "kill-published" else "staged"
        process = subprocess.Popen(
            app.command,
            cwd=work,
            env=app.environment({"WAV_PAUSE": stage, "WAV_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".wav-*"))) == (1 if stage == "staged" else 0)
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
                    name = "wav-job.json" if mutation == "request" else "source.wav"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".wav-*"))
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
        ["wav-job.json", "source.wav"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "wav-job.json")
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
        print(app.engine + " WAV analyzer " + name + ": passed", flush=True)
    return observations
