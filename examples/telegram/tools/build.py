#!/usr/bin/env python3
"""Development/build tooling; the application itself is compiled from main.py."""

import os
import shutil
import subprocess
from pathlib import Path

from py2rust.compiler.project import create_project

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".py2rust/rust"
# This app needs its own Cargo target: unrelated test projects use the same
# binary name, and Cargo can otherwise leave their executable in the shared slot.
TARGET = OUTPUT / "target"


def build() -> Path:
    create_project(ROOT, OUTPUT)
    subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--manifest-path",
            str(OUTPUT / "Cargo.toml"),
            "--target-dir",
            str(TARGET),
        ],
        env=dict(os.environ, CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0"),
        check=True,
    )
    binary = ROOT / ".py2rust/bin/paper-plane-server"
    binary.parent.mkdir(parents=True, exist_ok=True)
    temporary = binary.with_suffix(f".{os.getpid()}.new")
    shutil.copy2(TARGET / "debug/py2rust-service", temporary)
    temporary.replace(binary)
    return binary


if __name__ == "__main__":
    print(build())
