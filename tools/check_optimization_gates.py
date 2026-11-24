#!/usr/bin/env python3
"""Deterministic optimization checks; suitable for CI without timing thresholds."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from py2rust.compiler.diagnostics import select_and_check
from py2rust.compiler.pipeline import compile_loaded_project
from py2rust.compiler.project import Project

ROOT = Path(__file__).resolve().parents[1]


def check_gates(root: Path = ROOT, manifest: Path | None = None, *, frontend: str = "typed") -> list[str]:
    if frontend not in {"typed", "legacy"}:
        raise ValueError("unknown compiler frontend: " + frontend)
    specification = json.loads((manifest or root / "benchmarks/optimization-gates.json").read_text())
    if specification["schema_version"] != 1 or not specification["cases"]:
        raise ValueError("expected nonempty version-1 optimization gates")
    projects: dict[tuple[str, str], Project] = {}
    passed = []
    for case in specification["cases"]:
        key = case["project"], case["entry"]
        if key not in projects:
            project = Project(root / key[0], key[1])
            if frontend == "typed":
                compile_loaded_project(project, explain=True)
            else:
                project.compile(explain=True)
            projects[key] = project
        project = projects[key]
        report = select_and_check(
            project.optimization_report, project.source_map, [case["function"]], case.get("deny", [])
        )
        if report["violations"]:
            raise ValueError(f"{case['name']}: {report['violations']}")
        if len(report["functions"]) != 1:
            raise ValueError(f"{case['name']}: gate must select exactly one function")
        function = report["functions"][0]
        parameters = {item["name"]: item["mode"] for item in function["parameters"]}
        for name, mode in case.get("parameters", {}).items():
            if parameters.get(name) != mode:
                raise ValueError(f"{case['name']}: expected {name} to {mode}, got {parameters.get(name)}")
        for expected in case.get("decisions", []):
            if not expected or not any(
                all(actual.get(key) == value for key, value in expected.items()) for actual in function["decisions"]
            ):
                raise ValueError(f"{case['name']}: missing lowering {expected}")
        passed.append(case["name"])
    return passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", choices=["typed", "legacy"], default="typed")
    args = parser.parse_args()
    for name in check_gates(frontend=args.frontend):
        print("passed:", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
