"""Compatibility CLI for compiling one service entry point."""

import argparse
import subprocess
import sys
from pathlib import Path

from .service import ServiceError, create_service_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Transpile the typed HTTP/stdlib service subset into a Cargo project")
    parser.add_argument("source", type=Path)
    parser.add_argument("--frontend", choices=["typed", "legacy"], default="typed")
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.frontend == "typed":
            from .project import create_project

            create_project(args.source.resolve().parent, args.output, entry=args.source.name, frontend="typed")
        else:
            create_service_project(args.source.read_text(), args.output)
            subprocess.run(
                ["rustfmt", "--edition=2021", str(args.output / "src" / "main.rs")],
                check=True,
            )
    except (
        ServiceError,
        SyntaxError,
        ValueError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(
            f"{getattr(error, 'filename', None) or args.source}:{getattr(error, 'lineno', 1)}: {error}",
            file=sys.stderr,
        )
        return 1
    return 0
