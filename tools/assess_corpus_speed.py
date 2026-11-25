"""Release-build and benchmark selected complete corpus applications."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from py2rust.compiler.project import create_project

ROOT = Path(__file__).resolve().parents[1]
SELECTED = [
    "068",
    "071",
    "077",
    "078",
    "079",
    "080",
    "095",
    "096",
    "100",
    "104",
    "105",
    "109",
    "110",
    "111",
    "112",
    "113",
    "114",
    "115",
    "117",
    "118",
]


# Fixed follow-up selection; keep the original optimization set separate.
ADDITIONAL = ["041", "044", "045", "051", "055", "061", "065", "082", "088", "089"]


def digest(files: list[Path]) -> str:
    result = hashlib.sha256()
    for path in sorted(files):
        result.update(str(path.relative_to(ROOT)).encode())
        result.update(path.read_bytes())
    return result.hexdigest()


def build(output: Path, identifiers: list[str]) -> None:
    catalog = json.loads((ROOT / "examples/corpus/catalog.json").read_text())
    if isinstance(catalog, dict):
        catalog = catalog["programs"]
    programs = {row["id"]: row for row in catalog}
    compiler_files = [
        path
        for path in (ROOT / "py2rust").rglob("*")
        if path.is_file() and path.suffix in {".py", ".rs", ".toml", ".lock", ".json"}
    ]
    compiler_hash = digest(compiler_files)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for identifier in identifiers:
        program = programs[identifier]
        source = ROOT / "examples/corpus" / program["path"]
        work = output / identifier
        work.mkdir(exist_ok=True)
        source_hash = digest(list(source.rglob("*.py")))
        stamp = {"compiler_sha256": compiler_hash, "source_sha256": source_hash}
        record = work / "build.json"
        if record.exists():
            previous = json.loads(record.read_text())
            if (
                all(previous.get(key) == value for key, value in stamp.items())
                and previous.get("status") == "built"
                and (work / "program").exists()
                and hashlib.sha256((work / "program").read_bytes()).hexdigest() == previous.get("binary_sha256")
            ):
                rows.append(previous)
                print(f"{identifier}: reusing matching release build", flush=True)
                continue
        row = dict(
            stamp, id=identifier, title=program["title"], path=program["path"], check=program["check"], status="failed"
        )
        try:
            started = time.perf_counter()
            project = create_project(source, work / "rust", binary_name=f"speed_{identifier}")
            linked = {module.path.resolve() for module in project.modules.values() if module.tree is not None}
            assert set(path.resolve() for path in source.rglob("*.py")) <= linked
            with (work / "build.log").open("w") as log:
                subprocess.run(
                    [
                        "cargo",
                        "build",
                        "--release",
                        "--locked",
                        "--offline",
                        "--manifest-path",
                        str(work / "rust/Cargo.toml"),
                        "--bin",
                        f"speed_{identifier}",
                    ],
                    env=dict(os.environ, CARGO_TARGET_DIR=str(output / "target")),
                    stdout=log,
                    stderr=log,
                    check=True,
                    timeout=360,
                )
            shutil.copyfile(output / "target/release" / f"speed_{identifier}", work / "program")
            (work / "program").chmod(0o755)
            row.update(
                status="built",
                build_seconds=time.perf_counter() - started,
                binary_sha256=hashlib.sha256((work / "program").read_bytes()).hexdigest(),
                generated_sha256=hashlib.sha256((work / "rust/src/main.rs").read_bytes()).hexdigest(),
                generated_bytes=(work / "rust/src/main.rs").stat().st_size,
            )
            print(f"{identifier}: release built in {row['build_seconds']:.1f}s", flush=True)
        except Exception as error:
            import traceback

            row["error"] = traceback.format_exc()
            print(f"{identifier}: build failed: {error}", flush=True)
        record.write_text(json.dumps(row, indent=2) + "\n")
        rows.append(row)
    (output / "builds.json").write_text(json.dumps(rows, indent=2) + "\n")
    return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", default=SELECTED)
    parser.add_argument("--phase", choices=["build", "measure", "trace", "all"], default="all")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.phase in {"build", "all"}:
        build(args.output.resolve(), args.ids)
        if any(
            json.loads((args.output / identifier / "build.json").read_text())["status"] != "built"
            for identifier in args.ids
        ):
            raise SystemExit("Some release builds failed; see the per-application build logs")
    if args.phase in {"measure", "all"}:
        from corpus_speed_workloads import measure

        measure(args.output.resolve(), args.ids, args.repeats)
        if any(
            json.loads((args.output / identifier / f"{size}-measurements.json").read_text())["status"] != "measured"
            for identifier in args.ids
            for size in ["small", "large"]
        ):
            raise SystemExit("Some workloads failed; see the per-application measurement files")
    if args.phase == "trace":
        from corpus_speed_workloads import trace

        trace(args.output.resolve(), args.ids)
    return


if __name__ == "__main__":
    main()
