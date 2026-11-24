"""Run the existing full chat acceptance workflow through the typed compiler."""

import os
import shutil
import subprocess
from pathlib import Path

from py2rust.compiler.pipeline import compile_project
from py2rust.compiler.service import write_service_project

from .test_services import TARGET
from .test_telegram import APP
from .test_telegram import test_real_chat_workflow as run_workflow


def test_typed_chat_workflow(tmp_path: Path) -> None:
    code = compile_project(APP)
    output = tmp_path / "generated"
    write_service_project(code, output)
    env = dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0")
    result = subprocess.run(
        ["cargo", "build", "--locked", "--offline", "--manifest-path", str(output / "Cargo.toml")],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr + code
    binary = tmp_path / "typed-chat"
    shutil.copyfile(TARGET / "debug" / "py2rust-service", binary)
    binary.chmod(0o755)
    run_workflow(tmp_path, binary, "rust")
