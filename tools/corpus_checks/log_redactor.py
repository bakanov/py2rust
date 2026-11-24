"""Independent redaction/count oracle, sensitive-diagnostic checks and real atomic publication tests."""

# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
from __future__ import annotations

import copy
import decimal
import hashlib
import json
import math
import os
import queue
import random
import re
import resource
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from .common import Application

SECRET = "SENSITIVE-089-TOKEN-491"
EMAIL = "private.person@example.invalid"


def canonical(value: object) -> str:
    if type(value) is float:
        if value == 0.0:
            return "-0e0" if math.copysign(1.0, value) < 0 else "0e0"
        with decimal.localcontext() as context:
            context.prec = 1100
            context.rounding = decimal.ROUND_HALF_EVEN
            mantissa, exponent = format(decimal.Decimal.from_float(value), ".16e").split("e")
        return mantissa.rstrip("0").rstrip(".") + "e" + str(int(exponent))
    if isinstance(value, list):
        return "[" + ",".join(canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(canonical(key) + ":" + canonical(value[key]) for key in sorted(value)) + "}"
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def literal(pattern: str, replacement: str = "[MASKED]") -> dict:
    return {"kind": "literal", "pattern": pattern, "replacement": replacement}


def regex(pattern: str, replacement: str = "[MASKED]") -> dict:
    return dict(literal(pattern, replacement), kind="regex")


def examples() -> list[dict]:
    return [
        {
            "message": f"Hello {SECRET}; email {EMAIL}",
            "context": {"token": SECRET, "tries": 2},
            "recipients": [{"email": EMAIL, "active": True}],
            "unrelated": [None, False, 1.25, "世界"],
        },
        {"message": "No credentials", "context": {}, "recipients": []},
        {"message": f"{SECRET} {SECRET}", "context": {"token": ""}, "recipients": [{"email": "public"}]},
    ]


@dataclass
class Fixture:
    root: Path
    config: dict
    data: bytes

    @property
    def source(self) -> Path:
        return self.root / "input.jsonl"

    @property
    def output(self) -> Path:
        return self.root / self.config["output"]

    @property
    def settings(self) -> dict:
        return {"REDACTOR_CONFIG": str(self.root / "job.json")}

    def write(self) -> None:
        (self.root / "job.json").write_text(canonical(self.config))
        self.source.write_bytes(self.data)
        return


def fixture(
    root: Path,
    rows: list[dict] | None = None,
    *,
    raw: bytes | None = None,
    targets: list[list] | None = None,
    rules: list[dict] | None = None,
    missing: str = "skip",
) -> Fixture:
    root.mkdir(parents=True)
    config = {
        "version": 1,
        "input": "input.jsonl",
        "output": "output",
        "missing": missing,
        "targets": targets if targets is not None else [["message"], ["context", "token"], ["recipients", 0, "email"]],
        "rules": (
            rules
            if rules is not None
            else [literal(SECRET, "[TOKEN]"), regex(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]")]
        ),
    }
    if raw is None:
        raw = "".join(canonical(row) + "\n" for row in (examples() if rows is None else rows)).encode()
    fix = Fixture(root, copy.deepcopy(config), raw)
    fix.write()
    return fix


def reference(fix: Fixture) -> tuple[bytes, dict]:
    config = fix.config
    rule_counts = [
        {"index": i, "matches": 0, "matched_fields": 0, "changed_fields": 0} for i in range(len(config["rules"]))
    ]
    target_counts = [{"index": i, "present": 0, "missing": 0, "changed": 0} for i in range(len(config["targets"]))]
    audit = {
        "version": 1,
        "records": 0,
        "changed_records": 0,
        "selected_fields": 0,
        "missing_fields": 0,
        "changed_fields": 0,
        "matches": 0,
        "input_bytes": len(fix.data),
        "output_bytes": 0,
    }
    output = []
    for raw in fix.data.splitlines():
        row = json.loads(raw)
        changed = False
        for index, path in enumerate(config["targets"]):
            parent, found = row, True
            try:
                for key in path[:-1]:
                    parent = parent[key]
                original = parent[path[-1]]
            except (KeyError, IndexError):
                found = False
            target = target_counts[index]
            if not found:
                assert config["missing"] == "skip"
                target["missing"] += 1
                audit["missing_fields"] += 1
                continue
            assert type(original) is str
            value = original
            for rule_index, rule in enumerate(config["rules"]):
                pattern = re.escape(rule["pattern"]) if rule["kind"] == "literal" else rule["pattern"]
                compiled = re.compile(pattern, re.ASCII)
                occurrences = list(compiled.finditer(value))
                assert all(item.end() > item.start() for item in occurrences)
                transformed, count = compiled.subn(lambda _, replacement=rule["replacement"]: replacement, value)
                assert count == len(occurrences)
                counter = rule_counts[rule_index]
                counter["matches"] += count
                counter["matched_fields"] += count > 0
                counter["changed_fields"] += transformed != value
                audit["matches"] += count
                value = transformed
            target["present"] += 1
            target["changed"] += value != original
            audit["selected_fields"] += 1
            audit["changed_fields"] += value != original
            changed = changed or value != original
            parent[path[-1]] = value
        audit["records"] += 1
        audit["changed_records"] += changed
        output.append(canonical(row) + "\n")
    data = "".join(output).encode()
    audit.update(output_bytes=len(data), rules=rule_counts, targets=target_counts)
    return data, audit


def assert_clean(data: bytes) -> None:
    for secret in [SECRET, EMAIL]:
        assert secret.encode() not in data
    return


def verify(fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {"redacted.jsonl", "audit.json", "report.txt", "manifest.json"}
    expected, audit = reference(fix)
    assert files["redacted.jsonl"] == expected
    assert files["audit.json"] == (canonical(audit) + "\n").encode()
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(data), "sha256": digest(data)}
            for name, data in files.items()
            if name != "manifest.json"
        },
    }
    assert f"Records: {audit['records']}\n" in files["report.txt"].decode()
    for kind in ["rules", "targets"]:
        for counter in audit[kind]:
            assert canonical(counter) in files["report.txt"].decode()
    for data in files.values():
        assert_clean(data)
    assert audit["selected_fields"] + audit["missing_fields"] == audit["records"] * len(fix.config["targets"])
    assert audit["changed_fields"] == sum(counter["changed"] for counter in audit["targets"])
    assert audit["matches"] == sum(counter["matches"] for counter in audit["rules"])
    return audit, files


