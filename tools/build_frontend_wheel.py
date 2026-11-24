#!/usr/bin/env python3
"""Build the reviewed mypy snapshot as a pure-Python frontend wheel."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from urllib.request import urlopen
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "py2rust/compiler/frontend/mypy-source.json"
BUILD_FILES = ("setup.py", "pyproject.toml", "MANIFEST.in", "LICENSE")
IGNORED = {"__pycache__", ".mypy_cache", ".pytest_cache", ".git", "build", "dist"}


def source_files(source: Path) -> list[Path]:
    files = [source / name for name in BUILD_FILES]
    for package in ("mypy", "mypyc"):
        if not (source / package).is_dir():
            raise ValueError(f"missing supplied package: {source / package}")
        files.extend(
            path
            for path in (source / package).rglob("*")
            if path.is_file()
            and not IGNORED.intersection(path.relative_to(source).parts)
            and path.suffix not in {".pyc", ".pyo"}
        )
    for path in files:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"frontend input must be a regular file: {path}")
        if path.suffix in {".so", ".pyd", ".dll", ".dylib"}:
            raise ValueError(f"compiled frontend input is not supported: {path}")
    return sorted(files)


def source_digest(source: Path, files: list[Path]) -> str:
    inventory = [(path.relative_to(source).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()) for path in files]
    return hashlib.sha256(json.dumps(inventory, separators=(",", ":")).encode()).hexdigest()


def fetch_source(destination: Path) -> Path:
    """Fetch the immutable upstream archive; build() verifies its source inventory."""
    contract = json.loads(CONTRACT.read_text())
    revision = contract["upstream_revision"]
    if len(revision) != 40 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("invalid pinned frontend revision")
    archive_path = destination / "mypy.zip"
    url = f"https://codeload.github.com/python/mypy/zip/{revision}"
    with urlopen(url, timeout=60) as response, archive_path.open("wb") as output:
        shutil.copyfileobj(response, output)
    source = destination / f"mypy-{revision}"
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(source.resolve()):
                raise ValueError("unexpected path in frontend archive")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as data, target.open("wb") as output:
                    shutil.copyfileobj(data, output)
    return source


def build(source: Path, output: Path) -> Path:
    if output == source or output.is_relative_to(source):
        raise ValueError("wheel output must be outside the supplied mypy source")
    contract = json.loads(CONTRACT.read_text())
    files = source_files(source)
    digest = source_digest(source, files)
    if digest != contract["source_sha256"]:
        raise ValueError(
            "supplied mypy source differs from the reviewed snapshot; update and validate the contract first"
        )
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="py2rust-frontend-wheel-") as temporary:
        stage = Path(temporary) / "source"
        for path in files:
            destination = stage / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
        # Only the staged copy is changed; the user's supplied checkout remains intact.
        (stage / "mypy/version.py").write_text(f'__version__ = {contract["wheel_version"]!r}\n')
        wheels = Path(temporary) / "wheels"
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), str(stage)],
            env=dict(os.environ, MYPY_USE_MYPYC="0", SOURCE_DATE_EPOCH="315532800"),
            check=True,
        )
        built = list(wheels.glob("mypy-*-py3-none-any.whl"))
        if len(built) != 1:
            raise ValueError("expected exactly one pure-Python mypy wheel")
        wheel = built[0]
        with zipfile.ZipFile(wheel) as archive:
            if any(Path(name).suffix in {".so", ".pyd", ".dll", ".dylib"} for name in archive.namelist()):
                raise ValueError("frontend wheel unexpectedly contains compiled extensions")
            version = archive.read("mypy/version.py").decode()
            if contract["wheel_version"] not in version:
                raise ValueError("wheel version does not match the reviewed frontend contract")
            for required in ("mypy/nodes.py", "mypy/traverser.py", "mypy/typeshed/stdlib/builtins.pyi"):
                archive.getinfo(required)
        destination = output / wheel.name
        shutil.copyfile(wheel, destination)
    receipt = {
        "source_sha256": digest,
        "wheel_version": contract["wheel_version"],
        "wheel": destination.name,
        "wheel_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
    }
    destination.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, nargs="?", help="an existing reviewed mypy checkout")
    parser.add_argument("--fetch", action="store_true", help="download the pinned upstream source")
    parser.add_argument("--output", type=Path, required=True, help="wheel cache on Linux storage")
    args = parser.parse_args()
    if args.fetch == (args.source is not None):
        parser.error("provide either a source checkout or --fetch")
    try:
        if args.fetch:
            with tempfile.TemporaryDirectory(prefix="py2rust-frontend-download-") as temporary:
                source = fetch_source(Path(temporary))
                print(build(source, args.output.resolve()))
        else:
            print(build(args.source.resolve(), args.output.resolve()))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
