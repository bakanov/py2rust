"""Write Python-shaped Cargo projects through the modular emitter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..project_output import cargo_module_files
from .emission import ModuleEmission, ModuleSource, ModularEmissionError, emit_modules


def format_rust_files(files: dict[str, str]) -> dict[str, str]:
    formatted = {}
    for name, source in files.items():
        result = subprocess.run(
            ["rustfmt", "--edition=2021", "--config", "skip_children=true"],
            input=source,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ModularEmissionError(f"rustfmt failed for {name}: {result.stderr}")
        formatted[name] = result.stdout
    return formatted


def write_modular_project(
    code: str,
    modules: tuple[ModuleSource, ...] | list[ModuleSource],
    output: Path,
    *,
    source_root: Path,
    binary_name: str = "py2rust-service",
    format_rust: bool = True,
    native_files: dict[str, bytes] | None = None,
) -> ModuleEmission:
    """Generate a new Cargo directory; existing nonempty destinations are never modified."""
    output = output.resolve()
    source_root = source_root.resolve()
    if output == source_root or source_root.is_relative_to(output):
        raise ModularEmissionError("modular output must not replace the Python source root or its parents")
    if output.exists() and any(output.iterdir()):
        raise ModularEmissionError("modular output directory must be new or empty")
    emission = emit_modules(code, modules, source_root=source_root)
    rust_files = format_rust_files(emission.files) if format_rust else emission.files
    emission = ModuleEmission(rust_files, emission.modules, emission.symbols)
    files = cargo_module_files(rust_files, binary_name)
    files.update(native_files or {})
    metadata = {
        "format": 1,
        "layout": "python-modules",
        "binary_name": binary_name,
        "modules": {
            module.name: {
                "python": module.path.resolve().relative_to(source_root).as_posix(),
                "rust": emission.modules[module.name],
            }
            for module in modules
        },
        "symbols": {
            symbol: {"module": item.module, "name": item.name, "rust": item.file, "path": item.path}
            for symbol, item in emission.symbols.items()
        },
    }
    files[".py2rust-modular.json"] = (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode()
    for name, content in files.items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return emission
