"""Independent exact-value oracle for complete projects importing three actual Rust files."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import select
import subprocess
import time
from collections import Counter
from pathlib import Path

from .common import Application
from .native_reference import (
    runner,  # noqa: F401 - fingerprint the explicit CPython reference dependency closure
)

MINIMUM = -(2**63)
MAXIMUM = 2**63 - 1
MESSAGES = {
    "integer_range": "out of range integral type conversion attempted",
    "overflow": "native integer overflow",
    "nonfinite": "non-finite floating point result",
    "json_range": "JSON integers must fit signed 64 bits",
    "rejected": "native rejected text",
}


def case(operation: str, arguments: dict, expect: dict | None = None, name: str = "case") -> dict:
    return {"id": name, "operation": operation, "arguments": arguments, "expect": expect}


def oracle(row: dict) -> dict:
    op, args = row["operation"], row["arguments"]
    code = None
    result = None
    if op in {"narrow", "unsigned", "double"}:
        number = args["value"]
        result = number * 2 if op == "double" else number
        if (
            (op == "narrow" and not 0 <= number <= 255)
            or (op == "unsigned" and number < 0)
            or not MINIMUM <= result <= MAXIMUM
        ):
            code = "integer_range"
    elif op == "add":
        result = args["left"] + args["right"]
        if not MINIMUM <= result <= MAXIMUM:
            code = "overflow"
    elif op == "invert":
        result = not args["value"]
    elif op == "unicode":
        text = args["text"]
        result = [len(text), len(text.encode()), text[::-1]]
    elif op == "bytes":
        data = base64.b64decode(args["data"], validate=True)
        result = [base64.b64encode(bytes(byte ^ 165 for byte in reversed(data))).decode(), len(data)]
    elif op == "accept":
        if args["text"] == "deny":
            code = "rejected"
        else:
            result = "accepted:" + args["text"]
    elif op == "unit":
        result = None
    elif op in {"float", "nested"}:
        if args["mode"] != "finite":
            code = "nonfinite"
        else:
            result = 1.25 if op == "float" else [[1.25, -0.0], [2.5, "ok"]]
    elif op == "json":
        if args["mode"] == "wide":
            code = "json_range"
        else:
            result = {"items": [1, True, None, {"text": "世界"}]}
    else:
        assert op == "roundtrip"
        result = args["value"]
    return {"kind": "error", "code": code} if code else {"kind": "value", "value": result}


def equal(left: object, right: object) -> bool:
    # Keep booleans distinct from integers and compare every nested shape.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(root: Path, cases: list[dict], output: str = "inspection") -> dict:
    root.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "output": output, "cases": cases}
    save(root, config)
    return config


def save(root: Path, config: dict) -> None:
    (root / "imports-job.json").write_text(json.dumps(config, ensure_ascii=False, separators=(",", ":")) + "\n")
    return  # noqa: PLR1711 - explicit repository convention


def inspect_bundle(output: Path, source: bytes, cases: list[dict]) -> dict:
    assert {p.name for p in output.iterdir()} == {"report.json", "report.txt", "replay.json", "manifest.json"}
    manifest = json.loads((output / "manifest.json").read_bytes())
    assert set(manifest) == {"report.json", "report.txt", "replay.json"}
    for name, info in manifest.items():
        data = (output / name).read_bytes()
        assert info == {"bytes": len(data), "sha256": digest(data)}
    report = json.loads((output / "report.json").read_bytes())
    assert set(report) == {"version", "source_sha256", "summary", "operations", "error_codes", "cases"}
    assert report["version"] == 1 and report["source_sha256"] == digest(source)
    expected_rows, replay_rows = [], []
    operations, codes = Counter(), Counter()
    lines = ["Native Rust import inspection"]
    for row in cases:
        expected = oracle(row)
        observed = dict(expected)
        operations[row["operation"]] += 1
        if expected["kind"] == "error":
            codes[expected["code"]] += 1
            observed["message"] = MESSAGES[expected["code"]]
        asserted = row["expect"] is None or equal(row["expect"], expected)
        expected_rows.append(
            dict(
                row,
                reference=expected,
                observed=observed,
                matches_reference=True,
                matches_expectation=asserted,
                passed=asserted,
            )
        )
        replay_rows.append(dict(row, expect=expected))
        status = "passed" if asserted else "FAILED"
        rendered = json.dumps(observed, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        lines.append(f'{row["id"]} {row["operation"]}: {status} {rendered}')
    assert equal(report["cases"], expected_rows), (report["cases"], expected_rows)
    passed = sum(row["passed"] for row in expected_rows)
    assert report["summary"] == {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "native_errors": sum(codes.values()),
    }
    assert report["operations"] == dict(operations) and report["error_codes"] == dict(codes)
    replay = json.loads((output / "replay.json").read_bytes())
    assert equal(replay, {"version": 1, "output": "replayed", "cases": replay_rows})
    # JSON canonical rendering is already independently tested; parse each textual outcome too.
    actual_lines = (output / "report.txt").read_text().splitlines()
    assert actual_lines[0] == lines[0] and len(actual_lines) == len(lines)
    for actual, wanted, row in zip(actual_lines[1:], lines[1:], expected_rows, strict=True):
        prefix = f'{row["id"]} {row["operation"]}: {"passed" if row["passed"] else "FAILED"} '
        assert actual.startswith(prefix) and equal(json.loads(actual[len(prefix) :]), row["observed"])
    return report


def run(app: Application, root: Path, config: dict, code: int = 0, settings: dict | None = None) -> dict:
    source = (root / "imports-job.json").read_bytes()
    result = app.run(root, settings or {})
    assert result.returncode == code, (result.returncode, result.stdout, result.stderr)
    assert not result.stdout and not result.stderr, (result.stdout, result.stderr)
    assert (root / "imports-job.json").read_bytes() == source
    return inspect_bundle(root / config["output"], source, config["cases"])


def suite() -> list[dict]:
    rows = []
    boundaries = [
        MINIMUM,
        MINIMUM // 2 - 1,
        MINIMUM // 2,
        -257,
        -1,
        0,
        1,
        254,
        255,
        256,
        MAXIMUM // 2,
        MAXIMUM // 2 + 1,
        MAXIMUM,
    ]
    for op in ["narrow", "unsigned", "double"]:
        rows += [case(op, {"value": n}) for n in boundaries]
    for left in [MINIMUM, -1, 0, 1, MAXIMUM]:
        rows += [case("add", {"left": left, "right": right}) for right in [MINIMUM, -1, 0, 1, MAXIMUM]]
    rows += [case("invert", {"value": value}) for value in [False, True]]
    for text in ["", "a\x00b", "世界🙂e\u0301", '\r\n\t\\"', "deny", "x" * 1024, "🙂" * 256]:
        rows += [case(op, {"text": text}) for op in ["unicode", "accept", "unit"]]
    rows += [
        case("bytes", {"data": base64.b64encode(data).decode()})
        for data in [b"", b"\x00\xff", bytes(range(256)), bytes(range(256)) * 4]
    ]
    for mode in ["finite", "nan", "inf", "negative_inf"]:
        rows += [case(op, {"mode": mode}) for op in ["float", "nested"]]
    rows += [case("json", {"mode": mode}) for mode in ["finite", "wide"]]
    rows += [
        case("roundtrip", {"value": value})
        for value in [
            None,
            False,
            True,
            MINIMUM,
            MAXIMUM,
            -0.0,
            [],
            {},
            {"a": [1, True, None, {"text": "世界"}], "b": "\x00\n"},
        ]
    ]
    # Always follow recoverable errors with successful real adapter calls.
    expanded = []
    for row in rows:
        expanded.append(row)
        expanded.append(case("narrow", {"value": 7}))
    for index, row in enumerate(expanded):
        row["id"] = f"case_{index}"
        if index % 3 == 0:
            row["expect"] = oracle(row)
    return expanded


def semantics(app: Application, root: Path) -> dict:
    rows = suite()
    for start in range(0, len(rows), 64):
        work = root / str(start)
        config = fixture(work, rows[start : start + 64])
        run(app, work, config)
    work = root / "empty"
    run(app, work, fixture(work, []))
    mismatches = [
        case("narrow", {"value": 1}, {"kind": "value", "value": True}, "bool_is_not_int"),
        case("accept", {"text": "deny"}, {"kind": "error", "code": "overflow"}, "wrong_error"),
        case("float", {"mode": "nan"}, {"kind": "value", "value": 0}, "wrong_kind"),
        case("bytes", {"data": "AA=="}, {"kind": "value", "value": ["AA==", 1]}, "wrong_bytes"),
        case("add", {"left": 2, "right": 3}, {"kind": "value", "value": 5}, "continues"),
    ]
    work = root / "mismatches"
    report = run(app, work, fixture(work, mismatches), 1)
    assert report["summary"]["failed"] == 4
    return {
        "independent_cases": len(rows),
        "operations": 13,
        "intentional_mismatches": 4,
        "local_recovery_and_continued_native_calls": True,
        "empty_suite": True,
    }


def invalid(app: Application, root: Path) -> dict:
    base = {"version": 1, "output": "inspection", "cases": [case("narrow", {"value": 7})]}
    variants = []
    for key, value in [
        ("version", True),
        ("version", 2),
        ("output", ""),
        ("output", "\x00"),
        ("cases", {}),
        ("cases", [case("narrow", {"value": 1}, name=f"c{i}") for i in range(65)]),
    ]:
        variants.append(dict(copy.deepcopy(base), **{key: value}))
    variants += [dict(base, extra=1), {k: v for k, v in base.items() if k != "cases"}]
    bad_rows = [
        dict(case("narrow", {"value": 7}), **{key: value})
        for key, value in [
            ("id", ""),
            ("id", "x" * 33),
            ("id", "世界"),
            ("operation", "missing"),
            ("arguments", {"value": True}),
            ("arguments", {"value": 1.5}),
            ("arguments", {"value": "1"}),
            ("arguments", {}),
            ("arguments", {"value": 1, "extra": 0}),
            ("expect", {}),
            ("expect", {"kind": "error", "code": "unexpected"}),
            ("expect", {"kind": "value", "value": 1, "extra": 0}),
            ("expect", {"kind": "unknown", "code": "overflow"}),
        ]
    ]
    bad_rows += [case("bytes", {"data": data}) for data in ["!", "AA", "AB==", "AA==\n", "A" * 1368]]
    bad_rows += [
        case(op, args)
        for op, args in [
            ("unicode", {"text": "🙂" * 257}),
            ("accept", {"text": False}),
            ("unit", {"text": "a" * 1025}),
            ("invert", {"value": 1}),
            ("add", {"left": 1, "right": True}),
            ("float", {"mode": "wide"}),
            ("nested", {"mode": "other"}),
            ("json", {"mode": "nan"}),
            ("roundtrip", {"value": [0] * 256}),
            ("roundtrip", {"value": "a" * 4095}),
        ]
    ]
    nested = 0
    for _ in range(9):
        nested = [nested]
    bad_rows.append(case("roundtrip", {"value": nested}))
    variants.append(dict(base, cases=[case("roundtrip", {"value": "x" * 4084}, name=f"c{i}") for i in range(25)]))
    variants += [dict(base, cases=[row]) for row in bad_rows]
    variants.append(dict(base, cases=[case("narrow", {"value": 1}), case("narrow", {"value": 2})]))
    for index, config in enumerate(variants):
        work = root / str(index)
        work.mkdir(parents=True)
        save(work, config)
        result = app.run(work, {})
        assert result.returncode == 2 and result.stderr and not result.stdout, (config, result)
        assert {p.name for p in work.iterdir()} == {"imports-job.json"}
    malformed = [
        b"{",
        b"\xff",
        b'{"version":1,"version":1}',
        json.dumps(base).replace('"value": 7', '"value": 9223372036854775808').encode(),
        json.dumps(base).replace('"value": 7', '"value": NaN').encode(),
        json.dumps(base).replace('"value": 7', '"value": "\\ud800"').encode(),
        b" " * 262145,
    ]
    for index, data in enumerate(malformed):
        work = root / f"malformed_{index}"
        work.mkdir()
        (work / "imports-job.json").write_bytes(data)
        result = app.run(work, {})
        assert result.returncode == 2 and result.stderr and not (work / "inspection").exists()
    return {"invalid_configurations": len(variants), "malformed_documents": len(malformed)}


def paused(app: Application, root: Path, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=root,
        env=app.environment({"IMPORTS_PAUSE": label, "IMPORTS_RELEASE": str(root.parent / (root.name + "-release"))}),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        ready, _, _ = select.select([process.stdout], [], [], 0.05)
        if ready:
            line = process.stdout.readline()
            if line.strip() == "PAUSED " + label:
                return process
            if not line:
                break
    process.kill()
    stdout, stderr = process.communicate()
    raise AssertionError(("pause failed", stdout, stderr))


def publication(app: Application, root: Path) -> dict:
    rows = [case("bytes", {"data": "AP8="})]
    for label in ["staged", "published"]:
        for mode in ["fault", "kill"]:
            work = root / (label + "_" + mode)
            config = fixture(work, rows)
            source = (work / "imports-job.json").read_bytes()
            if mode == "fault":
                result = app.run(work, {"IMPORTS_FAULT": label})
                assert result.returncode == 2 and "injected failure" in result.stderr
                assert not list(work.glob(".imports-*"))
            else:
                process = paused(app, work, label)
                process.kill()
                process.communicate(timeout=5)
                assert process.returncode == -9
            if label == "published":
                inspect_bundle(work / config["output"], source, rows)
            else:
                assert not (work / config["output"]).exists()
            if mode == "fault" and label == "staged":
                run(app, work, config)
    for change in ["input", "competitor", "permission"]:
        work = root / change
        config = fixture(work, rows)
        process = paused(app, work, "staged")
        try:
            if change == "input":
                (work / "imports-job.json").write_text("{}")
            elif change == "competitor":
                (work / "inspection").mkdir()
                (work / "inspection/sentinel").write_text("preserved")
            else:
                assert os.getuid() != 0
                work.chmod(0o500)
            (work.parent / (work.name + "-release")).touch()
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 2 and stderr and not stdout
            if change == "competitor":
                assert (work / "inspection/sentinel").read_text() == "preserved"
            else:
                assert not (work / "inspection").exists()
        finally:
            work.chmod(0o700)
            if process.poll() is None:
                process.kill()
                process.communicate()
    return {
        "atomic_fault_or_kill_boundaries": 4,
        "changed_input_or_existing_output_rejected": 2,
        "publication_permission_failure": True,
    }


def filesystem(app: Application, root: Path) -> dict:
    names = [
        "input-symlink",
        "input-hardlink",
        "input-fifo",
        "input-unreadable",
        "output-symlink",
        "output-hardlink",
        "output-fifo",
        "output-directory",
    ]
    for name in names:
        work = root / name
        fixture(work, [])
        source, output, sentinel = work / "imports-job.json", work / "inspection", work / "sentinel"
        sentinel.write_bytes(b"preserve")
        guarded = source if name.startswith("input") else output
        if name == "input-unreadable":
            source.chmod(0)
        else:
            if name.startswith("input"):
                source.unlink()
            if name.endswith("symlink"):
                guarded.symlink_to(sentinel)
            elif name.endswith("hardlink"):
                os.link(sentinel, guarded)
            elif name.endswith("fifo"):
                os.mkfifo(guarded)
            else:
                guarded.mkdir()
        before = guarded.lstat()
        try:
            result = app.run(work, {}, timeout=5)
            assert result.returncode == 2 and result.stderr
            assert sentinel.read_bytes() == b"preserve" and guarded.lstat().st_ino == before.st_ino
        finally:
            if name == "input-unreadable":
                source.chmod(0o600)
    return {"guarded_paths": len(names)}


def limits(app: Application, root: Path) -> dict:
    value = 0
    for _ in range(8):
        value = [value]
    rows = [
        case("roundtrip", {"value": value}, name="depth"),
        case("roundtrip", {"value": [0] * 255}, name="nodes"),
        case("roundtrip", {"value": "x" * 4094}, name="bytes"),
    ]
    rows += [case("bytes", {"data": base64.b64encode(bytes(range(256)) * 4).decode()}, name=f"c{i}") for i in range(61)]
    config = fixture(root, rows)
    source = root / "imports-job.json"
    source.write_bytes(source.read_bytes().ljust(262144, b" "))
    run(app, root, config)
    replay_work = root / "aggregate"
    replay_config = fixture(replay_work, [case("roundtrip", {"value": "x" * 4084}, name=f"c{i}") for i in range(24)])
    run(app, replay_work, replay_config)
    exported = (replay_work / "inspection/replay.json").read_bytes()
    assert len(exported) <= 262144
    (replay_work / "imports-job.json").write_bytes(exported)
    run(app, replay_work, json.loads(exported))
    return {
        "cases": 64,
        "aggregate_argument_bytes": 98304,
        "maximum_budget_replay_verified": True,
        "config_bytes": 262144,
        "text_and_binary_bytes": 1024,
        "json_bytes": 4096,
        "json_depth": 8,
        "json_nodes": 256,
    }


def check(app: Application, directory: Path) -> dict:
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid": invalid(app, directory / "invalid"),
        "publication": publication(app, directory / "publication"),
        "filesystem": filesystem(app, directory / "filesystem"),
        "limits": limits(app, directory / "limits"),
        "independent_boundary_oracle": True,
    }
