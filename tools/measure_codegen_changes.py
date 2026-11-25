"""Interleave preserved before/after executables and native Rust under the same workload."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--workload", choices=["text", "counter", "access-log"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    before, after = args.before.resolve(), args.after.resolve()
    prefix = "access-log" if args.workload == "access-log" else "text"
    binaries = {
        "before": before / f"target/release/{prefix}-generated",
        "after": after / f"target/release/{prefix}-generated",
        "native": after / f"target/release/{prefix}-native",
    }
    cases = (
        ["10000", "100000"]
        if args.workload == "access-log"
        else (["counter"] if args.workload == "counter" else ["prefix", "count", "iterate"])
    )
    rows = []
    for case in cases:
        filename = f"events-{case}.jsonl" if args.workload == "access-log" else "input.txt"
        path = after / filename
        assert path.read_bytes() == (before / filename).read_bytes(), "inputs changed between builds"
        env = dict(os.environ)
        env.update(
            {"ACCESS_LOG": str(path)} if args.workload == "access-log" else {"TEXT_INPUT": str(path), "TEXT_CASE": case}
        )
        expected = json.loads(subprocess.check_output([str(binaries["native"])], env=env, text=True))
        samples = {name: [] for name in binaries}
        names = list(binaries)
        for repeat in range(10):
            # Warm each binary, then rotate execution order to spread scheduler/cache bias.
            order = names[repeat % 3 :] + names[: repeat % 3]
            for name in order:
                start = time.perf_counter_ns()
                result = subprocess.check_output([str(binaries[name])], env=env, text=True)
                elapsed = (time.perf_counter_ns() - start) / 1e6
                assert json.loads(result) == expected, (case, name)
                if repeat:
                    samples[name].append(elapsed)
        medians = {name: statistics.median(values) for name, values in samples.items()}
        row = {
            "case": case,
            "samples_ms": samples,
            "median_ms": medians,
            "speedup": medians["before"] / medians["after"],
            "after_over_native": medians["after"] / medians["native"],
        }
        rows.append(row)
        print(
            f"{case}: {medians['before']:.2f} → {medians['after']:.2f} ms; "
            f"{row['speedup']:.2f}x improvement; {row['after_over_native']:.2f}x native",
            flush=True,
        )
    report = {
        "workload": args.workload,
        "platform": platform.platform(),
        "cpu": next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            "",
        ),
        "method": "9 measured runs per executable; rotating before/after/native order; one warmup; process startup, warm file reads and stdout included; compile excluded",
        "generated_sha256": {
            name: hashlib.sha256((path / "generated/src/main.rs").read_bytes()).hexdigest()
            for name, path in [("before", before), ("after", after)]
        },
        "binary_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in binaries.items()},
        "rows": rows,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return


if __name__ == "__main__":
    main()