def run(app: Application, fix: Fixture) -> tuple[dict, dict[str, bytes]]:
    inputs = {name: (fix.root / name).read_bytes() for name in ["job.json", "input.jsonl"]}
    result = app.run(fix.root, fix.settings, timeout=60)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert_clean((result.stdout + result.stderr).encode())
    audit, files = verify(fix)
    assert json.loads(result.stdout) == audit
    assert inputs == {name: (fix.root / name).read_bytes() for name in inputs}
    assert not list(fix.root.glob(".redactor-*"))
    return audit, files


def rejected(app: Application, fix: Fixture, phase: str) -> None:
    result = app.run(fix.root, fix.settings, timeout=30)
    assert result.returncode == 2 and result.stdout == "", (result.stdout, result.stderr)
    assert result.stderr.strip().endswith("Redactor " + phase + " failed"), result.stderr
    assert_clean(result.stderr.encode())
    assert not (fix.root / "output").exists() and not list(fix.root.glob(".redactor-*"))
    return


def semantics(app: Application, root: Path) -> dict:
    proofs = []
    base = fixture(root / "default")
    audit, files = run(app, base)
    assert audit["records"] == 3 and audit["matches"] == 6 and audit["missing_fields"] == 2
    assert audit["changed_fields"] == 4
    proofs.append(digest(files["redacted.jsonl"]))
    cases = [
        ([{"message": "aaaaa"}], [["message"]], [literal("aa", "X")]),
        ([{"message": "ababa", "other": "ababa"}], [["message"]], [literal("aba", "Q")]),
        ([{"message": "a"}], [["message"]], [literal("a", "b"), literal("b", "a")]),
        ([{"message": "same same"}], [["message"]], [literal("same", "same")]),
        ([{"message": "TOKEN-123 TOKEN-456"}], [["message"]], [regex(r"(TOKEN)-[0-9]+", r"$1\1")]),
        ([{"message": "abc_123 λé１２３"}], [["message"]], [regex(r"\w+", "_"), regex(r"\d+", "!")]),
        ([{"message": "λ世界 λ🌍"}], [["message"]], [literal("λ", "é"), regex("世界|🌍", "<>")]),
        ([{"message": "line one\nline two\tend\r"}], [["message"]], [regex(r"\s+", " ")]),
        ([{"message": "start/end"}], [["message"]], [regex("^start|end$", "x")]),
        ([{"message": 'a\x00b " slash\\'}], [["message"]], [literal("\x00", "[NUL]"), literal('"', "'")]),
        ([{"": [{"a.b": "aaa", "other": 4}], "a.b": "aaa"}], [["", 0, "a.b"]], [literal("a", "z")]),
        ([{"message": ""}, {"different": True}], [["message"]], [regex("x", "y")]),
        ([], [["message"]], [literal("x", "y")]),
    ]
    for index, (rows, targets, rules) in enumerate(cases):
        fix = fixture(root / f"explicit-{index}", rows, targets=targets, rules=rules)
        audit, files = run(app, fix)
        if index == 2:
            assert audit["matches"] == 2 and audit["changed_fields"] == 0
            assert sum(row["changed_fields"] for row in audit["rules"]) == 2
        if index == 3:
            assert audit["matches"] == 2 and audit["changed_records"] == 0
        proofs.append(digest(files["redacted.jsonl"] + files["audit.json"]))
    mixed = fixture(
        root / "physical-lines",
        raw=b'{"message":"x"}\r\n{"message":"xx"}',
        targets=[["message"]],
        rules=[literal("x", "X")],
    )
    _, files = run(app, mixed)
    proofs.append(digest(files["redacted.jsonl"]))
    rng = random.Random(89037)
    generated_rows = []
    for index in range(300):
        values = [rng.choice(["safe", SECRET, EMAIL, "世界", "0123", "$1", "\\"]) for _ in range(12)]
        generated_rows.append(
            {
                "id": index,
                "message": " ".join(values),
                "context": {"token": rng.choice([SECRET, ""])},
                "recipients": [{"email": rng.choice([EMAIL, "public"])}],
                "unchanged": {"flag": bool(index % 2), "number": index * 17, "array": [None, "λ"]},
            }
        )
    fix = fixture(root / "generated", generated_rows)
    audit, files = run(app, fix)
    proofs.append(digest(files["redacted.jsonl"] + files["audit.json"]))
    repeat = fixture(root / "repeat", generated_rows)
    assert run(app, repeat)[1] == files
    return {
        "explicit_workloads": len(cases) + 2,
        "generated_records": 300,
        "identical_repeat": True,
        "ordered_reversal_and_noop_counts": True,
        "literal_replacement_metacharacters": True,
        "nested_fields_and_ascii_classes": True,
        "outputs_and_diagnostics_secret_free": True,
        "proof_sha256": digest("".join(proofs).encode()),
    }


