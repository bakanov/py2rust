"""Reports expose bounded coverage and strict selectors cannot silently pass."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import ast

import pytest

from py2rust.compiler.diagnostics import (
    LoweringDecision,
    build_report,
    select_and_check,
)


def test_strict_scope_and_snapshot_reason() -> None:
    functions = ast.parse("""
def stable(value):
    return value
def uncertain(value):
    return external(value)
""").body
    decision = LoweringDecision("stable", 3, 4, "iteration", "snapshot", "iteration_source_may_change")
    report = build_report(functions, {}, [decision, decision])
    symbols = {"stable": {"file": "app.py", "name": "stable"}, "uncertain": {"file": "app.py", "name": "uncertain"}}
    result = select_and_check(report, symbols, ["app.py:stable"], ["unknown-effects"])
    assert not result["violations"]
    assert len(result["functions"][0]["decisions"]) == 1
    result = select_and_check(report, symbols, ["app.py:*"], ["unknown-effects", "snapshot-iteration"])
    assert {item["check"] for item in result["violations"]} == {"unknown-effects", "snapshot-iteration"}
    assert result["violations"][0]["reason"] == "iteration_source_may_change"
    assert "main-guard" in result["coverage"]["scope"]
    return


def test_bad_scope_and_checks_fail_closed() -> None:
    functions = ast.parse("def known():\n    return 1").body
    report = build_report(functions, {}, [])
    with pytest.raises(ValueError, match="no functions matched"):
        select_and_check(report, {}, ["typo"], [])
    with pytest.raises(ValueError, match="unknown cost check"):
        select_and_check(report, {}, ["*"], ["everything-fast"])
    return


def test_snapshot_gate_checks_reachable_functions() -> None:
    functions = ast.parse("def entry(value):\n    return helper(value)\ndef helper(value):\n    return value").body
    report = build_report(
        functions, {}, [LoweringDecision("helper", 4, 4, "iteration", "snapshot", "required_snapshot")]
    )
    result = select_and_check(report, {}, ["entry"], ["snapshot-iteration"])
    assert len(result["violations"]) == 1
    assert result["violations"][0]["origin"].endswith(":helper")
    return


def test_project_explanation_and_cli_gates(tmp_path) -> None:
    import json
    import subprocess
    import sys

    from py2rust.compiler.project import Project

    (tmp_path / "main.py").write_text("""
from py2rust.stdlib import Json
import json

def encode(value: Json) -> str:
    return json.dumps(value)

def snapshot(values: list[int]) -> int:
    total: int = 0
    for item in values:
        values.clear()
        total = total + item
    return total + len(values)

def entry(values: list[int]) -> int:
    return snapshot(values)

if __name__ == "__main__":
    print(entry([1, 2]))
""")
    plain = Project(tmp_path).compile()
    project = Project(tmp_path)
    assert project.compile(explain=True) == plain
    report = project.optimization_report
    encoded = next(row for row in report["functions"] if row["symbol"].endswith("__encode"))
    assert encoded["effects"]["costs"] == ["serialize_output", "validate_input"]
    assert encoded["parameters"][0]["mode"] == "borrow"
    command = [sys.executable, "-m", "py2rust", "explain", str(tmp_path)]
    accepted = subprocess.run(
        command + ["--function", "main.py:encode", "--deny", "unknown-effects"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["violations"] == []
    rejected = subprocess.run(
        command + ["--function", "main.py:entry", "--deny", "snapshot-iteration"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode == 2, rejected.stderr
    assert json.loads(rejected.stdout)["violations"][0]["origin"] == "main.py:snapshot"
    unmatched = subprocess.run(command + ["--function", "typo"], capture_output=True, text=True, check=False)
    assert unmatched.returncode == 1
    assert "no functions matched" in unmatched.stderr
    assert sorted(path.name for path in tmp_path.iterdir()) == ["main.py"]
    return
