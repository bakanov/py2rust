#!/usr/bin/env python3
"""Build the actual portable compiler sources as a native IR-to-Rust executable.

The IR mode receives typed IR; source mode uses the portable subset frontend. Sources
are copied without rewriting; no emitted application code is bundled in it.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from py2rust.compiler.project import create_project

ROOT = Path(__file__).resolve().parents[1]

DRIVER = """from py2rust.stdlib import env_get, json_loads_unique, read_text, write_text
from compiler.native.emitter import emit_document

def main() -> None:
    source: str = env_get("PY2RUST_IR_INPUT", "")
    destination: str = env_get("PY2RUST_RUST_OUTPUT", "")
    assert source != "" and destination != "", "set PY2RUST_IR_INPUT and PY2RUST_RUST_OUTPUT"
    code: str = emit_document(json_loads_unique(read_text(source)))
    write_text(destination, code)
    return

if __name__ == "__main__":
    main()
"""


SOURCE_DRIVER = """from py2rust.stdlib import Json, env_get, json_loads_unique, json_array, read_text, write_text
from compiler.native.emitter import emit_document
from compiler.native.source_frontend import compile_sources

def main() -> None:
    bundle: str = env_get("PY2RUST_SOURCE_INPUT", "")
    source: str = env_get("PY2RUST_PYTHON_INPUT", "")
    destination: str = env_get("PY2RUST_RUST_OUTPUT", "")
    assert destination != "" and (bundle != "" or source != ""), "set source input and Rust output paths"
    assert bundle == "" or source == "", "choose a source bundle or a single Python file"
    modules: list[Json] = []
    if source != "":
        modules.append({"name": "main", "package": "", "path": source, "source": read_text(source)})
    else:
        modules = json_array(json_loads_unique(read_text(bundle)))
    code: str = emit_document(compile_sources(modules, "main"))
    write_text(destination, code)
    return

if __name__ == "__main__":
    main()
"""


def stage_sources(output: Path, source_mode: bool = False) -> Path:
    source = output / "python"
    source.mkdir(parents=True, exist_ok=True)
    (source / "main.py").write_text(SOURCE_DRIVER if source_mode else DRIVER)
    compiler = ROOT / "py2rust/compiler"
    destination = source / "compiler"
    destination.mkdir(exist_ok=True)
    shutil.copy2(compiler / "__init__.py", destination / "__init__.py")
    for family in ["native", "rules"]:
        (destination / family).mkdir(exist_ok=True)
        for file in (compiler / family).glob("*.py"):
            shutil.copy2(file, destination / family / file.name)
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--source", action="store_true", help="build the native Python-subset frontend")
    args = parser.parse_args()
    source = stage_sources(args.output, source_mode=args.source)
    name = "py2rust-native-source" if args.source else "py2rust-native-ir"
    create_project(source, args.output / "rust", binary_name=name, frontend="typed")
    if args.build:
        result = subprocess.run(
            ["cargo", "build", "--locked", "--offline", "--manifest-path", str(args.output / "rust/Cargo.toml")],
            check=False,
        )
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