def invalid(app: Application, root: Path) -> dict:
    base = fixture(root / "template").config
    configurations = []
    for field, values in [
        ("version", [0, 2, True, 1.0, None]),
        ("missing", ["", "ignore", None]),
        ("input", ["", "\x00", None, "job.json", SECRET + "/missing"]),
        ("output", ["", "\x00", None, "job.json", SECRET + "/missing"]),
    ]:
        for value in values:
            configurations.append(dict(copy.deepcopy(base), **{field: value}))
    for field in base:
        config = copy.deepcopy(base)
        del config[field]
        configurations.append(config)
    configurations.append(dict(copy.deepcopy(base), extra=SECRET))
    for targets in [
        [],
        None,
        {},
        [None],
        [[]],
        [[-1]],
        [[4096]],
        [[True]],
        [[1.0]],
        [["a" * 129]],
        [["a"] * 17],
        [["a"]] * 2,
        [["a"], ["a", "b"]],
        [["a", "b"], ["a"]],
        [["a" + str(i)] for i in range(33)],
    ]:
        configurations.append(dict(copy.deepcopy(base), targets=targets))
    for rules in [
        [],
        None,
        {},
        [None],
        [literal("x")] * 33,
        [dict(literal("x"), extra=SECRET)],
        [{"kind": "literal", "pattern": "x"}],
    ]:
        configurations.append(dict(copy.deepcopy(base), rules=rules))
    for field, values in [
        ("kind", ["", "unknown", None]),
        ("pattern", ["", None, "x" * 513]),
        ("replacement", [None, 1, "x" * 257]),
    ]:
        for value in values:
            rule = dict(literal("x"), **{field: value})
            configurations.append(dict(copy.deepcopy(base), rules=[rule]))
    for pattern in ["[", SECRET + "[", "(?=" + SECRET + ")", r"(a)\1", "", "a*", "^", "$", "x|"]:
        configurations.append(dict(copy.deepcopy(base), rules=[regex(pattern)]))
    for index, config in enumerate(configurations):
        fix = fixture(root / f"configuration-{index}")
        fix.config = config
        fix.write()
        rejected(app, fix, "configuration")
    malformed_config = [
        b"{",
        b"null",
        b"[]",
        b"\xff",
        b'{"version":1,"version":1}',
        ('{"value":"' + SECRET + '","version":NaN}').encode(),
    ]
    for index, raw in enumerate(malformed_config):
        fix = fixture(root / f"config-raw-{index}")
        (fix.root / "job.json").write_bytes(raw)
        rejected(app, fix, "configuration")
    malformed_data = [
        b"\n",
        b" \t\r\n",
        b"null\n",
        b"[]\n",
        b"1\n",
        b'"text"\n',
        b"{",
        b"\xff\n",
        b'{"message":"\\ud800"}\n',
        b'{"message":"x","message":"y"}\n',
        b'{"message":"x","n":9223372036854775808}\n',
        b'{"message":"x","n":1e999}\n',
        b'{"message":"x","n":NaN}\n',
        ('{"message":"' + SECRET + '"}\n{broken:' + SECRET).encode(),
    ]
    for index, raw in enumerate(malformed_data):
        fix = fixture(root / f"data-raw-{index}", raw=raw)
        rejected(app, fix, "input processing")
    invalid_targets = [
        ({"message": None}, [["message"]], "skip"),
        ({"message": 3}, [["message"]], "skip"),
        ({"message": []}, [["message"]], "skip"),
        ({"message": {}}, [["message"]], "skip"),
        ({"nested": None}, [["nested", "x"]], "skip"),
        ({"array": {}}, [["array", 0]], "skip"),
        ({"array": []}, [["array", "0"]], "skip"),
        ({}, [["missing"]], "error"),
        ({"array": []}, [["array", 0]], "error"),
    ]
    for index, (row, targets, policy) in enumerate(invalid_targets):
        fix = fixture(root / f"target-{index}", [row], targets=targets, missing=policy)
        rejected(app, fix, "input processing")
    for index, pattern in enumerate([r"\b", r"x+|\b", r"\B"]):
        fix = fixture(
            root / f"zero-width-{index}", [{"message": SECRET}], targets=[["message"]], rules=[regex(pattern)]
        )
        rejected(app, fix, "input processing")
    return {
        "configurations": len(configurations) + len(malformed_config),
        "records": len(malformed_data) + len(invalid_targets) + 3,
        "sensitive_errors_suppressed": True,
    }


