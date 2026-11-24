"""Run the checked benchmark inside Docker and export only useful artifacts."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--sizes", type=int, nargs="+", default=[10000, 100000])
    args = parser.parse_args()
    if args.samples < 3 or any(size < 1 for size in args.sizes):
        parser.error("use at least three samples and positive input sizes")
    output = Path("/output")
    output.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S-")
    destination = Path(tempfile.mkdtemp(prefix=stamp, dir=output))
    print("Transpiling and compiling release binaries; the first build may take a few minutes.", flush=True)
    print(f"Export directory: {destination}", flush=True)
    # Cargo builds on container storage, even when /output is an exFAT mount.
    with tempfile.TemporaryDirectory(prefix="py2rust-benchmark-") as temporary:
        work = Path(temporary) / "benchmark"
        command = [
            sys.executable,
            str(ROOT / "tools/compare_access_log.py"),
            "--offline",
            "--output",
            str(work),
            "--samples",
            str(args.samples),
            "--sizes",
            *map(str, args.sizes),
        ]
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            log = work / "build.log"
            if log.exists():
                shutil.copyfile(log, destination / "build.log")
                print(log.read_text(), file=sys.stderr)
            raise SystemExit(result.returncode)
        shutil.copytree(work / "generated", destination / "rust")
        binaries = destination / "bin"
        binaries.mkdir()
        for name in ("access-log-generated", "access-log-native"):
            shutil.copyfile(work / "target/release" / name, binaries / name)
            (binaries / name).chmod(0o755)
        for name in ("results.json", "build.log"):
            shutil.copyfile(work / name, destination / name)
        sample = ROOT / "examples/projects/access_log/sample.jsonl"
        shutil.copyfile(sample, destination / "sample.jsonl")
        print("\nSample program output:", flush=True)
        subprocess.run(
            [str(work / "target/release/access-log-generated")],
            env=dict(os.environ, ACCESS_LOG=str(sample)),
            check=True,
        )
    print(f"\nSaved Rust: {destination}/rust/src/main.rs")
    print(f"Saved executable: {destination}/bin/access-log-generated")
    print(f"Saved measurements: {destination}/results.json")
    print("The /output directory is your mounted host directory. Earlier runs are preserved.")
    return


if __name__ == "__main__":
    main()
