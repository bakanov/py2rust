"""Independent Python-AST arithmetic, session recovery and durable publication for 074."""

# ruff: noqa: PLR1711 - explicit repository returns
from __future__ import annotations

import ast
import hashlib
import json
import math
import operator
import random
import selectors
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .common import Application
from .csv_json import canonical


def sample() -> tuple[dict, bytes]:
    return (
        {"price": 12.5, "quantity": 4},
        b"total = price * quantity\nsplit = total / 3\nquantity = 1 / 0\nquantity\n-7 // 3\n-7 % 3\nadjusted = -(total + 2) * 0.5\n",
    )


@dataclass
class Fixture:
    work: Path
    config: dict

    @property
    def path(self) -> Path:
        return self.work / "calculator-job.json"

    @property
    def output(self) -> Path:
        return self.work / self.config["output"]

    def save(self) -> None:
        self.path.write_text(json.dumps(self.config))
        return

    def settings(self, mode: str = "write", **extra: str) -> dict:
        return {
            "CALC_CONFIG": str(self.path),
            "CALC_MODE": mode,
            "CALC_FAIL": "",
            "CALC_PAUSE": "",
            "CALC_CONTINUE": "",
            **extra,
        }


def fixture(directory: Path, name: str, variables: dict, script: bytes, **changes: str) -> Fixture:
    work = directory / name
    work.mkdir(parents=True)
    fix = Fixture(work, {"state": "initial.json", "script": "input.txt", "output": "calculated", **changes})
    (work / "initial.json").write_text(json.dumps({"version": 1, "variables": variables}))
    (work / "input.txt").write_bytes(script)
    fix.save()
    return fix


def checked(value: float) -> int | float:
    if type(value) is int:
        assert -(2**63) <= value < 2**63
    else:
        assert type(value) is float and math.isfinite(value)
    return value


def evaluate(node: ast.AST, variables: dict) -> int | float:
    if isinstance(node, ast.Constant):
        return checked(node.value)
    if isinstance(node, ast.Name):
        return variables[node.id]
    if isinstance(node, ast.UnaryOp):
        # Negative numeric literals include the minimum signed integer.
        if isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
            return checked(-node.operand.value)
        operand = evaluate(node.operand, variables)
        return checked(-operand if isinstance(node.op, ast.USub) else operand)
    assert isinstance(node, ast.BinOp)
    left, right = evaluate(node.left, variables), evaluate(node.right, variables)
    if isinstance(node.op, (ast.FloorDiv, ast.Mod)):
        assert type(left) is int and type(right) is int
    functions = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
    }
    return checked(functions[type(node.op)](left, right))


def reference(variables: dict, source: bytes) -> tuple[list[dict], dict]:
    current = variables.copy()
    records = []
    for index, line in enumerate(source.decode().replace("\r\n", "\n").split("\n")):
        if not line.split("#", 1)[0].strip():
            continue
        record = {"line": index + 1, "source": line}
        try:
            statement = ast.parse(line.strip()).body[0]
            binding = statement.targets[0].id if isinstance(statement, ast.Assign) else ""
            value = evaluate(statement.value, current)
            record.update(status="ok", binding=binding, value=value)
            if binding:
                current[binding] = value
        except (AssertionError, ZeroDivisionError, OverflowError, KeyError, SyntaxError):
            record["status"] = "error"
        records.append(record)
    return records, current


def outputs(fix: Fixture, report: dict) -> dict[str, bytes]:
    files = {path.name: path.read_bytes() for path in fix.output.iterdir()}
    assert set(files) == {"state.json", "initial-state.json", "script.txt", "report.json", "manifest.json"}
    assert files["initial-state.json"] == (fix.work / fix.config["state"]).read_bytes()
    assert files["script.txt"] == (fix.work / fix.config["script"]).read_bytes()
    assert files["state.json"] == (canonical({"version": 1, "variables": report["variables"]}) + "\n").encode()
    assert files["report.json"] == (canonical(report) + "\n").encode()
    assert json.loads(files["manifest.json"]) == {
        "version": 1,
        "files": {
            name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in files.items()
            if name != "manifest.json"
        },
    }
    return files


