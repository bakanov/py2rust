#!/usr/bin/env python3
"""Compare a preserved compiler and current compiler on Unicode access orders.

Run only while other builds/tests are idle. Compilation, input construction and
expected checksums are outside timing; each call includes its index construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def observe(binary: Path, engine: str, size: int, order: str, repeats: int) -> dict:
    return json.loads(
        subprocess.check_output(
            [str(binary), engine, str(size), order, str(repeats)],
            text=True,
            timeout=180,
        )
    )


def measure_peak_rss(
    cases: list[tuple[str, Path, str]], output: Path, *, size: int = 4_194_304, samples: int = 3
) -> dict:
    """Measure whole-process resident high-water marks, including input setup."""
    timer = Path("/usr/bin/time")
    if not timer.is_file():
        raise ValueError("peak RSS measurement requires GNU /usr/bin/time")
    readings: dict[str, list[int]] = {name: [] for name, _, _ in cases}
    expected = None
    for sample in range(samples):
        for name, binary, engine in (cases if sample % 2 == 0 else list(reversed(cases))):
            measurement = output / f"rss-{name}-{sample}.txt"
            observed = json.loads(
                subprocess.check_output(
                    [str(timer), "-f", "%M", "-o", str(measurement), str(binary), engine, str(size), "sequential", "1"],
                    text=True,
                    timeout=180,
                )
            )
            if expected is None:
                expected = observed["answer"]
            if observed["answer"] != expected:
                raise ValueError("memory-probe checksum mismatch")
            resident_kib = int(measurement.read_text().strip())
            if resident_kib <= 0:
                raise ValueError("invalid peak RSS measurement")
            readings[name].append(resident_kib)
    return {
        "characters": size,
        "order": "sequential",
        "metric": "whole-process maximum resident set size (KiB), including inputs and index construction",
        "samples_kib": readings,
        "medians_kib": {name: statistics.median(values) for name, values in readings.items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline-package", type=Path, required=True, help="Directory containing preserved py2rust package"
    )
    parser.add_argument(
        "--candidate-package", type=Path, default=ROOT, help="Compiler package root to compare against baseline"
    )
    parser.add_argument("--output", type=Path, required=True, help="Fresh artifact directory")
    parser.add_argument("--target-dir", type=Path, help="Optional reusable Cargo target on a Linux filesystem")
    parser.add_argument(
        "--smoke", action="store_true", help="Build and verify small checksums without timing comparisons"
    )
    parser.add_argument(
        "--memory", action="store_true", help="Also measure whole-process peak RSS with large sequential inputs"
    )
    args = parser.parse_args()
    if args.smoke and args.memory:
        parser.error("--smoke and --memory cannot be combined")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixtures = ROOT / "benchmarks/rust_quality"
    generate = """from pathlib import Path
import sys
from py2rust.compiler import service
assert Path(service.__file__).resolve().is_relative_to(Path(sys.argv[3]).resolve()), service.__file__
service.create_service_project(Path(sys.argv[1]).read_text(), Path(sys.argv[2]))
"""
    target = (args.target_dir or out / "target").resolve()
    for label, package in [("before", args.baseline_package.resolve()), ("after", args.candidate_package.resolve())]:
        if not (package / "py2rust/compiler/service.py").is_file():
            raise ValueError("not a compiler package root: " + str(package))
        project = out / label
        subprocess.run(
            [sys.executable, "-c", generate, str(fixtures / "unicode_access.py"), str(project), str(package)],
            cwd=out,
            env=dict(os.environ, PYTHONPATH=str(package), PYTHONDONTWRITEBYTECODE="1"),
            check=True,
        )
        main_rs = project / "src/main.rs"
        main_rs.write_text(
            main_rs.read_text().replace("fn main()", "fn generated_entry()")
            + "\n"
            + (fixtures / "unicode_harness.rs").read_text()
        )
        # Alternate projects sharing a package name must not reuse a stale executable.
        for path in (project / "src").glob("*.rs"):
            os.utime(path, None)
        with (out / f"{label}-build.log").open("w") as log:
            subprocess.run(
                [
                    "cargo",
                    "build",
                    "--release",
                    "--locked",
                    "--offline",
                    "--manifest-path",
                    str(project / "Cargo.toml"),
                ],
                env=dict(os.environ, CARGO_TARGET_DIR=str(target)),
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
        shutil.copy2(target / "release/py2rust-service", out / label / "probe")
    cases = [
        ("before", out / "before/probe", "generated"),
        ("after", out / "after/probe", "generated"),
        ("native", out / "after/probe", "native"),
    ]
    sources = {
        str(path.relative_to(out)): hashlib.sha256(path.read_bytes()).hexdigest()
        for label in ["before", "after"]
        for path in sorted((out / label / "src").glob("*.rs"))
    }
    (out / "source_sha256.json").write_text(json.dumps(sources, indent=2) + "\n")
    shutil.copy2(__file__, out / "measure.py")
    if args.smoke:
        verified = []
        for order in ["sequential", "reverse", "permuted"]:
            answers = [observe(binary, engine, 64, order, 1)["answer"] for _, binary, engine in cases]
            if len(set(answers)) != 1:
                raise ValueError("checksum mismatch: " + order)
            verified.append({"order": order, "answer": answers[0]})
        (out / "smoke.json").write_text(json.dumps(verified, indent=2) + "\n")
        print("Unicode access checksum smoke checks passed; no timing comparison performed")
        return 0
    rows = []
    for order in ["sequential", "reverse", "permuted"]:
        for size in [8192, 16384, 32768, 65536]:
            samples = {name: [] for name, _, _ in cases}
            repeats = {}
            for name, binary, engine in cases:
                warm = observe(binary, engine, size, order, 1)
                repeats[name] = max(1, min(1000, 20_000_000 // max(warm["ns"], 1)))
            for sample in range(7):
                for name, binary, engine in (cases if sample % 2 == 0 else list(reversed(cases))):
                    result = observe(binary, engine, size, order, repeats[name])
                    samples[name].append(result["ns"] / repeats[name])
            medians = {name: statistics.median(values) for name, values in samples.items()}
            row = {
                "characters": size,
                "order": order,
                "samples_ns": samples,
                "repeats": repeats,
                "medians_ns": medians,
                "speedup": medians["before"] / medians["after"],
                "native_ratio": medians["after"] / medians["native"],
            }
            rows.append(row)
            print(json.dumps(row), flush=True)
            (out / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    if args.memory:
        memory = measure_peak_rss(cases, out)
        (out / "peak-rss.json").write_text(json.dumps(memory, indent=2) + "\n")
        print(json.dumps(memory), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
