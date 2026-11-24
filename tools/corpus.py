#!/usr/bin/env python3
"""Build and verify the 120-program catalog without treating pending work as passing."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import tokenize
import traceback
from functools import lru_cache
from pathlib import Path

from corpus_checks.common import Application

from py2rust.compiler.project import Project, create_project

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "examples/corpus"
BUILD_ROOT = Path(os.environ.get("PY2RUST_BUILD_DIR", str(ROOT / "build")))
BUILD = BUILD_ROOT / "corpus"
TARGET = BUILD_ROOT / "service-test-target"
# 094 deliberately inspects the native import boundary. All other applications
# retain the all-Python policy; these small adapter fixtures contain no case/report policy.
NATIVE_FIXTURES = {"094": {"native_numbers.rs", "native_text.rs", "native_values.rs"}}


def substantive_lines(path: Path) -> int:
    source = path.read_text()
    tree = ast.parse(source)
    documentation: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and ast.get_docstring(node) is not None
        ):
            documentation.update(range(node.body[0].lineno, node.body[0].end_lineno + 1))
    ignored = {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
        tokenize.ENCODING,
    }
    lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in ignored and token.start[0] not in documentation:
            # Bulk multiline string literals count once, never as application logic.
            lines.add(token.start[0])
    return len(lines)


def source_files(program: dict) -> list[Path]:
    if not program["path"]:
        return []
    return sorted(
        path
        for path in (CORPUS / program["path"]).rglob("*.py")
        if not any(part.startswith(".") or part == "__pycache__" for part in path.relative_to(CORPUS).parts)
    )


def checker_sources(name: str) -> set[Path]:
    """Follow static local imports so unrelated applications do not stale this check."""
    root = ROOT / "tools"
    pending = [root.joinpath("corpus_checks", *name.split(".")).with_suffix(".py"), root / "corpus_checks/__init__.py"]
    found: set[Path] = set()

    def include(module: Path, required: bool = False) -> None:
        if module.with_suffix(".py").is_file():
            pending.append(module.with_suffix(".py"))
        elif module.is_dir():
            pending.append(module / "__init__.py")
        elif required:
            pending.append(module.with_suffix(".py"))
        return  # noqa: PLR1711 - explicit return required by repository guidelines

    while pending:
        path = pending.pop().resolve()
        if not path.is_relative_to(root):
            raise ValueError("checker local imports must remain inside tools")
        if path in found:
            continue
        found.add(path)
        if not path.is_file():
            continue
        for parent in path.parents:
            if parent == root:
                break
            pending.append(parent / "__init__.py")
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            ):
                raise ValueError("checker dependencies require static imports")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "importlib" or alias.name.startswith("importlib."):
                        raise ValueError("checker dependencies require static imports")
                    include(root.joinpath(*alias.name.split(".")))
            elif isinstance(node, ast.ImportFrom):
                if node.module == "importlib" or (node.module or "").startswith("importlib."):
                    raise ValueError("checker dependencies require static imports")
                base = path.parent if node.level else root
                for _level in range(max(0, node.level - 1)):
                    base = base.parent
                module = base.joinpath(*(node.module or "").split("."))
                include(module, required=bool(node.level) or (node.module or "").startswith("corpus_checks."))
                for alias in node.names:
                    if alias.name != "*":
                        include(module / alias.name, required=module.is_dir())
    return found


def native_source_files(program: dict) -> list[Path]:
    if not program["path"]:
        return []
    root = CORPUS / program["path"]
    return sorted(
        path for path in root.rglob("*.rs") if not any(part.startswith(".") for part in path.relative_to(root).parts)
    )


def validate_project_sources(program: dict, project: Project) -> dict[str, str]:
    """Require every Python module and exactly the explicitly allowed adapter fixtures."""
    root = CORPUS / program["path"]
    declared = program.get("native_adapters", [])
    assert isinstance(declared, list) and all(isinstance(name, str) for name in declared), "invalid native declaration"
    assert len(declared) == len(set(declared)), "duplicate native declaration"
    if declared:
        assert set(declared) == NATIVE_FIXTURES.get(program["id"], set()), "native adapters are only permitted for 094"
    actual = native_source_files(program)
    assert {str(path.relative_to(root)) for path in actual} == set(declared), "undeclared or missing native adapter"
    assert all(not path.is_symlink() for path in actual), "native adapter aliases are not allowed"
    linked_python = {module.path.resolve() for module in project.modules.values() if module.tree is not None}
    linked_native = {module.path.resolve() for module in project.modules.values() if module.tree is None}
    assert set(source_files(program)) <= linked_python, "application has untranspiled Python modules"
    assert linked_native == {path.resolve() for path in actual}, "native module inventory mismatch"
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in actual}


def reference_command(program: dict) -> list[str]:
    command = [sys.executable, "-u"]
    if program.get("native_adapters"):
        assert program["id"] == "094", "unexpected native reference shim"
        command.append(str(ROOT / "tools/corpus_checks/native_reference/runner.py"))
    return command + [str(CORPUS / program["path"] / "main.py")]


@lru_cache(maxsize=1)
def typed_dependency_fingerprint() -> str:
    """Identify the installed frontend and bundled typing definitions for evidence."""
    from importlib.metadata import version

    import mypy

    package = Path(mypy.__file__).resolve().parent
    digest = hashlib.sha256()
    digest.update(version("mypy").encode())
    digest.update(sys.version.encode())
    for source in sorted(package.rglob("*")):
        if source.is_file() and source.suffix in {".py", ".pyi", ".so"}:
            digest.update(source.relative_to(package).as_posix().encode())
            digest.update(source.read_bytes())
    return digest.hexdigest()


def fingerprint(program: dict, frontend: str = "typed") -> str:
    files = source_files(program)
    files += native_source_files(program)
    if program.get("native_adapters"):
        files += [ROOT / "tools/corpus_checks/native_reference/runner.py"]
    files += [CORPUS / program["path"] / name for name in program.get("assets", [])]
    files += [Path(__file__), ROOT / "pyproject.toml", ROOT / "py2rust/compiler/frontend/mypy-source.json"]
    files += sorted((ROOT / "py2rust/compiler").rglob("*.py"))
    files += sorted((ROOT / "py2rust").glob("*.py"))
    files += sorted((ROOT / "py2rust/compiler/service_runtime/src").rglob("*.rs"))
    files += sorted(checker_sources(program["check"]))
    files += [
        ROOT / "py2rust/compiler/service_runtime/Cargo.toml",
        ROOT / "py2rust/compiler/service_runtime/Cargo.lock",
    ]
    digest = hashlib.sha256()
    digest.update(b"complete-application-evidence-v3\0")
    digest.update(frontend.encode())
    if frontend == "typed":
        digest.update(typed_dependency_fingerprint().encode())
    digest.update(json.dumps(program, sort_keys=True, separators=(",", ":")).encode())
    for path in sorted(set(files)):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes() if path.is_file() else b"<missing-source-file>")
    return digest.hexdigest()


def evidence_root(frontend: str) -> Path:
    return BUILD if frontend == "legacy" else BUILD.with_name("typed-" + BUILD.name)


def verify(program: dict, frontend: str = "typed") -> dict:
    identifier = program["id"]
    work = evidence_root(frontend) / identifier
    work.mkdir(parents=True, exist_ok=True)
    report = {
        "id": identifier,
        "title": program["title"],
        "status": "failed",
        "frontend": frontend,
        "fingerprint": fingerprint(program, frontend),
        "stages": {},
    }
    try:
        root = CORPUS / program["path"]
        files = source_files(program)
        report["sloc_by_file"] = {str(path.relative_to(root)): substantive_lines(path) for path in files}
        report["sloc"] = sum(report["sloc_by_file"].values())
        assert program["minimum_sloc"] <= report["sloc"] <= program["maximum_sloc"], report["sloc_by_file"]
        report["stages"]["size"] = "passed"
        name = "corpus_" + identifier
        project = create_project(root, work / "rust", binary_name=name, frontend=frontend)
        report["native_adapter_sha256"] = validate_project_sources(program, project)
        if program.get("native_adapters"):
            report["python_reference"] = (
                "094 uses explicit test-only native adapter shims; Rust calls the .rs files directly"
            )
        report["stages"]["whole_project_transpilation"] = "passed"
        build = subprocess.run(
            [
                "cargo",
                "build",
                "--locked",
                "--offline",
                "--manifest-path",
                str(work / "rust/Cargo.toml"),
                "--bin",
                name,
            ],
            env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        (work / "build.log").write_text(build.stdout + build.stderr)
        assert build.returncode == 0, f"Cargo failed; see {work / 'build.log'}"
        binary = work / name
        shutil.copyfile(TARGET / "debug" / name, work / (name + ".new"))
        (work / (name + ".new")).chmod(0o755)
        (work / (name + ".new")).replace(binary)
        report["stages"]["native_build"] = "passed"
        check = importlib.import_module("corpus_checks." + program["check"]).check
        observations = {}
        for engine, command in [("python", reference_command(program)), ("rust", [str(binary)])]:
            directory = work / "runs" / engine
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)
            observations[engine] = check(Application(command, engine), directory)
            report["stages"][engine + "_acceptance"] = "passed"
        assert observations["python"] == observations["rust"], observations
        report["observations"] = observations["rust"]
        report["stages"]["behavioral_parity"] = "passed"
        report["native_environment"] = "PATH, PYTHONHOME and PYTHONPATH=/nonexistent"
        report["status"] = "verified"
    except Exception:  # noqa: BLE001 - record every failed stage and continue checking other programs
        report["error"] = traceback.format_exc()
    report["checked_at_unix"] = time.time()
    (work / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def status(programs: list[dict], frontend: str = "typed") -> dict[str, int]:
    build = evidence_root(frontend)
    totals = {"verified": 0, "stale": 0, "failed": 0, "in_progress": 0, "pending": 0}
    rows = []
    for program in programs:
        state = "in_progress" if source_files(program) else "pending"
        evidence = build / program["id"] / "result.json"
        if evidence.exists():
            result = json.loads(evidence.read_text())
            state = result["status"] if result["fingerprint"] == fingerprint(program, frontend) else "stale"
        totals[state] += 1
        rows.append({"id": program["id"], "title": program["title"], "status": state})
    build.mkdir(parents=True, exist_ok=True)
    (build / "status.json").write_text(json.dumps({"totals": totals, "programs": rows}, indent=2) + "\n")
    print("Catalog: " + ", ".join(f"{count} {key}" for key, count in totals.items()), flush=True)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*", help="catalog IDs; omit to require verification of all 120")
    parser.add_argument("--status", action="store_true", help="show current evidence without running applications")
    parser.add_argument("--frontend", choices=["legacy", "typed"], default="typed")
    args = parser.parse_args()
    programs = json.loads((CORPUS / "catalog.json").read_text())["programs"]
    if args.status:
        status(programs, args.frontend)
        return 0
    requested = {str(int(value)).zfill(3) for value in args.ids}
    assert requested <= {item["id"] for item in programs}, "unknown program ID"
    passed = True
    for program in programs:
        if requested and program["id"] not in requested:
            continue
        if not source_files(program):
            print(program["id"] + ": pending (no implementation)", flush=True)
            passed = False
            continue
        report = verify(program, args.frontend)
        print(f"{program['id']}: {report['status']} ({report.get('sloc', 0)} Python SLOC)", flush=True)
        if report["status"] != "verified":
            print(report["error"], flush=True)
            passed = False
    totals = status(programs, args.frontend)
    return 0 if passed and (requested or totals["verified"] == 120) else 1


if __name__ == "__main__":
    raise SystemExit(main())
