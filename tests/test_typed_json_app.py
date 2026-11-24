"""Compile and execute the existing mixed-language JSON application unchanged."""

import json
import os
import subprocess
from pathlib import Path

from py2rust.compiler.pipeline import compile_project
from py2rust.compiler.service import write_service_project

from .test_services import ROOT, TARGET


def test_existing_json_application(tmp_path: Path) -> None:
    code = compile_project(ROOT / "examples/projects/json_app")
    write_service_project(code, tmp_path)
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0")
    build = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(tmp_path / "Cargo.toml")],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert build.returncode == 0, build.stderr + code
    result = subprocess.run(
        [str(TARGET / "debug" / "py2rust-service")], capture_output=True, text=True, timeout=10, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "message": "Hello, 世界",
        "path": "/hello",
        "bytes": 6,
        "status": "ok",
        "version": 1,
    }