def success(app: Application, fix: Fixture, mode: str = "write", independent: bool = True) -> dict:
    paths = [fix.path, fix.work / fix.config["state"], fix.work / fix.config["script"]]
    original = {path: path.read_bytes() for path in paths}
    result = app.run(fix.work, fix.settings(mode), timeout=60)
    assert result.returncode == 0 and not result.stderr, (fix.work, result)
    report = json.loads(result.stdout)
    assert result.stdout == canonical(report) + "\n"
    assert report["version"] == 1 and set(report) == {"version", "records", "errors", "variables"}
    assert report["errors"] == sum(row["status"] == "error" for row in report["records"])
    if independent:
        state = json.loads(original[paths[1]])["variables"]
        expected, variables = reference(state, original[paths[2]])
        assert len(report["records"]) == len(expected)
        for row, wanted in zip(report["records"], expected, strict=True):
            if wanted["status"] == "error":
                assert set(row) == {"line", "source", "status", "error"} and row["error"]
                row = {key: value for key, value in row.items() if key != "error"}
            assert canonical(row) == canonical(wanted), (fix.work, row, wanted)
        assert canonical(report["variables"]) == canonical(variables), (fix.work, report, variables)
    assert original == {path: path.read_bytes() for path in paths}
    if mode == "write":
        outputs(fix, report)
    else:
        assert not fix.output.exists()
    assert not list(fix.output.parent.glob(".calc-*"))
    return report


def failure(app: Application, fix: Fixture, message: str = "", **extra: str) -> None:
    existed = fix.output.exists() or fix.output.is_symlink()
    before = fix.output.read_bytes() if fix.output.is_file() else None
    result = app.run(fix.work, fix.settings(**extra))
    assert result.returncode == 2 and result.stderr and message in result.stderr and not result.stdout, (
        fix.work,
        result,
    )
    assert (fix.output.exists() or fix.output.is_symlink()) == existed
    if before is not None:
        assert fix.output.read_bytes() == before
    assert not list(fix.output.parent.glob(".calc-*"))
    return


def generated(rng: random.Random, depth: int) -> str:
    if depth == 0 or rng.randrange(4) == 0:
        return rng.choice(["a", "b", "c", "0", "1", "3", "7", "0.1", "1.5", "-2", "5e-324", "-0.0"])
    if rng.randrange(5) == 0:
        return rng.choice(["+", "-"]) + "(" + generated(rng, depth - 1) + ")"
    body = (
        generated(rng, depth - 1) + rng.choice([" + ", " - ", " * ", " / ", " // ", " % "]) + generated(rng, depth - 1)
    )
    return "(" + body + ")" if rng.randrange(2) else body


def arithmetic_cases(app: Application, directory: Path) -> dict:
    reports = [success(app, fixture(directory, "sample", *sample()))]
    expressions = [
        "1 + 2 * 3",
        "(1 + 2) * 3",
        "20 / 5 / 2",
        "20 - 5 - 2",
        "8 // 3 * 2",
        "8 % 3 + 2",
        "-7 // 3",
        "7 // -3",
        "-7 % 3",
        "7 % -3",
        "---2",
        "1+-2",
        "1--2",
        "-0.0",
        "-(-0.0)",
        "+0.0",
        "1e-300 / 1e100",
        "9007199254740993 / 3",
        "9223372036854775807",
        "-9223372036854775808",
        "-9223372036854775808 / -1",
        "-9223372036854775808 % -1",
        "(-9223372036854775808) // -1",
        "9223372036854775807 + 1",
        "-(-9223372036854775808)",
        "3037000500 * 3037000500",
        "1.7976931348623157e308 * 2",
        "1.7976931348623157e308 / 5e-324",
        "1 / -0.0",
        "1 // 0",
        "1 % 0",
        "1.0 // 2",
        "1 % 2.0",
        "a",
        "missing",
        "a + b * c",
    ]
    fix = fixture(directory, "directed", {"a": 9, "b": 0.5, "c": -3}, "\n".join(expressions).encode())
    reports.append(success(app, fix))
    rng = random.Random(740074)
    for index in range(24):
        lines = []
        for step in range(64):
            text = generated(rng, 5)
            lines.append(rng.choice(["a = ", "b = ", "c = ", ""]) + text)
        fix = fixture(directory, f"generated-{index}", {"a": 7, "b": 1.5, "c": -3}, "\n".join(lines).encode())
        reports.append(success(app, fix))
    return {
        "directed_expressions": len(expressions),
        "generated_sessions": 24,
        "generated_expressions": 1536,
        "independent_reference": "Python ast plus checked operator arithmetic",
        "reports_sha256": hashlib.sha256(canonical(reports).encode()).hexdigest(),
    }


