"""Complete ZIP project acceptance with independent archive tooling and crafted malformed records."""

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

from .common import Application
from .zip_fixture import (
    canonical,
    check_valid,
    craft,
    digest,
    files_at,
    inspect,
    raw_deflate,
    save,
    standard,
)

DEFAULT = {"entries": 512, "entry_bytes": 8388608, "total_bytes": 33554432}


def fixture(root: Path, source: bytes | None = None, settings: dict | None = None) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {
        "version": 1,
        "mode": "inspect",
        "input": "source.zip",
        "output": "output",
        "limits": settings or dict(DEFAULT),
    }
    save(root / "zip-job.json", config)
    (root / "source.zip").write_bytes(
        standard(
            [
                ("notes/", b"", 0),
                ("notes/message-世界.md", b"**Important** attachment\n", 8),
                ("data.bin", bytes(range(256)), 0),
            ]
        )
        if source is None
        else source
    )
    return config


def run(
    app: Application, root: Path, config: dict, selected: str = "zip-job.json", codes: set[str] | None = None
) -> dict:
    preserved = {root / name: (root / name).read_bytes() for name in [selected, config["input"]]}
    result = app.run(root, {"ZIP_CONFIG": str(root / selected)}, timeout=240)
    assert result.returncode in [0, 1] and not result.stderr, (root, result)
    archive = inspect(root, config)
    results = archive["results"]
    assert result.returncode == int(bool(results["errors"])) and result.stdout == canonical(results["summary"]).decode()
    if codes is not None:
        assert {row["code"] for row in results["errors"]} == codes, (root, results, codes)
    assert all(path.read_bytes() == raw for path, raw in preserved.items())
    return archive


def consume(app: Application, root: Path, name: str) -> dict:
    return run(app, root, json.loads((root / name).read_bytes()), name)


def reject(app: Application, root: Path, needle: str = "") -> None:
    result = app.run(root, {}, timeout=60)
    assert result.returncode == 2 and result.stderr and not result.stdout, (root, result)
    assert needle in result.stderr and not (root / "output").exists() and not list(root.glob(".zip-*"))
    return  # noqa: PLR1711


def edit_export(app: Application, root: Path, source: bytes, settings: dict, stem: str) -> dict:
    before = files_at(root)
    config = json.loads((root / "inspect.json").read_bytes())
    config.update(input=stem + ".zip", output=stem, limits=settings)
    (root / config["input"]).write_bytes(source)
    save(root / (stem + "-job.json"), config)
    result = run(app, root, config, stem + "-job.json")
    assert all((root / name).read_bytes() == raw for name, raw in before.items())
    return result


def semantics(app: Application, root: Path) -> dict:
    config = fixture(root)
    original = run(app, root, config, codes=set())
    check_valid((root / "source.zip").read_bytes(), original["results"])
    assert consume(app, root / "output", "replay.json") == original
    assert consume(app, root / "output", "inspect.json") == original
    valid = [
        standard([]),
        craft([]),
        craft([{"name": b"caf\x82.txt"}]),
        craft([{"flags": 8}]),
        craft([{"flags": 8, "signed": False}]),
    ]
    for streaming in [False, True]:
        for method in [0, 8]:
            valid.append(
                standard(
                    [
                        ("empty", b"", method),
                        ("all-bytes", bytes(range(256)), method),
                        ("Café 東京.txt", b"x" * 65536, method),
                    ],
                    streaming,
                )
            )
    for index, source in enumerate(valid):
        work = root / str(index)
        observed = run(app, work, fixture(work, source), codes=set())
        check_valid(source, observed["results"])
    # Unicode path extra overrides a legacy spelling; CPython zipfile ignores this optional extra.
    import binascii

    legacy, unicode_name = b"legacy.txt", "資料/notes.txt"
    payload = b"\x01" + struct.pack("<I", binascii.crc32(legacy)) + unicode_name.encode()
    extra = struct.pack("<HH", 0x7075, len(payload)) + payload
    work = root / "unicode-extra"
    archive = run(app, work, fixture(work, craft([{"name": legacy, "extra": extra, "local_extra": b""}])), codes=set())
    assert archive["results"]["entries"][0]["name"] == unicode_name
    return {
        "valid_archive_cases": len(valid) + 2,
        "stored_deflated_signed_unsigned_descriptors": True,
        "cp437_utf8_and_unicode_path_extra": True,
        "standard_zipfile_payload_oracle": True,
        "actual_inspect_replay_requests": True,
        "archive_sha256": digest(canonical(original)),
    }


