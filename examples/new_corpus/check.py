#!/usr/bin/env python3
"""Compare every selected OpenCiv3-inspired example with its exact expected output."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(__file__).resolve().parent


def run(
    command: list[str], project: Path, environment: dict[str, str], timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def check(project: Path, build_root: Path, python_only: bool, release: bool, online: bool) -> str | None:
    expected: str = (project / "expected.txt").read_text()
    environment: dict[str, str] = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else ""
    )
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    reference: subprocess.CompletedProcess[str] = run([sys.executable, "main.py"], project, environment, 30)
    if reference.returncode != 0:
        return "Python reference failed:\n" + reference.stdout + reference.stderr
    if reference.stdout != expected:
        return "Python output differs from expected.txt:\n" + reference.stdout
    if python_only:
        return None
    output: Path = build_root / project.name
    command: list[str] = [
        sys.executable,
        "-m",
        "py2rust",
        "build",
        str(project),
        "--name",
        "new-corpus-" + project.name[:3],
        "-o",
        str(output),
    ]
    if release:
        command.append("--release")
    if not online:
        command.append("--offline")
    try:
        build: subprocess.CompletedProcess[str] = run(command, project, environment, 240)
    except subprocess.TimeoutExpired:
        return "Native transpilation/build exceeded 240 seconds"
    if build.returncode != 0:
        return "Native transpilation/build failed:\n" + build.stdout + build.stderr
    executable: Path = output / "target" / ("release" if release else "debug") / ("new-corpus-" + project.name[:3])
    try:
        native: subprocess.CompletedProcess[str] = run([str(executable)], project, environment, 20)
    except subprocess.TimeoutExpired:
        return "Native executable exceeded 20 seconds"
    if native.returncode != 0:
        return "Native execution failed:\n" + native.stdout + native.stderr
    if native.stdout != expected:
        return "Rust output differs from expected.txt:\n" + native.stdout + "\nExpected:\n" + expected
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="numeric IDs such as 001 005; default: all examples")
    parser.add_argument("--python-only", action="store_true", help="check references without compiling Rust")
    parser.add_argument("--release", action="store_true", help="build optimized native executables")
    parser.add_argument("--online", action="store_true", help="allow Cargo to access the network")
    args = parser.parse_args()
    projects: list[Path] = sorted(path for path in CORPUS.glob("[0-9][0-9][0-9]_*") if path.is_dir())
    by_id: dict[str, Path] = {path.name[:3]: path for path in projects}
    requested: set[str] = {value.zfill(3) for value in args.ids}
    unknown: set[str] = requested - set(by_id)
    if unknown:
        parser.error("unknown example IDs: " + ", ".join(sorted(unknown)))
    selected: list[Path] = [path for path in projects if not requested or path.name[:3] in requested]
    default_build: Path = Path.home() / ".cache/py2rust-build"
    build_root: Path = Path(os.environ.get("PY2RUST_BUILD_DIR", str(default_build))) / "new-corpus"
    failures: int = 0
    for project in selected:
        error: str | None = check(project, build_root, args.python_only, args.release, args.online)
        if error is None:
            engines: str = "Python" if args.python_only else "Python + Rust"
            print("[ok] " + project.name + " (" + engines + ")", flush=True)
        else:
            failures += 1
            print("[failed] " + project.name + "\n" + error, file=sys.stderr, flush=True)
    print(str(len(selected) - failures) + "/" + str(len(selected)) + " examples passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