def expression_errors(app: Application, directory: Path) -> int:
    cases = [
        ("x = 1 / 0", "column 7: division by zero"),
        ("x = absent", "column 5: undefined variable: absent"),
        ("x = 1 2", "column 7: unexpected trailing token"),
        ("x = (1 + 2", "column 11: expected closing parenthesis"),
        ("x = 1 +", "column 8: expected number, variable or parenthesis"),
        ("x = ()", "column 6: expected number, variable or parenthesis"),
        ("x = 1 ** 2", "column 8: expected number, variable or parenthesis"),
        ("x = 1 ^ 2", "column 7: unexpected character"),
        ("x = é", "column 5: unexpected character"),
        ("x = 01", "column 5: invalid or out-of-range number"),
        ("x = .5", "column 5: invalid or out-of-range number"),
        ("x = 1.", "column 5: invalid or out-of-range number"),
        ("x = 1e+", "column 5: invalid or out-of-range number"),
        ("x = 9223372036854775808", "column 5: invalid or out-of-range number"),
        ("x = -9223372036854775809", "column 5: invalid or out-of-range number"),
        ("x = 1e999", "column 5: invalid or out-of-range number"),
        ("x = 1.0 % 2", "column 9: floor division and remainder require integers"),
        ("x = 9223372036854775807 + 1", "column 25: arithmetic result outside numeric range"),
        ("x = y = 2", "column 5: undefined variable: y"),
        ("x = 1,2", "column 6: unexpected character"),
        ("x = 0x10", "column 6: unexpected trailing token"),
        ("x = 1_000", "column 6: unexpected trailing token"),
        ("x = 2;3", "column 6: unexpected character"),
        ("x = 's'", "column 5: unexpected character"),
        ("x = True", "column 5: undefined variable: True"),
        ("x = 1 == 1", "column 7: unexpected trailing token"),
    ]
    for index, (source, error) in enumerate(cases):
        fix = fixture(directory, f"error-{index}", {"x": 42}, (source + "\nx\nx = x + 1\nx").encode())
        report = success(app, fix, independent=False)
        assert report["errors"] == 1 and report["records"][0]["error"] == error, (source, report, error)
        assert [row["value"] for row in report["records"][1:]] == [42, 43, 43]
        assert report["variables"] == {"x": 43}
    return len(cases)


def invalid_inputs(app: Application, directory: Path) -> int:
    count = 0
    base = {"state": "initial.json", "script": "input.txt", "output": "calculated"}
    configs = [None, [], {}, {**base, "extra": 1}]
    for field in base:
        configs.append({key: value for key, value in base.items() if key != field})
        configs += [{**base, field: value} for value in [None, True, 1, [], {}, "", "absent/item", "a\0b"]]
    for index, value in enumerate(configs):
        fix = fixture(directory, f"config-{index}", *sample())
        fix.path.write_text(json.dumps(value))
        result = app.run(fix.work, fix.settings())
        assert result.returncode == 2 and result.stderr and not result.stdout and not fix.output.exists()
        count += 1
    base = {"version": 1, "variables": {}}
    states = [None, [], {}, {"version": 1}, {"variables": {}}, {**base, "extra": 1}]
    states += [{**base, "version": value} for value in [None, True, 0, 2, "1", 1.5]]
    states += [{**base, "variables": value} for value in [None, True, 1, [], "x"]]
    states += [{**base, "variables": {name: 1}} for name in ["", "1x", "a-b", "é", "a\0", "x" * 65]]
    states += [{**base, "variables": {"x": value}} for value in [None, False, True, [], {}, "1"]]
    for index, value in enumerate(states):
        fix = fixture(directory, f"state-{index}", *sample())
        (fix.work / "initial.json").write_text(json.dumps(value))
        failure(app, fix)
        count += 1
    for filename in ["initial.json", "calculator-job.json"]:
        for index, raw in enumerate(
            [
                b"\xff",
                b"{",
                b'{"version":1,"variables":{"x":NaN}}',
                b'{"version":1,"variables":{"x":9223372036854775808}}',
                b'{"version":1,"variables":{"x":"\\ud800"}}',
            ]
        ):
            fix = fixture(directory, f"json-{filename}-{index}", *sample())
            (fix.work / filename).write_bytes(raw)
            failure(app, fix)
            count += 1
    fix = fixture(directory, "invalid-utf8-script", {}, b"\xff")
    failure(app, fix)
    count += 1
    fix = fixture(directory, "invalid-mode", *sample())
    failure(app, fix, "invalid calculator mode", CALC_MODE="other")
    return count + 1


