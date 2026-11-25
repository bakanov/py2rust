"""Compare immediate split consumers against native Rust with checked outputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

from py2rust.compiler.project import create_project

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workload", choices=["text_consumers", "map_counter"], default="text_consumers")
    args = parser.parse_args()
    source_dir = ROOT / "benchmarks" / args.workload
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    project = output / "generated"
    create_project(source_dir, project, binary_name="text-generated")
    (project / "src/bin").mkdir()
    shutil.copyfile(source_dir / "native.rs", project / "src/bin/text-native.rs")
    with (output / "build.log").open("w") as log:
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "--locked",
                "--offline",
                "--bins",
                "--manifest-path",
                str(project / "Cargo.toml"),
            ],
            env=dict(os.environ, CARGO_TARGET_DIR=str(output / "target")),
            stdout=log,
            stderr=log,
            check=True,
        )
    payload = "/api/messages?" + "".join(f"field-{i % 127}-世界?value\n" for i in range(20000))
    path = output / "input.txt"
    path.write_text(payload)
    expected = {"prefix": len("/api/messages") * 100, "count": 20001 * 100, "iterate": (len(payload) - 20000) * 10}
    if args.workload == "map_counter":
        expected = {"counter": (len(payload) - 20000) * 10}
    rows = []
    for case, answer in expected.items():
        env = dict(os.environ, TEXT_INPUT=str(path), TEXT_CASE=case, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
        reference = subprocess.check_output([sys.executable, str(source_dir / "main.py")], env=env, text=True)
        assert int(reference) == answer
        samples = {name: [] for name in ("generated", "native")}
        for repeat in range(8):
            for name in (["generated", "native"] if repeat % 2 else ["native", "generated"]):
                start = time.perf_counter_ns()
                result = subprocess.check_output([str(output / "target/release" / f"text-{name}")], env=env, text=True)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                assert int(result) == answer
                if repeat:
                    samples[name].append(elapsed)
        medians = {name: statistics.median(values) for name, values in samples.items()}
        rows.append(
            {
                "case": case,
                "expected": answer,
                "samples_ms": samples,
                "median_ms": medians,
                "generated_over_native": medians["generated"] / medians["native"],
            }
        )
        print(
            f"{case}: generated {medians['generated']:.2f} ms; native {medians['native']:.2f} ms; "
            f"ratio {medians['generated'] / medians['native']:.2f}x",
            flush=True,
        )
    sources = [source_dir / "main.py", source_dir / "native.rs", Path(__file__)]
    report = {
        "platform": platform.platform(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "generated_sha256": hashlib.sha256((project / "src/main.rs").read_bytes()).hexdigest(),
        "rows": rows,
    }
    (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    return


if __name__ == "__main__":
    main()
