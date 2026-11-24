"""Pass actual binary stdout and stderr files through Python/Rust shell executions."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.command_shell import fixture, job, run
from corpus_checks.common import Application
from corpus_checks.process_fixture import build_fixture

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, transformer: Application, reader: Application, directory: Path) -> dict:
    helper = build_fixture(directory / "native-fixture")
    first = fixture(
        directory, "first", helper, [job("data", "process-fixture emit 262144 131072 | process-fixture copy")]
    )
    _report, original = run(writer, first)
    assert original["data.stdout"] == bytes(range(256)) * 1024
    assert original["data.0.stderr"] == b"e" * 131072
    second = fixture(
        directory,
        "second",
        helper,
        [
            job("upper", "process-fixture copy | process-fixture upper", str(first.output / "data.stdout")),
            job("errors", "process-fixture upper", str(first.output / "data.0.stderr")),
            job("status", "process-fixture exit 7 | process-fixture exit 0"),
        ],
    )
    report, transformed = run(transformer, second, 7)
    assert report["jobs"][-1]["stages"] == [7, 0]
    assert transformed["upper.stdout"] == original["data.stdout"].upper()
    assert transformed["errors.stdout"] == b"E" * 131072
    third = fixture(
        directory,
        "third",
        helper,
        [
            job("copy", "process-fixture copy", str(second.output / "upper.stdout")),
            job("literal", "process-fixture args '' 'quoted | pipe' '$HOME'", LABEL="世界"),
        ],
    )
    _report, final = run(reader, third)
    assert final["copy.stdout"] == transformed["upper.stdout"]
    assert final["literal.stdout"] == b"\n71756f746564207c2070697065\n24484f4d45\n"
    assert original == {path.name: path.read_bytes() for path in first.output.iterdir()}
    assert transformed == {path.name: path.read_bytes() for path in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "transformer": transformer.engine,
        "reader": reader.engine,
        "stdout_sha256": hashlib.sha256(original["data.stdout"]).hexdigest(),
        "transformed_sha256": hashlib.sha256(final["copy.stdout"]).hexdigest(),
        "actual_capture_paths": True,
        "binary_stdout_and_separate_stderr": True,
        "failed_stage_status_preserved": True,
        "previous_captures_unchanged": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "076")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "076/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"076": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "command-shell"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "076/corpus_076")], "rust"),
    ]
    observations = []
    for writer in apps:
        for transformer in apps:
            for reader in apps:
                name = f"{writer.engine}-{transformer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, transformer, reader, work))
                print(name + " binary pipelines, stderr captures and statuses: passed", flush=True)
    for field in ["stdout_sha256", "transformed_sha256"]:
        assert len({row[field] for row in observations}) == 1
    assert fingerprint(program) == current
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": fingerprints,
                "checker_sha256": checker_hash,
                "observations": observations,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
