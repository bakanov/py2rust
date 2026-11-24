"""Strict ownership boundary checks propagate without claiming all-copy coverage."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes and explicit returns
import json
import os
import subprocess
import sys
from pathlib import Path

from py2rust.compiler.diagnostics import select_and_check
from py2rust.compiler.project import Project


def test_owned_boundary_gate(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("""
def owned(value: str) -> str:
    value = value + "!"
    return value

def materializing(value: str) -> str:
    return value

def snapshot(values: list[int]) -> int:
    values.append(1)
    saved: list[int] = values
    values.append(2)
    return len(saved)

def wrapper(values: list[int]) -> int:
    return snapshot(values)

if __name__ == "__main__":
    print(wrapper([1]))
""")
    project = Project(tmp_path)
    project.compile(explain=True)
    gate = ["owned-boundary-copy"]
    accepted = select_and_check(project.optimization_report, project.source_map, ["main.py:owned"], gate)
    assert not accepted["violations"]
    materialized = select_and_check(project.optimization_report, project.source_map, ["main.py:materializing"], gate)
    assert len(materialized["violations"]) == 1
    assert materialized["violations"][0]["reason"] == "borrowed_value_requires_owned_result"
    rejected = select_and_check(project.optimization_report, project.source_map, ["main.py:wrapper"], gate)
    assert len(rejected["violations"]) == 1
    assert rejected["violations"][0]["origin"] == "main.py:snapshot"
    assert rejected["violations"][0]["reason"] == "value_live_after_use"
    # Ensure the public CLI accepts the new named gate and returns its specified status.
    result = subprocess.run(
        [sys.executable, "-m", "py2rust", "explain", str(tmp_path), "--function", "main.py:wrapper", "--deny", *gate],
        cwd=tmp_path,
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stderr
    assert json.loads(result.stdout)["violations"] == rejected["violations"]
    return
