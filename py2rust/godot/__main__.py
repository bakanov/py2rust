"""Generate or verify a Godot native project."""

from __future__ import annotations

import argparse
from pathlib import Path

from .generator import GodotGenerationError, GodotProject, generate_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a consolidated Rust GDExtension for OpenCiv3")
    parser.add_argument("root", type=Path, help="Godot project root containing project.godot")
    parser.add_argument("--check", action="store_true", help="Fail if generated files differ without rewriting them")
    arguments = parser.parse_args()
    try:
        files = generate_project(GodotProject(arguments.root), check=arguments.check)
    except GodotGenerationError as error:
        parser.error(str(error))
    print(f"{'Verified' if arguments.check else 'Generated'} {len(files)} files in {arguments.root / 'native'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