def limits(app: Application, directory: Path) -> dict:
    for filename in ["calculator-job.json", "initial.json"]:
        for size in [65536, 65537]:
            fix = fixture(directory, f"bytes-{filename}-{size}", *sample())
            path = fix.work / filename
            path.write_bytes(path.read_bytes().ljust(size, b" "))
            if size == 65536:
                success(app, fix)
            else:
                failure(app, fix, "input byte limit")
    for count in [256, 257]:
        fix = fixture(directory, f"initial-variables-{count}", {f"v{n}": n for n in range(count)}, b"v0")
        if count == 256:
            success(app, fix)
        else:
            failure(app, fix, "session exceeds 256 variables")
    fix = fixture(directory, "full-session-recovery", {f"v{n}": n for n in range(256)}, b"new = 4\nv0 = v0 + 1\nv0")
    report = success(app, fix, independent=False)
    assert report["errors"] == 1 and report["records"][0]["error"] == "session exceeds 256 variables"
    assert report["variables"]["v0"] == 1 and "new" not in report["variables"] and len(report["variables"]) == 256
    for size in [64, 65]:
        name = "x" * size
        fix = fixture(directory, f"name-{size}", {}, (name + " = 2").encode())
        report = success(app, fix, independent=False)
        assert report["errors"] == (size == 65)
        assert report["variables"] == ({name: 2} if size == 64 else {})
    for depth in [32, 33]:
        for kind, text in [("parentheses", "(" * depth + "x" + ")" * depth), ("unary", "-" * depth + "x")]:
            fix = fixture(directory, f"{kind}-{depth}", {"x": 1}, text.encode())
            report = success(app, fix, independent=False)
            assert report["errors"] == (depth == 33)
            if depth == 33:
                assert "nesting exceeds 32" in report["records"][0]["error"]
            else:
                assert report["records"][0]["value"] == 1
    for count in [512, 513]:
        text = "+" * (count - 511) + "+".join(["1"] * 256)
        fix = fixture(directory, f"tokens-{count}", {}, text.encode())
        report = success(app, fix, independent=False)
        assert report["errors"] == (count == 513)
        if count == 512:
            assert report["records"][0]["value"] == 256
        else:
            assert report["records"][0]["error"] == "expression exceeds 512 tokens"
    for size in [4096, 4097]:
        fix = fixture(directory, f"line-bytes-{size}", {}, b"1".ljust(size, b" "))
        report = success(app, fix, independent=False)
        assert report["errors"] == (size == 4097)
        if size == 4096:
            assert report["records"][0]["value"] == 1
        else:
            assert report["records"][0]["error"] == "expression exceeds 4096 bytes"
    for count in [256, 257]:
        fix = fixture(directory, f"lines-{count}", {}, b"\n" * (count - 1))
        if count == 256:
            assert success(app, fix)["records"] == []
        else:
            failure(app, fix, "script exceeds 256 lines")
    source = b"\n".join([b"#".ljust(4095, b" ")] * 255 + [b"#".ljust(4096, b" ")])
    assert len(source) == 1048576
    for extra in [0, 1]:
        fix = fixture(directory, f"script-bytes-{extra}", {}, source + b" " * extra)
        if not extra:
            assert success(app, fix)["records"] == []
        else:
            failure(app, fix, "input byte limit")
    # JSON escaping can expand source bytes retained in error reports beyond the export budget.
    fix = fixture(directory, "export-budget", {}, b"\n".join([b"\0" * 4096] * 180))
    failure(app, fix, "exports exceed 4 MiB")
    fix = fixture(
        directory,
        "comments-and-crlf",
        {},
        b"\t # a comment \xe4\xb8\x96\xe7\x95\x8c\r\nx = 2 # comment\r\n\r\nx + 1\r\n",
    )
    assert [row["value"] for row in success(app, fix)["records"]] == [2, 3]
    fix = fixture(directory, "duplicate-json-keys", {}, b"x")
    (fix.work / "initial.json").write_bytes(b'{"version":1,"variables":{"x":1,"x":2}}')
    assert success(app, fix)["variables"] == {"x": 2}
    return {
        "config_and_state_bytes": 65536,
        "script_bytes": 1048576,
        "script_lines": 256,
        "line_bytes": 4096,
        "tokens_per_expression": 512,
        "recursive_parse_depth": 32,
        "variables": 256,
        "identifier_characters": 64,
        "export_bytes": 4194304,
    }


