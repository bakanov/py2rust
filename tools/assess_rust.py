"""Reproduce generated-code inspection, release timing and separate allocation diagnostics."""

# ruff: noqa: EXE002, PLR1711 - exFAT modes; explicit returns required
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from py2rust.compiler.project import create_project
from py2rust.compiler.project_output import application_source_text
from py2rust.compiler.service import create_service_project

ROOT = Path(__file__).resolve().parents[1]


def command(args: list[str], env: dict[str, str], log: Path) -> None:
    with log.open("w") as stream:
        subprocess.run(args, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
    return


def application_diagnostic(span: dict) -> bool:
    name = span["file_name"].replace("\\", "/")
    application_path = name.startswith("src/") or "/src/" in name
    native_path = name.startswith("src/native/") or "/src/native/" in name
    return span["is_primary"] and application_path and not native_path and name.endswith(".rs")


def observe(binary: Path, case: str, engine: str, size: int, rounds: int, repeats: int) -> dict:
    return json.loads(
        subprocess.check_output([str(binary), case, engine, str(size), str(rounds), str(repeats)], text=True)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh artifact directory on a Linux filesystem")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, CARGO_TARGET_DIR=str(out / "target"), CARGO_PROFILE_DEV_DEBUG="0", CARGO_INCREMENTAL="0")
    fixtures = ROOT / "benchmarks/rust_quality"
    source = (fixtures / "kernels.py").read_text()
    project = out / "kernels"
    create_service_project(source, project)
    generated = project / "src/main.rs"
    original = generated.read_text()
    (out / "kernels-generated.rs").write_text(original)
    generated.write_text(
        original.replace("fn main()", "fn generated_entry()") + "\n" + (fixtures / "harness.rs").read_text()
    )
    manifest = project / "Cargo.toml"
    manifest.write_text(manifest.read_text() + "\n[features]\nalloc-metrics = []\n")
    base = ["cargo", "build", "--release", "--locked", "--offline", "--manifest-path", str(manifest)]
    command(base, env, out / "release-build.log")
    binary = out / "timing"
    shutil.copy2(out / "target/release/py2rust-service", binary)
    command(base + ["--features", "alloc-metrics"], env, out / "allocation-build.log")
    counted = out / "allocations"
    shutil.copy2(out / "target/release/py2rust-service", counted)
    spec = importlib.util.spec_from_file_location("quality_kernels", fixtures / "kernels.py")
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    rows = []
    for case, sizes, rounds in [
        ("bytes", [65536, 1048576], 128),
        ("list", [1024, 32768], 32),
        ("json", [32, 1024], 1000),
        ("text", [1000, 10000], 1),
        ("arithmetic", [10000, 100000], 1),
    ]:
        for size in sizes:
            if case == "bytes":
                expected = reference.read_payload(bytes([42]) * size, rounds)
            elif case == "list":
                expected = reference.sum_values([i % 101 for i in range(size)], rounds)
            elif case == "json":
                expected = reference.route(
                    {"route": "/messages/世界", **{f"key{i}": "x" * 64 for i in range(size)}}, rounds
                )
            elif case == "text":
                expected = len(reference.build_text(size))
            else:
                expected = reference.arithmetic(size)
            result = {"case": case, "size": size, "rounds": rounds, "expected": expected}
            samples = {"generated": [], "native": []}
            repeats = {}
            for engine in samples:
                warm = observe(binary, case, engine, size, rounds, 1)
                assert warm["answer"] == expected
                repeats[engine] = max(1, min(100000, int(20_000_000 / max(warm["ns"], 1))))
                allocation = observe(counted, case, engine, size, rounds, 1)
                assert allocation["answer"] == expected
                result[engine + "_allocation_diagnostic"] = {
                    k: allocation[k] for k in ["allocations", "allocated_bytes"]
                }
            for sample in range(7):
                for engine in (["generated", "native"] if sample % 2 == 0 else ["native", "generated"]):
                    value = observe(binary, case, engine, size, rounds, repeats[engine])
                    assert value["answer"] == expected
                    samples[engine].append(value["ns"] / repeats[engine])
            for engine, values in samples.items():
                result[engine] = {
                    "samples_ns": values,
                    "median_ns": statistics.median(values),
                    "repeats": repeats[engine],
                }
            result["ratio"] = result["generated"]["median_ns"] / result["native"]["median_ns"]
            rows.append(result)
            print(case, size, "ratio", round(result["ratio"], 2), flush=True)
    inspections = []
    for name, path in [
        ("chat", ROOT / "examples/telegram"),
        ("traffic", ROOT / "examples/corpus/120_traffic_replayer"),
        ("gzip", ROOT / "examples/corpus/119_gzip_archiver"),
    ]:
        destination = out / name
        create_project(path, destination, binary_name="quality_" + name)
        code = application_source_text(destination)
        log = out / (name + "-clippy.jsonl")
        command(
            [
                "cargo",
                "clippy",
                "--locked",
                "--offline",
                "--manifest-path",
                str(destination / "Cargo.toml"),
                "--bin",
                "quality_" + name,
                "--message-format=json",
                "--",
                "--force-warn",
                "clippy::all",
                "--force-warn",
                "clippy::pedantic",
                "--force-warn",
                "unused_mut",
                "--force-warn",
                "unused_parens",
            ],
            env,
            log,
        )
        warnings = collections.Counter()
        for line in log.read_text().splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("reason") != "compiler-message":
                continue
            message = item["message"]
            if message["level"] == "warning" and any(application_diagnostic(s) for s in message["spans"]):
                warnings[(message.get("code") or {}).get("code", "unknown")] += 1
        inspections.append(
            {
                "project": name,
                "python_lines": sum(
                    len(p.read_text().splitlines()) for p in path.rglob("*.py") if "tools" not in p.parts
                ),
                "rust_lines": len(code.splitlines()),
                "clone_calls": code.count(".clone()"),
                "functions": len(re.findall(r"^(?:pub\(crate\) )?fn ", code, re.MULTILINE)),
                "clippy_generated_warnings": dict(warnings),
            }
        )
    report = {
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "platform": platform.platform(),
        "timestamp_unix": time.time(),
        "timings": rows,
        "inspections": inspections,
        "notes": [
            "Timing executable has no counting allocator. Allocation diagnostics use a separate instrumented build and can affect optimization.",
            "Setup, input construction and process startup excluded; function input cloning included as generated calling-convention cost.",
            "Seven alternating-order samples after warmup, adaptive batch size, black_box barriers and Python-reference result checks.",
            "Checked i64 arithmetic and Unicode character counts preserved in native baselines. Inputs are valid; these are kernels, not end-to-end service throughput.",
            "Allocated bytes are cumulative requested allocation/reallocation sizes, not RSS or peak live memory.",
        ],
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Assessment:", out / "results.json", flush=True)
    return


if __name__ == "__main__":
    main()
