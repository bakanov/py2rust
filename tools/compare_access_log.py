"""Build both access-log implementations and compare checked, alternating release runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

from py2rust.compiler.project import create_project

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/projects/access_log"
NATIVE = ROOT / "benchmarks/access_log/native.rs"


def fixture(path: Path, size: int) -> dict:
    expected = {"requests": size, "errors": 0, "total_bytes": 0, "max_elapsed_ms": 0, "routes": {}}
    with path.open("w", encoding="utf-8") as stream:
        for index in range(size):
            route = f"/rooms/{index % 127}/世界" if index % 11 else '/files/quoted"name'
            status = 503 if index % 17 == 0 else 200
            count = index * 97 % 65536
            elapsed = index * 13 % 1000
            event = {"path": route + f"?page={index % 5}", "status": status, "bytes": count, "elapsed_ms": elapsed}
            stream.write(json.dumps(event, ensure_ascii=index % 3 == 0, separators=(",", ":")) + "\n")
            if index % 101 == 0:
                stream.write(" \t\n")
            expected["errors"] += status >= 400
            expected["total_bytes"] += count
            expected["max_elapsed_ms"] = max(expected["max_elapsed_ms"], elapsed)
            expected["routes"][route] = expected["routes"].get(route, 0) + 1
    return expected


def observe(command: list[str], path: Path, expected: dict) -> float:
    environment = dict(os.environ, ACCESS_LOG=str(path), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    start = time.perf_counter_ns()
    result = subprocess.run(command, env=environment, capture_output=True, text=True, check=True, timeout=120)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    assert json.loads(result.stdout) == expected, "summary differs from the independent input oracle"
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new artifact directory on Linux storage")
    parser.add_argument("--offline", action="store_true", help="use cached Cargo dependencies")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10000, 100000])
    parser.add_argument("--samples", type=int, default=7)
    args = parser.parse_args()
    if args.samples < 3 or any(size < 1 for size in args.sizes):
        parser.error("use at least three samples and positive input sizes")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "generated"
    create_project(EXAMPLE, project, binary_name="access-log-generated")
    native = project / "src/bin/access-log-native.rs"
    native.parent.mkdir()
    shutil.copyfile(NATIVE, native)
    build = ["cargo", "build", "--release", "--locked", "--bins", "--manifest-path", str(project / "Cargo.toml")]
    if args.offline:
        build.append("--offline")
    target = output / "target"
    with (output / "build.log").open("w") as log:
        subprocess.run(build, env=dict(os.environ, CARGO_TARGET_DIR=str(target)), stdout=log, stderr=log, check=True)
    binaries = {name: [str(target / "release" / f"access-log-{name}")] for name in ["generated", "native"]}
    reference = [sys.executable, str(EXAMPLE / "main.py")]
    sample_expected = {
        "requests": 5,
        "errors": 2,
        "total_bytes": 11456,
        "max_elapsed_ms": 120,
        "routes": {"/api/messages": 3, "/files/世界.png": 1, "/api/search": 1},
    }
    for command in [reference, *binaries.values()]:
        observe(command, EXAMPLE / "sample.jsonl", sample_expected)
    rows = []
    for size in args.sizes:
        path = output / f"events-{size}.jsonl"
        expected = fixture(path, size)
        observe(reference, path, expected)
        samples: dict[str, list[float]] = {name: [] for name in binaries}
        for command in binaries.values():
            observe(command, path, expected)  # Warm executable and filesystem caches.
        for index in range(args.samples):
            order = ["generated", "native"] if index % 2 == 0 else ["native", "generated"]
            for name in order:
                samples[name].append(observe(binaries[name], path, expected))
        medians = {name: statistics.median(values) for name, values in samples.items()}
        row = {
            "records": size,
            "input_bytes": path.stat().st_size,
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "samples_ms": samples,
            "median_ms": medians,
            "generated_over_native": medians["generated"] / medians["native"],
        }
        rows.append(row)
        print(
            f"{size:,} records: generated {medians['generated']:.2f} ms; native {medians['native']:.2f} ms; "
            f"ratio {row['generated_over_native']:.2f}x",
            flush=True,
        )
    sources = [EXAMPLE / "main.py", EXAMPLE / "analysis.py", NATIVE, Path(__file__).resolve()]
    report = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "method": "release; same Cargo dependency graph; alternating separate processes; warm file cache; includes startup, read, parse, aggregation and JSON stdout; excludes build and fixture generation",
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources
        },
        "generated_sha256": hashlib.sha256((project / "src/main.rs").read_bytes()).hexdigest(),
        "rows": rows,
    }
    (output / "results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(f"Rust source: {project / 'src/main.rs'}\nMeasurements: {output / 'results.json'}")
    return


if __name__ == "__main__":
    main()