def generated(app: Application, root: Path) -> dict:
    rng = random.Random(118)
    hashes, total = [], 0
    for index in range(16):
        rows = [
            (
                f"notes/{j:03}-" + rng.choice(["東京", "café", "test", "👩🏽‍💻"]) + ".bin",
                rng.randbytes(rng.randrange(2048)),
                rng.choice([0, 8]),
            )
            for j in range(rng.randrange(33))
        ]
        source = standard(rows, streaming=bool(index % 2))
        work = root / str(index)
        original = run(app, work, fixture(work, source), codes=set())
        check_valid(source, original["results"])
        assert consume(app, work / "output", "replay.json") == original
        changed = standard(list(reversed(rows)) + [("edited.txt", b"An edited attachment", 8)])
        edited = edit_export(app, work / "output", changed, DEFAULT, "edited")
        check_valid(changed, edited["results"])
        assert consume(app, work / "output/edited", "replay.json") == edited
        restored = edit_export(app, work / "output/edited", source, DEFAULT, "restored")
        assert restored == original
        total += len(rows)
        hashes.append(digest(canonical(original)))
    return {
        "seed": 118,
        "generated_archives": 16,
        "entries": total,
        "edit_replay_restore": 16,
        "archives_sha256": digest(canonical(hashes)),
    }


def malformed(app: Application, root: Path) -> dict:
    cases = []
    for name in [
        b"../outside",
        b"/absolute",
        b"a/../../outside",
        b"C:/drive",
        b"a\\b",
        b"a//b",
        b"./dot",
        b"a/./b",
        b"trailing.",
        b"space ",
        b"NUL.txt",
        b"COM1",
        b"a\0b",
        b"a\x1bb",
        "a\u202eb".encode(),
    ]:
        cases.append((craft([{"name": name, "flags": 2048}]), {"unsafe_name"}))
    for names in [[b"same", b"same"], [b"Name", b"name"], ["é".encode(), "é".encode()], [b"folder/", b"folder"]]:
        rows = [{"name": name, "flags": 2048, "data": b"" if name.endswith(b"/") else b"x"} for name in names]
        cases.append((craft(rows), {"duplicate_name"}))
    for entry, codes in [
        ({"crc": 0}, {"crc"}),
        ({"expanded": 1}, {"expanded_size"}),
        ({"name": b"bad\xff", "flags": 2048}, {"name_encoding", "unsafe_name"}),
        ({"attributes": 0o120777 << 16}, {"unsafe_type"}),
        ({"attributes": 0o40755 << 16}, {"directory_payload"}),
        ({"name": b"directory/"}, {"directory_payload"}),
        ({"flags": 1}, {"encrypted"}),
        ({"flags": 64}, {"unsupported_entry"}),
        ({"method": 0, "flags": 2}, {"unsupported_entry"}),
        ({"method": 12}, {"unsupported_entry"}),
        ({"disk": 1}, {"unsupported_entry"}),
        ({"version": 63}, {"unsupported_entry"}),
        ({"local_name": b"different"}, {"local_name"}),
        ({"local_values": (1, 2, 3)}, {"local_sizes"}),
        ({"compressed": b"\x07"}, {"decompression"}),
        ({"compressed": raw_deflate(b"Saved network message\n") + b"trailing"}, {"decompression"}),
        ({"compressed": raw_deflate(b"Saved network message\n")[:-1]}, {"decompression"}),
        ({"extra": b"x"}, {"extra_structure"}),
        ({"extra": struct.pack("<HH", 123, 10) + b"x"}, {"extra_structure"}),
        ({"extra": struct.pack("<HHHH", 123, 0, 123, 0)}, {"duplicate_extra"}),
        ({"extra": struct.pack("<HH", 1, 0)}, {"zip64", "zip64_entry"}),
        ({"extra": struct.pack("<HH", 0x7075, 1) + b"\x01"}, {"unicode_path_extra"}),
    ]:
        cases.append((craft([entry]), codes))
    for index, (source, codes) in enumerate(cases):
        work = root / str(index)
        observed = run(app, work, fixture(work, source), codes=codes)
        assert consume(app, work / "output", "replay.json") == observed
        assert not (work / "outside").exists()
    source = craft([{"name": b"test", "data": b"payload"}])
    for length in range(len(source)):
        work = root / ("prefix-" + str(length))
        observed = run(app, work, fixture(work, source[:length]), codes={"archive_structure"})
        assert observed["results"]["summary"]["entries"] == 0
    for index, raw in enumerate(
        [standard([("small", b"x", 8)], zip64=True), standard([("small", b"x", 8)], streaming=True, zip64=True)]
    ):
        work = root / ("zip64-" + str(index))
        archive = run(app, work, fixture(work, raw))
        assert "zip64" in {e["code"] for e in archive["results"]["errors"]}
        assert archive["results"]["summary"]["verified_payloads"] == 0
    return {
        "unsafe_names_and_entry_mutations": len(cases),
        "all_proper_prefixes": len(source),
        "zip64_local_profiles": 2,
        "malformed_reports_replayed": len(cases),
    }


