"""Independent program semantics, bounded execution and portable result-bundle checks."""

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from corpus_checks.common import Application

from .automation_oracle import generated


@dataclass
class Fixture:
    directory: Path
    source: bytes
    budget: int

    @property
    def config(self) -> Path:
        return self.directory / "job.json"

    @property
    def program(self) -> Path:
        return self.directory / json.loads(self.config.read_text())["program"]

    @property
    def output(self) -> Path:
        return self.directory / "output"


def fixture(directory: Path, source: str | bytes, budget: int = 100) -> Fixture:
    directory.mkdir(parents=True)
    data = source.encode() if isinstance(source, str) else source
    (directory / "program.auto").write_bytes(data)
    (directory / "job.json").write_text(
        json.dumps({"version": 1, "program": "program.auto", "steps": budget, "output": "output"})
    )
    return Fixture(directory, data, budget)


def run(app: Application, case: Fixture, code: int) -> tuple[dict, dict[str, bytes]]:
    before = case.config.read_bytes()
    result = app.run(case.directory, {"AUTOMATION_CONFIG": str(case.config)}, timeout=45)
    assert result.returncode == code, result
    assert case.config.read_bytes() == before and case.program.read_bytes() == case.source
    assert not list(case.directory.glob(".automation-*"))
    if code == 2:
        assert not result.stdout and result.stderr and not case.output.exists(), result
        return {"error": result.stderr.removeprefix("ERROR:root:").removeprefix("ERROR:").strip()}, {}
    assert not result.stderr, result
    files = {path.name: path.read_bytes() for path in case.output.iterdir()}
    assert set(files) == {"program.auto", "ast.json", "report.json", "job.json"}
    assert files["program.auto"] == case.source
    report = json.loads(result.stdout)
    assert report == json.loads(files["report.json"])
    assert report["version"] == 1 and 0 <= report["steps"] <= case.budget
    assert report["status"] == ("ok" if code == 0 else "error")
    assert bool(report["error"]) == bool(code)
    assert json.loads(files["job.json"]) == {
        "version": 1,
        "program": "program.auto",
        "steps": case.budget,
        "output": "replayed",
    }
    tree = json.loads(files["ast.json"])
    assert tree["version"] == 1 and tree["nodes"][0]["kind"] == "block"
    assert tree["nodes"][0]["parent"] == -1 and tree["nodes"][0]["child_index"] == 0
    children = {}
    for index, node in enumerate(tree["nodes"][1:], 1):
        assert 0 <= node["parent"] < index
        expected = children.get(node["parent"], 0)
        assert node["child_index"] == expected
        children[node["parent"]] = expected + 1
    return report, files


def snapshot(directory: Path) -> dict:
    result = {}
    for path in directory.rglob("*"):
        info = path.lstat()
        data = os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None
        result[str(path.relative_to(directory))] = (info.st_mode, info.st_mtime_ns, data)
    return result


def invalid_configurations(app: Application, directory: Path) -> int:
    case = fixture(directory, "emit 1\n")
    base = json.loads(case.config.read_text())
    cases = [
        dict(base, **change)
        for change in [
            {"version": True},
            {"version": 2},
            {"version": None},
            {"extra": 1},
            {"program": ""},
            {"program": "missing"},
            {"program": 4},
            {"program": "folder"},
            {"program": "link"},
            {"steps": True},
            {"steps": 1.5},
            {"steps": "1"},
            {"output": ""},
            {"output": 1},
            {"output": "absent/output"},
            {"output": "program.auto"},
            {"output": "job.json"},
            {"output": "folder"},
            {"output": "dangling"},
            {"output": "link"},
        ]
    ]
    for key in base:
        value = copy.deepcopy(base)
        del value[key]
        cases.append(value)
    (directory / "folder").mkdir()
    (directory / "folder/keep").write_text("keep")
    (directory / "link").symlink_to(directory / "program.auto")
    (directory / "dangling").symlink_to(directory / "absent")
    for value in cases:
        case.config.write_text(json.dumps(value))
        before = snapshot(directory)
        result = app.run(directory, {"AUTOMATION_CONFIG": str(case.config)})
        assert result.returncode == 2 and not result.stdout and result.stderr, result
        assert snapshot(directory) == before
    return len(cases)