def capacity(app: Application, root: Path) -> dict:
    line_size = len((canonical({"message": ""}) + "\n").encode())
    raw = (canonical({"message": "b" * (65536 - line_size)}) + "\n").encode()
    assert len(raw) == 65536
    fix = fixture(root / "full-input-output", raw=raw * 64, targets=[["message"]], rules=[literal("x")])
    config = fix.root / "job.json"
    data = config.read_bytes()
    config.write_bytes(data + b" " * (65536 - len(data)))

    def limited() -> None:
        resource.setrlimit(resource.RLIMIT_AS, (268435456, 268435456))
        return

    result = subprocess.run(
        app.command,
        cwd=fix.root,
        env=app.environment(fix.settings),
        capture_output=True,
        text=True,
        timeout=60,
        preexec_fn=limited,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    audit, files = verify(fix)
    assert json.loads(result.stdout) == audit
    assert audit["input_bytes"] == audit["output_bytes"] == 4194304
    proofs = [digest(files["redacted.jsonl"])]
    for filename, size, phase in [("job.json", 65536, "configuration"), ("input.jsonl", 4194304, "input processing")]:
        over = fixture(root / ("oversized-" + filename))
        path = over.root / filename
        data = path.read_bytes()
        path.write_bytes(data + b" " * (size + 1 - len(data)))
        rejected(app, over, phase)
    for name, rows in [
        ("max-records", [{"message": "safe"}] * 1024),
        ("max-rules-targets", [{"k" + str(i): "safe" for i in range(32)}]),
    ]:
        targets = [["message"]] if name == "max-records" else [["k" + str(i)] for i in range(32)]
        rules = [literal("x")] if name == "max-records" else [literal("z" * 512, "m" * 256)] * 32
        full = fixture(root / name, rows, targets=targets, rules=rules)
        report, bundle = run(app, full)
        assert report["records"] == len(rows)
        proofs.append(digest(bundle["audit.json"]))
    depth = ["k" * 128] * 16
    nested: object = "x"
    for key in reversed(depth):
        nested = {key: nested}
    nested["array"] = [0] * 4095 + ["x"]
    deep = fixture(root / "deep", [nested], targets=[depth, ["array", 4095]], rules=[literal("x", "y")])
    assert run(app, deep)[0]["changed_fields"] == 2
    over = fixture(root / "too-many-records", [{"message": "safe"}] * 1025, targets=[["message"]])
    rejected(app, over, "input processing")
    over = fixture(root / "long-line", raw=raw[:-1] + b" \n", targets=[["message"]])
    rejected(app, over, "input processing")
    full = fixture(
        root / "field-limit", [{"message": "x" * 256}], targets=[["message"]], rules=[literal("x", "a" * 256)]
    )
    _, bundle = run(app, full)
    assert len(json.loads(bundle["redacted.jsonl"])["message"]) == 65536
    over = fixture(
        root / "field-over", [{"message": "x" * 256 + "y"}], targets=[["message"]], rules=[literal("x", "a" * 256)]
    )
    rejected(app, over, "input processing")
    record = {"k" + str(i): "x" * 255 for i in range(4)}
    record["padding"] = ""
    expanded = dict(record, **{"k" + str(i): "a" * (255 * 256) for i in range(4)})
    padding = 262144 - len((canonical(expanded) + "\n").encode())
    record["padding"] = "b" * padding
    full = fixture(
        root / "output-record-limit",
        [record],
        targets=[["k" + str(i)] for i in range(4)],
        rules=[literal("x", "a" * 256)],
    )
    _, bundle = run(app, full)
    assert len(bundle["redacted.jsonl"]) == 262144
    record["padding"] += "b"
    over = fixture(root / "output-record-over", [record], targets=full.config["targets"], rules=full.config["rules"])
    rejected(app, over, "input processing")
    record["padding"] = record["padding"][:-1]
    full = fixture(
        root / "expanded-total-limit", [record] * 16, targets=full.config["targets"], rules=full.config["rules"]
    )
    assert run(app, full)[0]["output_bytes"] == 4194304
    over = fixture(
        root / "expanded-total-over",
        [record] * 16 + [{"k0": "b"}],
        targets=full.config["targets"],
        rules=full.config["rules"],
    )
    rejected(app, over, "input processing")
    rows = [{"message": "x" * 62500}] * 16
    full = fixture(root / "match-limit", rows, targets=[["message"]], rules=[literal("x", "x")])
    assert run(app, full)[0]["matches"] == 1000000
    over = fixture(root / "match-over", rows + [{"message": "x"}], targets=[["message"]], rules=[literal("x", "x")])
    rejected(app, over, "input processing")
    return {
        "records": 1024,
        "rules": 32,
        "targets": 32,
        "path_depth": 16,
        "array_index": 4095,
        "key_bytes": 128,
        "pattern_bytes": 512,
        "replacement_bytes": 256,
        "matches": 1000000,
        "input_line_bytes": 65536,
        "field_bytes": 65536,
        "output_record_bytes": 262144,
        "config_bytes": 65536,
        "input_bytes": 4194304,
        "output_bytes": 4194304,
        "memory_limit": 268435456,
        "proof_sha256": digest("".join(proofs).encode()),
    }


def paused(app: Application, fix: Fixture, label: str) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.root,
        env=app.environment(dict(fix.settings, REDACTOR_PAUSE=label, REDACTOR_RELEASE=str(fix.root / "release"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: queue.Queue = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)
        return

    threading.Thread(target=reader, daemon=True).start()
    try:
        while True:
            line = lines.get(timeout=15)
            assert line is not None, "exited before checkpoint"
            if line.strip() == "PAUSED " + label:
                return process
    except BaseException:
        process.kill()
        process.wait(timeout=5)
        raise


def publication(app: Application, root: Path) -> dict:
    count = 0
    for label in ["staged", "published"]:
        for killed in [False, True]:
            fix = fixture(root / f"{label}-{killed}")
            if killed:
                process = paused(app, fix, label)
                process.kill()
                stdout, _ = process.communicate(timeout=5)
                assert_clean(stdout.encode())
            else:
                result = app.run(fix.root, dict(fix.settings, REDACTOR_FAULT=label))
                assert result.returncode == 2 and result.stderr.strip().endswith("Redactor publication failed")
                assert_clean((result.stdout + result.stderr).encode())
                assert not list(fix.root.glob(".redactor-*"))
            if label == "staged":
                assert not fix.output.exists()
                orphan = next(fix.root.glob(".redactor-*")) if killed else None
                original = {p.name: p.read_bytes() for p in orphan.iterdir()} if orphan else {}
                for data in original.values():
                    assert_clean(data)
                assert app.run(fix.root, fix.settings).returncode == 0
                verify(fix)
                if orphan:
                    assert original == {p.name: p.read_bytes() for p in orphan.iterdir()}
            else:
                _, files = verify(fix)
                result = app.run(fix.root, fix.settings)
                assert result.returncode == 2
                assert_clean((result.stdout + result.stderr).encode())
                assert files == {p.name: p.read_bytes() for p in fix.output.iterdir()}
            count += 1
    for name in ["job.json", "input.jsonl"]:
        fix = fixture(root / ("live-change-" + name))
        process = paused(app, fix, "staged")
        path = fix.root / name
        path.write_bytes(path.read_bytes() + b" ")
        (fix.root / "release").write_text("resume")
        stdout, _ = process.communicate(timeout=10)
        assert process.returncode == 2 and not fix.output.exists() and not list(fix.root.glob(".redactor-*"))
        assert_clean(stdout.encode())
        count += 1
    for name in ["job.json", "input.jsonl"]:
        phase = "configuration" if name == "job.json" else "input processing"
        for kind in ["symlink", "hardlink", "directory", "fifo"]:
            fix = fixture(root / f"{name}-{kind}")
            path, target = fix.root / name, fix.root / "original"
            original = path.read_bytes()
            path.rename(target)
            if kind == "symlink":
                path.symlink_to(target)
            elif kind == "hardlink":
                os.link(target, path)
            elif kind == "directory":
                path.mkdir()
            else:
                os.mkfifo(path)
            rejected(app, fix, phase)
            assert target.read_bytes() == original
            count += 1
    for kind in ["directory", "file", "symlink", "input", "parent"]:
        fix = fixture(root / ("existing-" + kind))
        if kind == "directory":
            fix.output.mkdir()
            (fix.output / "preserved").write_text("keep")
        elif kind == "file":
            fix.output.write_text("keep")
        elif kind == "symlink":
            fix.output.symlink_to(fix.root / "missing")
        else:
            fix.config["output"] = "input.jsonl" if kind == "input" else "."
            fix.write()
        result = app.run(fix.root, fix.settings)
        assert result.returncode == 2 and result.stderr.strip().endswith("Redactor configuration failed")
        assert_clean(result.stderr.encode())
        if kind == "directory":
            assert (fix.output / "preserved").read_text() == "keep"
        elif kind == "file":
            assert fix.output.read_text() == "keep"
        elif kind == "symlink":
            assert fix.output.is_symlink() and not fix.output.exists()
        assert fix.source.read_bytes() == fix.data
        count += 1
    if os.getuid() != 0:
        fix = fixture(root / "permissions")
        fix.root.chmod(0o500)
        try:
            rejected(app, fix, "publication")
        finally:
            fix.root.chmod(0o700)
        count += 1
    fix = fixture(root / "concurrent")
    processes = [
        subprocess.Popen(
            app.command,
            cwd=fix.root,
            env=app.environment(fix.settings),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(8)
    ]
    results = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            results.append(process.returncode)
            assert process.returncode in [0, 2]
            assert_clean((stdout + stderr).encode())
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    assert results.count(0) == 1
    verify(fix)
    assert not list(fix.root.glob(".redactor-*"))
    return {
        "failure_and_alias_checks": count,
        "concurrent_writers": 8,
        "successful_publications": 1,
        "staged_outputs_and_errors_secret_free": True,
    }


def check(app: Application, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "semantics": semantics(app, directory / "semantics"),
        "invalid": invalid(app, directory / "invalid"),
        "capacity": capacity(app, directory / "capacity"),
        "publication": publication(app, directory / "publication"),
        "independent_regex_and_literal_oracle": True,
    }
