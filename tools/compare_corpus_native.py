"""Compare complete checked jobs with independently handwritten Rust baselines.

Missing baselines are an error, never silently treated as a passing 2x gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile

from assess_corpus_speed import ROOT, SELECTED, digest
from corpus_speed_workloads import TimedApplication, job
from py2rust.compiler.project_output import application_source_text

BASELINES = {
    "041": "csv_json.rs",
    "044": "csv_join.rs",
    "068": "huffman.rs",
    "071": "access_log.rs",
    "078": "regex_rewrite.rs",
    "096": "resolver.rs",
    "105": "telemetry.rs",
    "100": "text_diff.rs",
    "104": "circuits.rs",
    "110": "population.rs",
    "111": "png.rs",
    "112": "wav.rs",
    "117": "terminal_dashboard.rs",
    "114": "ppm.rs",
    "113": "bmp.rs",
    "118": "zip.rs",
    "115": "atlas.rs",
    "079": "automation.rs",
    "080": "highlighter.rs",
    "077": "source_outline.rs",
    "109": "warehouse.rs",
    "095": "code_metrics.rs",
    "061": "route_planner.rs",
    "065": "terrain_routes.rs",
    "082": "cron_explorer.rs",
    "088": "scheduler.rs",
    "089": "log_redactor.rs",
    "045": "json_patch.rs",
    "051": "lru_cache.rs",
    "055": "autocomplete.rs",
}
NATIVE = ROOT / "benchmarks/corpus_speed_20/native"


def files_hash(root: Path) -> str:
    result = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        result.update(str(path.relative_to(root)).encode())
        result.update(path.read_bytes())
    return result.hexdigest()


def unmet_targets(report: dict) -> list[dict]:
    exempt = set(report.get("target_exemptions", []))
    return [row for row in report["rows"] if not row["target_met"] and row["id"] not in exempt]


def compare(
    generated: Path,
    output: Path,
    identifiers: list[str],
    repeats: int,
    before: Path | None = None,
    target_exemptions: tuple[str, ...] = (),
    large_target: float = 2.0,
) -> dict:
    if not math.isfinite(large_target) or large_target <= 0:
        raise ValueError("Large-workload target must be finite and positive")
    if set(target_exemptions) - set(identifiers):
        raise ValueError("Target exemptions must be included in --ids")
    missing = sorted(set(identifiers) - BASELINES.keys())
    if missing:
        raise ValueError("No handwritten baseline yet for: " + ", ".join(missing))
    if repeats < 3:
        raise ValueError("at least three repetitions are required")
    output.mkdir(parents=True, exist_ok=False)
    compiler_files = [
        p
        for p in (ROOT / "py2rust").rglob("*")
        if p.is_file() and p.suffix in {".py", ".rs", ".toml", ".lock", ".json"}
    ]
    compiler = digest(compiler_files)
    report = {
        "platform": platform.platform(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "repeats": repeats,
        "method": "Release executables; rotating order; one warmup; fresh jobs; independent oracles and equal complete file contents; compilation and checking excluded",
        "target": f"generated/native < 2.00 for small and < {large_target:.2f} for large non-exempt cases",
        "target_limits": {"small": 2.0, "large": large_target},
        "target_exemptions": sorted(set(target_exemptions)),
        "coverage": identifiers,
        "missing_from_selected_twenty": sorted(set(SELECTED) - set(identifiers)),
        "rows": [],
    }
    for identifier in identifiers:
        original = generated / identifier
        stamp = json.loads((original / "build.json").read_text())
        assert stamp["compiler_sha256"] == compiler, "generated compiler fingerprint is stale"
        assert stamp["source_sha256"] == digest(list((ROOT / "examples/corpus" / stamp["path"]).rglob("*.py")))
        assert stamp["binary_sha256"] == hashlib.sha256((original / "program").read_bytes()).hexdigest()
        project = output / identifier / "native"
        shutil.copytree(original / "rust", project)
        shutil.copyfile(NATIVE / BASELINES[identifier], project / "src/main.rs")
        native_sources = [BASELINES[identifier], "common.rs"]
        if identifier in {"041", "044"}:
            shutil.copyfile(NATIVE / "csv_codec.rs", project / "src/csv_codec.rs")
            native_sources.append("csv_codec.rs")
        shutil.copyfile(NATIVE / "common.rs", project / "src/common.rs")
        manifest = project / "Cargo.toml"
        manifest.write_text(manifest.read_text().replace(f"speed_{identifier}", f"native_{identifier}"))
        target = generated / "target"
        with (project.parent / "native-build.log").open("w") as log:
            subprocess.run(
                [
                    "cargo",
                    "build",
                    "--release",
                    "--locked",
                    "--offline",
                    "--manifest-path",
                    str(manifest),
                    "--bin",
                    f"native_{identifier}",
                ],
                env=dict(os.environ, CARGO_TARGET_DIR=str(target)),
                stdout=log,
                stderr=log,
                check=True,
            )
        native = project.parent / "native-program"
        shutil.copyfile(target / "release" / f"native_{identifier}", native)
        native.chmod(0o755)
        saved_generated = project.parent / "generated-program"
        shutil.copyfile(original / "program", saved_generated)
        saved_generated.chmod(0o755)
        (project.parent / "generated.rs").write_text(application_source_text(original / "rust"))
        binaries = {"generated": saved_generated, "native": native}
        before_stamp = None
        if before is not None:
            before_stamp = json.loads((before / identifier / "build.json").read_text())
            assert before_stamp["source_sha256"] == stamp["source_sha256"], "application source changed"
            saved_before = project.parent / "before-program"
            shutil.copyfile(before / identifier / "program", saved_before)
            saved_before.chmod(0o755)
            binaries["before"] = saved_before
            assert hashlib.sha256(saved_before.read_bytes()).hexdigest() == before_stamp["binary_sha256"]
        variants = ["csv-to-json", "json-to-csv"] if identifier == "041" else ["default"]
        for variant, size in [(variant, size) for variant in variants for size in ["small", "large"]]:
            samples: dict[str, list[dict]] = {engine: [] for engine in binaries}
            expected_input = expected_output = None
            for repetition in range(repeats + 1):
                order = list(binaries)
                offset = repetition % len(order)
                order = order[offset:] + order[:offset]
                for engine in order:
                    with tempfile.TemporaryDirectory(prefix=f"{identifier}-{size}-{engine}-", dir=output) as temporary:
                        root = Path(temporary) / "job"
                        if identifier == "041":
                            from corpus_additional_workloads import converter_job

                            verify, description, units = converter_job(root, size == "large", variant)
                        else:
                            verify, description, units = job(identifier, root, size == "large")
                        input_hash = files_hash(root)
                        if expected_input is None:
                            expected_input = input_hash
                        assert input_hash == expected_input, "inputs differ"
                        binary = binaries[engine]
                        app = TimedApplication([str(binary)], "rust")
                        verify(app)
                        assert len(app.observations) == 1
                        output_hash = files_hash(root)
                        if expected_output is None:
                            expected_output = output_hash
                        assert output_hash == expected_output, "generated/native complete file contents differ"
                        if repetition:
                            samples[engine].append(app.observations[0])
            medians = {engine: statistics.median(s["wall_ms"] for s in values) for engine, values in samples.items()}
            ratio = medians["generated"] / medians["native"]
            row = {
                "id": identifier,
                "size": size,
                "variant": variant,
                "description": description,
                "units": units,
                "build": stamp,
                "before_build": before_stamp,
                "native_sources_sha256": {
                    name: hashlib.sha256((NATIVE / name).read_bytes()).hexdigest() for name in native_sources
                },
                "native_binary_sha256": hashlib.sha256(native.read_bytes()).hexdigest(),
                "input_sha256": expected_input,
                "checked_files_sha256": expected_output,
                "samples": samples,
                "median_ms": medians,
                "generated_over_native": ratio,
                "target_limit": large_target if size == "large" else 2.0,
                "target_met": ratio < (large_target if size == "large" else 2.0),
            }
            report["rows"].append(row)
            (output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"{identifier} {variant} {size}: generated {medians['generated']:.2f} ms; handwritten {medians['native']:.2f} ms; {ratio:.2f}x",
                flush=True,
            )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--before", type=Path, help="optional preserved old generated build for rotating before/after/native runs"
    )
    parser.add_argument("--ids", nargs="+", default=SELECTED)
    parser.add_argument("--repeats", type=int, default=9)
    parser.add_argument("--check-target", action="store_true")
    parser.add_argument(
        "--large-target", type=float, default=2.0, help="strict large-workload ratio limit (default: 2)"
    )
    parser.add_argument(
        "--exempt-from-target",
        nargs="+",
        default=[],
        metavar="ID",
        help="explicitly accepted exceptions; still measure/check outputs and retain actual ratios",
    )
    args = parser.parse_args()
    report = compare(
        args.generated.resolve(),
        args.output.resolve(),
        args.ids,
        args.repeats,
        args.before.resolve() if args.before else None,
        tuple(args.exempt_from_target),
        args.large_target,
    )
    if args.check_target and unmet_targets(report):
        raise SystemExit("The requested size-specific targets are not met for non-exempt cases")
    return


if __name__ == "__main__":
    main()
