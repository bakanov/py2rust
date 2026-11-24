"""Run unchanged corpus acceptance checks against the typed IR pipeline."""

import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from py2rust.compiler.pipeline import compile_project
from py2rust.compiler.service import write_service_project

from .test_services import TARGET


@pytest.mark.parametrize(
    "identifier",
    [
        "006",
        "016",
        "020",
        "026",
        "038",
        "053",
        "057",
        "060",
        "063",
        "065",
        "068",
        "079",
        "086",
        "089",
        "091",
        "096",
        "097",
        "100",
        "102",
        "108",
        "114",
        "118",
    ],
)
def test_typed_corpus_acceptance(tmp_path: Path, monkeypatch, identifier: str) -> None:
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root / "tools"))
    from corpus_checks.common import Application

    catalog = json.loads((root / "examples/corpus/catalog.json").read_text())["programs"]
    program = next(item for item in catalog if item["id"] == identifier)
    source = root / "examples/corpus" / program["path"]
    generated = tmp_path / "generated"
    write_service_project(compile_project(source), generated)
    build = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(generated / "Cargo.toml")],
        env=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    binary = tmp_path / "typed-application"
    shutil.copyfile(TARGET / "debug/py2rust-service", binary)
    binary.chmod(0o755)
    check = importlib.import_module("corpus_checks." + program["check"]).check
    observations = {}
    for engine, command in [("python", [sys.executable, "-u", str(source / "main.py")]), ("rust", [str(binary)])]:
        directory = tmp_path / engine
        directory.mkdir()
        observations[engine] = check(Application(command, engine), directory)
    assert observations["python"] == observations["rust"]