def check(app: Application, directory: Path) -> dict:
    hashes = []
    programs = generated()
    for index, (source, budget, expected) in enumerate(programs):
        case = fixture(directory / ("generated-" + str(index)), source, budget)
        report, files = run(app, case, 1 if expected["error"] else 0)
        assert {key: report[key] for key in expected} == expected
        hashes.append(hashlib.sha256(files["report.json"] + files["ast.json"]).hexdigest())
    limited = Application(["/usr/bin/prlimit", "--as=268435456", "--", *app.command], app.engine)
    for name, (source, budget, code) in BOUNDARY_CASES.items():
        report, files = run(limited, fixture(directory / name, source, budget), code)
        if code != 2:
            hashes.append(hashlib.sha256(files["report.json"] + files["ast.json"]).hexdigest())
        if name == "budget-max":
            assert report["steps"] == 10000 and report["error"] == "1:1: step budget exhausted"
        if name == "partial-unwind":
            assert report["variables"] == {"x": 1}
        if name == "min-mod":
            assert report["emitted"] == [0]
    case = fixture(directory / "flat-ast", "let x = 2\nemit x\n")
    report, files = run(app, case, 0)
    assert report["emitted"] == [2] and report["variables"] == {"x": 2}
    assert json.loads(files["ast.json"])["nodes"] == [
        {"kind": "block", "value": "", "location": "1:1: ", "parent": -1, "child_index": 0},
        {"kind": "let", "value": "x", "location": "1:1: ", "parent": 0, "child_index": 0},
        {"kind": "number", "value": "2", "location": "1:9: ", "parent": 1, "child_index": 0},
        {"kind": "emit", "value": "", "location": "2:1: ", "parent": 0, "child_index": 1},
        {"kind": "name", "value": "x", "location": "2:6: ", "parent": 3, "child_index": 0},
    ]
    errors = [
        ("emit absent", 1, "1:6: undefined variable: absent"),
        ("emit 1 // 0", 1, "1:8: division by zero"),
        ("let x = 1; let x = 2", 1, "1:12: variable already declared: x"),
        ("# 世界\n  emit @", 2, "2:8: unexpected character"),
        ("if 0 { emit ( }", 2, "1:15: expected expression"),
    ]
    for index, (source, code, message) in enumerate(errors):
        report, _files = run(app, fixture(directory / ("diagnostic-" + str(index)), source), code)
        assert report["error"] == message, report
    invalid = invalid_configurations(app, directory / "invalid")
    return {
        "independent_oracle_programs": len(programs),
        "boundary_cases": len(BOUNDARY_CASES),
        "no_write_validation_cases": invalid,
        "maximum_steps": 10000,
        "memory_limit": 268435456,
        "flat_ast_and_source_coordinates": True,
        "nested_scopes_and_error_unwinding": True,
        "exact_source_diagnostics": len(errors),
        "checked_i64_arithmetic": True,
        "source_bytes_unchanged": True,
        "reports_and_asts_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
    }


BOUNDARY_CASES = {
    "budget-max": ("repeat 9223372036854775807 {}", 10000, 1),
    "tokens-4096": (";" * 4096, 10000, 0),
    "tokens-4097": (";" * 4097, 10000, 2),
    "ast-height-64": ("emit " + "+".join(["1"] * 62), 10000, 0),
    "ast-height-65": ("emit " + "+".join(["1"] * 63), 10000, 2),
    "budget-empty": ("", 10000, 0),
    "block-16": ("if 1 {" * 16 + "emit 1" + "}" * 16, 10000, 0),
    "block-17": ("if 1 {" * 17 + "emit 1" + "}" * 17, 10000, 2),
    "groups-32": ("emit " + "(" * 32 + "1" + ")" * 32, 10000, 0),
    "groups-33": ("emit " + "(" * 33 + "1" + ")" * 33, 10000, 2),
    "vars-128": ("\n".join(f"let x{i}= {i}" for i in range(128)), 10000, 0),
    "vars-129": ("\n".join(f"let x{i}= {i}" for i in range(129)), 10000, 1),
    "name-64": ("let " + "x" * 64 + "=1", 10000, 0),
    "name-65": ("let " + "x" * 65 + "=1", 10000, 2),
    "bytes-32768": ("#" + "x" * 32767, 10000, 0),
    "bytes-32769": ("#" + "x" * 32768, 10000, 2),
    "crlf": ("let x = 2\r\nif x {\r\n emit x\r\n}\r\n", 10000, 0),
    "cr": ("let x = 2\rif x {\r emit x\r}\r", 10000, 0),
    "undefined": ("emit absent", 10000, 1),
    "redeclare": ("let x = 1; let x = 2", 10000, 1),
    "negative": ("repeat -1 {}", 10000, 1),
    "division": ("emit 1//0", 10000, 1),
    "overflow": ("emit 9223372036854775807+1", 10000, 1),
    "min-negate": ("emit -(-9223372036854775808)", 10000, 1),
    "min-divide": ("emit -9223372036854775808 // -1", 10000, 1),
    "min-mod": ("emit -9223372036854775808 % -1", 10000, 0),
    "partial-unwind": ("let x=0; if 1 { set x=1; if 1 {let z=2; emit bad}}", 10000, 1),
    "zero-repeat": ("repeat 0 { emit 1//0 }", 10000, 0),
    "dead-runtime": ("if 0 {emit missing} else {emit 4}", 10000, 0),
    "dead-syntax": ("if 0 { emit ( } else {emit 4}", 10000, 2),
    "unknown-statement": ("exec 1", 10000, 2),
    "keyword-name": ("let repeat=1", 10000, 2),
    "open-block": ("if 1 {", 10000, 2),
    "close-block": ("}", 10000, 2),
    "parenthesized-compare": ("emit (1<2)<3", 10000, 0),
    "chained-compare": ("emit 1<2<3", 10000, 2),
    "single-slash": ("emit 4/2", 10000, 2),
    "float": ("emit 1.5", 10000, 2),
    "nul": ("emit 1\0", 10000, 2),
    "utf8": (b"\xff", 10000, 2),
    "negative-budget": ("", -1, 2),
    "oversize-budget": ("", 10001, 2),
}