def paused(app: Application, fix: Fixture) -> subprocess.Popen:
    process = subprocess.Popen(
        app.command,
        cwd=fix.work,
        env=app.environment(fix.settings(CALC_PAUSE="ready", CALC_CONTINUE=str(fix.work / "continue"))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = bool(selector.select(20))
    if not ready or process.stdout.readline() != "PAUSED ready\n":
        process.kill()
        raise AssertionError(process.communicate(timeout=5))
    return process


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=5)
    return


def publication(app: Application, directory: Path) -> int:
    points = [
        "validated",
        "stage",
        "state.json",
        "initial-state.json",
        "script.txt",
        "report.json",
        "manifest.json",
        "ready",
        "published",
    ]
    for point in points:
        fix = fixture(directory, "fault-" + point, *sample())
        reference = success(app, fix, mode="preview")
        result = app.run(fix.work, fix.settings(CALC_FAIL=point))
        assert result.returncode == 2 and "injected failure: " + point in result.stderr and not result.stdout
        assert not list(fix.work.glob(".calc-*"))
        if point == "published":
            outputs(fix, reference)
        else:
            assert not fix.output.exists()
            success(app, fix)
    for name in ["initial.json", "input.txt", "config", "destination"]:
        fix = fixture(directory, "changed-" + name, *sample())
        process = paused(app, fix)
        try:
            if name == "destination":
                fix.output.mkdir()
                (fix.output / "keep").write_bytes(b"another writer")
            else:
                path = fix.path if name == "config" else fix.work / name
                with path.open("ab") as stream:
                    stream.write(b" ")
            (fix.work / "continue").touch()
            output, error = process.communicate(timeout=20)
            assert process.returncode == 2 and error and not output
            assert not list(fix.work.glob(".calc-*"))
            if name == "destination":
                assert list(fix.output.iterdir()) == [fix.output / "keep"]
                assert (fix.output / "keep").read_bytes() == b"another writer"
            else:
                assert "input changed before publication" in error and not fix.output.exists()
        finally:
            stop(process)
    fix = fixture(directory, "killed", *sample())
    reference = success(app, fix, mode="preview")
    process = paused(app, fix)
    stop(process)
    assert not fix.output.exists()
    abandoned = list(fix.work.glob(".calc-*"))
    assert len(abandoned) == 1
    old = {path.name: path.read_bytes() for path in abandoned[0].iterdir()}
    result = app.run(fix.work, fix.settings())
    assert result.returncode == 0 and not result.stderr
    outputs(fix, reference)
    assert {path.name: path.read_bytes() for path in abandoned[0].iterdir()} == old
    return len(points) + 5


def paths(app: Application, directory: Path) -> int:
    names = ["initial.json", "input.txt", "calculator-job.json"]
    for name in ["file", "directory", "symlink", "dangling", *names]:
        fix = fixture(directory, "destination-" + name, *sample())
        if name == "file":
            fix.output.write_bytes(b"preserve")
        elif name == "directory":
            fix.output.mkdir()
            (fix.output / "keep").write_bytes(b"preserve")
        elif name in ["symlink", "dangling"]:
            fix.output.symlink_to(fix.work / ("input.txt" if name == "symlink" else "missing"))
        else:
            fix.config["output"] = name
            fix.save()
        failure(app, fix, "output directory already exists")
    for name in names:
        fix = fixture(directory, "symlink-" + name, *sample())
        path = fix.work / name
        path.rename(fix.work / "original")
        path.symlink_to(fix.work / "original")
        original = (fix.work / "original").read_bytes()
        failure(app, fix, "regular file")
        assert path.is_symlink() and (fix.work / "original").read_bytes() == original
    fix = fixture(directory, "readonly", *sample())
    parent = fix.work / "readonly"
    parent.mkdir()
    fix.config["output"] = "readonly/result"
    fix.save()
    parent.chmod(0o500)
    try:
        failure(app, fix)
        assert not list(parent.iterdir())
    finally:
        parent.chmod(0o700)
    fix = fixture(directory, "nested-inputs", *sample())
    nested = fix.work / "nested"
    nested.mkdir()
    (fix.work / "initial.json").rename(nested / "initial.json")
    (fix.work / "input.txt").rename(nested / "input.txt")
    fix.config.update(state="nested/initial.json", script="nested/../nested/input.txt")
    fix.save()
    success(app, fix)
    return 12


def check(app: Application, directory: Path) -> dict:
    result = arithmetic_cases(app, directory / "arithmetic")
    result["located_recovery_errors"] = expression_errors(app, directory / "errors")
    print(
        app.engine + " calculator: independent precedence, numeric boundaries and session recovery passed", flush=True
    )
    result["invalid_inputs"] = invalid_inputs(app, directory / "invalid")
    result["limits"] = limits(app, directory / "limits")
    result["publication_cases"] = publication(app, directory / "publication")
    result["path_cases"] = paths(app, directory / "paths")
    print(app.engine + " calculator: bounds, validation, publication and paths passed", flush=True)
    return result
