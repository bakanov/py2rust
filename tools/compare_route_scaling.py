"""Check route-planner scaling at five sizes using preserved matched comparison binaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import tempfile

from assess_corpus_speed import ROOT, digest
from compare_corpus_native import files_hash
from corpus_additional_workloads import route_job
from corpus_speed_workloads import TimedApplication


def compare(comparison: Path, output: Path, repeats: int) -> dict:
    if repeats < 3:
        raise ValueError("at least three repetitions required")
    report = json.loads((comparison / "results.json").read_text())
    row = next(row for row in report["rows"] if row["id"] == "061")
    compiler = digest(
        [
            p
            for p in (ROOT / "py2rust").rglob("*")
            if p.is_file() and p.suffix in {".py", ".rs", ".toml", ".lock", ".json"}
        ]
    )
    assert compiler == row["build"]["compiler_sha256"]
    assert row["build"]["source_sha256"] == row["before_build"]["source_sha256"]
    assert (
        digest(list((ROOT / "examples/corpus" / row["build"]["path"]).rglob("*.py"))) == row["build"]["source_sha256"]
    )
    hashes = {
        "generated": row["build"]["binary_sha256"],
        "before": row["before_build"]["binary_sha256"],
        "native": row["native_binary_sha256"],
    }
    binaries = {engine: comparison / "061" / f"{engine}-program" for engine in hashes}
    for engine, path in binaries.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes[engine]
    output.mkdir(parents=True, exist_ok=False)
    result = {
        "compiler_sha256": compiler,
        "source_sha256": row["build"]["source_sha256"],
        "binary_sha256": hashes,
        "repeats": repeats,
        "method": "rotating old/generated/native order after warmup, fresh graph/query jobs, independent oracle and complete output equality; startup and durable output included",
        "rows": [],
    }
    for count in [12, 25, 50, 75, 100]:
        samples = {engine: [] for engine in binaries}
        expected_input = expected_output = None
        for repetition in range(repeats + 1):
            order = list(binaries)
            offset = repetition % len(order)
            for engine in order[offset:] + order[:offset]:
                with tempfile.TemporaryDirectory(dir=output, prefix=f"jobs-{count}-{engine}-") as directory:
                    root = Path(directory) / "job"
                    run, description, queries = route_job(root, False, count=count)
                    input_hash = files_hash(root)
                    if expected_input is None:
                        expected_input = input_hash
                    assert input_hash == expected_input
                    app = TimedApplication([str(binaries[engine])], "rust")
                    run(app)
                    assert len(app.observations) == 1
                    output_hash = files_hash(root)
                    if expected_output is None:
                        expected_output = output_hash
                    assert output_hash == expected_output
                    if repetition:
                        samples[engine].append(app.observations[0])
        medians = {
            engine: statistics.median(sample["wall_ms"] for sample in values) for engine, values in samples.items()
        }
        result["rows"].append(
            {
                "vertices": count,
                "queries": queries,
                "description": description,
                "input_sha256": expected_input,
                "output_sha256": expected_output,
                "samples": samples,
                "median_ms": medians,
                "generated_over_native": medians["generated"] / medians["native"],
            }
        )
        (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"{count} vertices: old {medians['before']:.2f} ms; new {medians['generated']:.2f} ms; native {medians['native']:.2f} ms",
            flush=True,
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=9)
    args = parser.parse_args()
    compare(args.comparison.resolve(), args.output.resolve(), args.repeats)
    return


if __name__ == "__main__":
    main()
