"""Generate a Python-shaped project from Python source or an existing flat emission."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..project import Project, native_source_files
from .emission import ModuleSource
from .project import write_modular_project


def _entry_name(root: Path, entry: Path) -> str:
    parts = list(entry.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts:
        raise ValueError("root __init__.py cannot be the entry point")
    return ".".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit one Rust module per Python module")
    parser.add_argument("project", type=Path)
    parser.add_argument("--entry", default="main.py")
    parser.add_argument("--flat-source", type=Path, help="reuse an existing flat main.rs instead of compiling")
    parser.add_argument("--python-scope", action="store_true")
    parser.add_argument("--name", default="py2rust-service")
    parser.add_argument("--no-format", action="store_true")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project.resolve()
    project = Project(root, args.entry)
    entry = _entry_name(root, project.entry)
    if args.flat_source is None:
        from ..pipeline import compile_loaded_project

        code = compile_loaded_project(project, packaged=True, python_scope=args.python_scope)
    else:
        project.load(entry)
        code = args.flat_source.read_text()
    modules = [ModuleSource.from_project(module) for module in project.modules.values()]
    emission = write_modular_project(
        code,
        modules,
        args.output,
        source_root=root,
        binary_name=args.name,
        format_rust=not args.no_format,
        native_files=native_source_files(project, args.output.resolve()),
    )
    print(f"Wrote {len(emission.modules)} Python-shaped Rust modules to {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