def invalid(app: Application, root: Path) -> dict:
    base = {"version": 1, "mode": "inspect", "input": "source.zip", "output": "output", "limits": DEFAULT}
    configs = []
    for key, values in [
        ("version", [None, True, 1.0, 0, 2, "1"]),
        ("mode", [None, True, 0, "", "extract"]),
        ("input", [None, 1, "", "missing", "bad\0path"]),
        ("output", [None, 1, "", "source.zip", "missing/parent/output", "bad\0path"]),
        ("limits", [None, [], {}, True]),
    ]:
        configs.extend(dict(base, **{key: value}) for value in values)
    for field, maximum in [("entries", 2048), ("entry_bytes", 16777216), ("total_bytes", 67108864)]:
        for value in [None, True, 1.0, "1", -1, maximum + 1]:
            configs.append(dict(base, limits=dict(DEFAULT, **{field: value})))
        configs.append(dict(base, limits={k: v for k, v in DEFAULT.items() if k != field}))
    configs.append(dict(base, limits=dict(DEFAULT, extra=1)))
    configs.extend({key: value for key, value in base.items() if key != omitted} for omitted in base)
    configs.append(dict(base, extra=1))
    for index, config in enumerate(configs):
        work = root / ("request-" + str(index))
        fixture(work)
        save(work / "zip-job.json", config)
        reject(app, work)
    broken = [
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
        for index, raw in enumerate(broken):
            work = root / (slot + "-json-" + str(index))
            config = fixture(work)
            name = "zip-job.json"
            if slot == "archive":
                name = "archive.json"
                config = {k: v for k, v in config.items() if k != "limits"}
                config.update(mode="verify", input=name)
                save(work / "zip-job.json", config)
            (work / name).write_bytes(raw)
            reject(app, work)
    work = root / "baseline"
    archive = run(app, work, fixture(work), codes=set())
    changes = [
        (("version",), 1.0),
        (("version",), True),
        (("source_hex",), None),
        (("source_hex",), archive["source_hex"].upper()),
        (("source_hex",), " " + archive["source_hex"]),
        (("source_hex",), archive["source_hex"][:-1]),
        (("source_hex",), "zz"),
        (("source_hex",), "00" + archive["source_hex"][2:]),
        (("limits", "entries"), True),
        (("limits", "entry_bytes"), 0),
        (("limits", "total_bytes"), -1),
        (("results", "summary", "bytes"), float(archive["results"]["summary"]["bytes"])),
        (("results", "summary", "errors"), False),
        (("results", "summary", "budget_used"), 0),
        (("results", "entries", 0, "crc"), 1),
        (("results", "entries", 0, "local_offset"), 9),
        (("results", "entries", 1, "sha256"), "0" * 64),
        (("results", "entries", 1, "name"), "edited"),
        (("results", "entries", 1, "key"), "edited"),
        (("results", "entries", 1, "checked_bytes"), True),
        (("results", "errors"), [{"entry": 0, "offset": 0, "code": "fake"}]),
        (("results",), None),
    ]
    altered = []
    for path, value in changes:
        changed = copy.deepcopy(archive)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        altered.append(changed)
    altered.extend({key: value for key, value in archive.items() if key != omitted} for omitted in archive)
    altered.append(dict(archive, extra=0))
    for index, changed in enumerate(altered):
        work = root / ("tampered-" + str(index))
        fixture(work)
        save(work / "zip-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
        save(work / "archive.json", changed)
        reject(app, work)
    return {
        "invalid_requests": len(configs),
        "malformed_json_per_input": len(broken),
        "inconsistent_archives": len(altered),
        "strict_cached_types_and_canonical_hex": True,
    }


def limits(app: Application, root: Path) -> dict:
    maximum = 16777216
    overhead = len(craft([{"name": b"payload", "data": b"", "method": 0}]))
    raw = craft([{"name": b"payload", "data": b"x" * (maximum - overhead), "method": 0}])
    assert len(raw) == maximum
    work = root / "maximum-bytes"
    settings = dict(DEFAULT, entry_bytes=maximum)
    archive = run(app, work, fixture(work, raw, settings), codes=set())
    check_valid(raw, archive["results"])
    assert consume(app, work / "output", "replay.json") == archive
    work = root / "over-bytes"
    fixture(work, raw + b"x")
    reject(app, work, "input byte limit")
    del raw, archive
    for count in [2048, 2049]:
        work = root / ("entries-" + str(count))
        raw = standard([(str(i), b"", 0) for i in range(count)])
        config = fixture(work, raw, {"entries": 2048, "entry_bytes": 0, "total_bytes": 0})
        archive = run(app, work, config, codes=set() if count == 2048 else {"entry_limit"})
        assert archive["results"]["summary"]["entries"] == (2048 if count == 2048 else 0)
    for index, (rows, settings, expected, used) in enumerate(
        [
            ([{"data": b"x" * 32}], {"entries": 1, "entry_bytes": 32, "total_bytes": 32}, set(), 32),
            ([{"data": b"x" * 33}], {"entries": 1, "entry_bytes": 32, "total_bytes": 64}, {"expanded_limit"}, 0),
            (
                [{"name": b"a", "data": b"x" * 32}, {"name": b"b", "data": b"y" * 32}],
                {"entries": 2, "entry_bytes": 32, "total_bytes": 63},
                {"expanded_limit"},
                32,
            ),
            (
                [{"data": b"x" * 1048576, "expanded": 0}, {"name": b"next", "data": b"y"}],
                {"entries": 2, "entry_bytes": 128, "total_bytes": 128},
                {"decompression", "expanded_limit"},
                128,
            ),
            (
                [{"data": b"x" * 8, "expanded": 0}],
                {"entries": 1, "entry_bytes": 32, "total_bytes": 64},
                {"expanded_size"},
                8,
            ),
        ]
    ):
        work = root / ("budget-" + str(index))
        archive = run(app, work, fixture(work, craft(rows), settings), codes=expected)
        assert archive["results"]["summary"]["budget_used"] == used
        assert consume(app, work / "output", "replay.json") == archive
    for extra_entry in [False, True]:
        work = root / ("total-over" if extra_entry else "total-exact")
        rows = [{"name": str(i).encode(), "data": b"x" * 16777216} for i in range(4)]
        if extra_entry:
            rows.append({"name": b"over", "data": b"y"})
        config = fixture(work, craft(rows), {"entries": 5, "entry_bytes": 16777216, "total_bytes": 67108864})
        observed = run(app, work, config, codes={"expanded_limit"} if extra_entry else set())
        assert (
            observed["results"]["summary"]["checked_bytes"] == observed["results"]["summary"]["budget_used"] == 67108864
        )
    for kind in ["name", "extra", "comment", "archive-comment"]:
        work = root / ("maximum-" + kind)
        entry = {"data": b""}
        comment = b""
        if kind == "archive-comment":
            comment = b"x" * 65535
        elif kind == "extra":
            entry[kind] = struct.pack("<HH", 123, 65531) + b"x" * 65531
        else:
            entry[kind] = b"x" * 65535
        source = craft([entry], comment)
        observed = run(app, work, fixture(work, source), codes=set())
        check_valid(source, observed["results"])
    work = root / "exact-request"
    config = fixture(work)
    path = work / "zip-job.json"
    path.write_bytes(path.read_bytes().ljust(65536, b" "))
    archive = run(app, work, config, codes=set())
    work = root / "over-request"
    fixture(work)
    path = work / "zip-job.json"
    path.write_bytes(path.read_bytes().ljust(65537, b" "))
    reject(app, work)
    for over in [False, True]:
        work = root / ("archive-over" if over else "archive-limit")
        fixture(work)
        config = {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"}
        save(work / "zip-job.json", config)
        (work / "archive.json").write_bytes(canonical(archive).ljust(67108864 + int(over), b" "))
        if over:
            reject(app, work, "input byte limit")
        else:
            run(app, work, config, codes=set())
    work = root / "over-hex"
    fixture(work)
    save(work / "zip-job.json", {"version": 1, "mode": "verify", "input": "archive.json", "output": "output"})
    save(work / "archive.json", dict(archive, source_hex="00" * (16777216 + 1)))
    reject(app, work, "source byte limit")
    return {
        "source_bytes": maximum,
        "archive_bytes": 67108864,
        "request_bytes": 65536,
        "entry_count": 2048,
        "declared_and_actual_expansion_budgets": 7,
        "maximum_name_extra_entry_comment_archive_comment_bytes": 65535,
        "total_expanded_bytes": 67108864,
        "maximum_source_replayed": True,
        "failed_decompression_reserves_allowance": True,
    }


def publication(app: Application, root: Path) -> dict:
    rows = craft([{}])
    for stage in ["staged", "published"]:
        work = root / ("fault-" + stage)
        config = fixture(work, rows)
        result = app.run(work, {"ZIP_FAULT": stage})
        assert result.returncode == 2 and result.stderr and not result.stdout
        assert not list(work.glob(".zip-*")) and (work / "output").exists() == (stage == "published")
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
            env=app.environment({"ZIP_PAUSE": stage, "ZIP_RELEASE": str(release), "PYTHONUNBUFFERED": "1"}),
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
                assert len(list(work.glob(".zip-*"))) == (1 if stage == "staged" else 0)
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
                    name = "zip-job.json" if mutation == "request" else "source.zip"
                    with (work / name).open("ab") as stream:
                        stream.write(b" ")
                release.touch()
                stdout, stderr = process.communicate(timeout=10)
                assert process.returncode == 2 and stderr and not stdout and not list(work.glob(".zip-*"))
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
        ["zip-job.json", "source.zip"], ["symlink", "hardlink", "fifo", "directory", "unreadable"]
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
            output.symlink_to(work / "zip-job.json")
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


def structure(app: Application, root: Path) -> dict:
    raw = craft([{"flags": 8}])
    central = raw.index(b"PK\x01\x02")
    ending = len(raw) - 22
    descriptor = raw.index(b"PK\x07\x08")
    cases = []
    for offset, fmt, value, codes in [
        (ending + 4, "H", 1, {"multi_disk"}),
        (ending + 8, "H", 0, {"multi_disk"}),
        (ending + 12, "I", 1, {"archive_structure"}),
        (ending + 16, "I", central + 1, {"archive_structure"}),
        (0, "I", 0, {"local_structure", "unclaimed_local_bytes"}),
        (6, "H", 0, {"local_fields"}),
        (8, "H", 0, {"local_fields"}),
        (central, "I", 0, {"archive_structure"}),
        (central + 42, "I", central, {"local_structure", "unclaimed_local_bytes"}),
        (descriptor + 4, "I", 0, {"descriptor"}),
    ]:
        changed = bytearray(raw)
        struct.pack_into("<" + fmt, changed, offset, value)
        cases.append((bytes(changed), codes))
    changed = bytearray(raw)
    struct.pack_into("<HH", changed, ending + 8, 0, 0)
    cases.append((bytes(changed), {"central_trailing", "unclaimed_local_bytes"}))
    changed = bytearray(raw)
    struct.pack_into("<HH", changed, ending + 8, 2, 2)
    cases.append((bytes(changed), {"archive_structure"}))
    cases.append((raw + b"x", {"archive_structure"}))
    # Two central records referencing one physical local span: inspect it only once.
    shared = bytearray(craft([{"name": b"same"}, {"name": b"same"}]))
    first = shared.index(b"PK\x01\x02")
    second = shared.index(b"PK\x01\x02", first + 4)
    struct.pack_into("<I", shared, second + 42, 0)
    cases.append((bytes(shared), {"duplicate_name", "overlap", "unclaimed_local_bytes"}))
    # Local and central names are independently checked, including optional Unicode extras.
    import binascii

    payload = b"\x01" + struct.pack("<I", binascii.crc32(b"notes.txt")) + b"../outside"
    extra = struct.pack("<HH", 0x7075, len(payload)) + payload
    cases.append((craft([{"local_extra": extra}]), {"unsafe_name"}))
    for index, (source, expected) in enumerate(cases):
        work = root / str(index)
        archive = run(app, work, fixture(work, source), codes=expected)
        assert consume(app, work / "output", "replay.json") == archive
    overlapping = json.loads((root / "13/output/archive.json").read_bytes())["results"]
    assert overlapping["summary"]["verified_payloads"] == 1 and overlapping["entries"][1]["checked_bytes"] == -1
    # Solve a small GF(2) system to construct data whose CRC equals the optional descriptor signature.
    zero = binascii.crc32(b"\0" * 4)
    basis = {}
    for bit in range(32):
        value, mask = binascii.crc32((1 << bit).to_bytes(4, "little")) ^ zero, 1 << bit
        while value:
            pivot = value.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = (value, mask)
                break
            value ^= basis[pivot][0]
            mask ^= basis[pivot][1]
    value, mask = 0x08074B50 ^ zero, 0
    while value:
        pivot = value.bit_length() - 1
        value ^= basis[pivot][0]
        mask ^= basis[pivot][1]
    data = mask.to_bytes(4, "little")
    assert binascii.crc32(data) == 0x08074B50
    for signed in [False, True]:
        work = root / ("crc-signature-" + str(signed))
        source = craft([{"data": data, "flags": 8, "signed": signed}])
        archive = run(app, work, fixture(work, source), codes=set())
        check_valid(source, archive["results"])
    return {
        "structural_mutations": len(cases),
        "descriptor_crc_equals_signature": 2,
        "overlapping_payload_never_reinflated": True,
        "local_unicode_path_checked": True,
    }


def check(app: Application, directory: Path) -> dict:
    observations = {}
    for name, test in [
        ("semantics", semantics),
        ("generated", generated),
        ("malformed", malformed),
        ("structure", structure),
        ("invalid", invalid),
        ("limits", limits),
        ("memory", memory),
        ("publication", publication),
        ("filesystem", filesystem),
    ]:
        observations[name] = test(app, directory / name)
        print(app.engine + " ZIP validator " + name + ": passed", flush=True)
    return observations


def memory(app: Application, root: Path) -> dict:
    import zlib

    encoder = zlib.compressobj(6, zlib.DEFLATED, -15)
    fragments = [encoder.compress(b"x" * 1048576) for _ in range(256)]
    compressed = b"".join(fragments) + encoder.flush()
    source = craft([{"data": b"", "compressed": compressed, "expanded": 0, "crc": 0}])
    config = fixture(root, source, {"entries": 1, "entry_bytes": 128, "total_bytes": 128})
    command = ["/usr/bin/prlimit", "--as=134217728", "--", *app.command]
    result = subprocess.run(
        command, cwd=root, env=app.environment({}), capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 1 and not result.stderr, result
    archive = inspect(root, config)
    assert {row["code"] for row in archive["results"]["errors"]} == {"decompression"}
    assert archive["results"]["summary"]["budget_used"] == 128
    assert archive["results"]["summary"]["checked_bytes"] == 0
    return {
        "address_space_bytes": 134217728,
        "bomb_expanded_bytes": 268435456,
        "allowed_expanded_bytes": 128,
        "no_full_bomb_allocation": True,
    }
