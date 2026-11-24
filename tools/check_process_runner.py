"""Exchange actual failed-suite reports and binary captures across Python and native Rust."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.process_runner import case, fixture, outcome, run
from corpus_checks.runner_fixture import build_runner_fixture

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    helper = build_runner_fixture(directory)
    payload = bytes(range(256)) * 13 + "portable 世界".encode()
    first = fixture(
        directory / "first", helper, [case("binary", ["copy"], payload, payload), case("failed-test", ["exit", "7"])]
    )
    first_report = run(writer, first, [(outcome(), payload, b""), (outcome(code=7), b"", b"")])
    assert first_report["status"] == "failed"
    first_files = {p.name: p.read_bytes() for p in first.output.iterdir()}
    saved_capture = (first.output / "binary.stdout").read_bytes()
    saved_report = (first.output / "report.json").read_bytes()
    second = fixture(
        directory / "second",
        helper,
        [
            case("copied-capture", ["copy"], saved_capture, saved_capture),
            case("copied-report", ["copy"], saved_report, saved_report),
        ],
    )
    run(replayer, second, [(outcome(), saved_capture, b""), (outcome(), saved_report, b"")])
    second_files = {p.name: p.read_bytes() for p in second.output.iterdir()}
    propagated = (second.output / "copied-report.stdout").read_bytes()
    assert propagated == saved_report
    second_report = (second.output / "report.json").read_bytes()
    third = fixture(
        directory / "third",
        helper,
        [
            case("report-chain", ["copy"], second_report, second_report),
            case("original-capture", ["copy"], (second.output / "copied-capture.stdout").read_bytes(), payload),
        ],
    )
    run(reader, third, [(outcome(), second_report, b""), (outcome(), payload, b"")])
    assert first_files == {p.name: p.read_bytes() for p in first.output.iterdir()}
    assert second_files == {p.name: p.read_bytes() for p in second.output.iterdir()}
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_report_and_capture_files_consumed": True,
        "failed_suite_report_preserved": True,
        "binary_capture_sha256": hashlib.sha256(payload).hexdigest(),
        "initial_report_sha256": hashlib.sha256(saved_report).hexdigest(),
        "final_report_sha256": hashlib.sha256((third.output / "report.json").read_bytes()).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "091")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "091/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"091": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "process-runner"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "091/corpus_091")], "rust"),
    ]
    observations = []
    for writer in apps:
        for replayer in apps:
            for reader in apps:
                name = f"{writer.engine}-{replayer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, replayer, reader, work))
                print(name + " report/capture exchange: passed", flush=True)
    assert len({(row["initial_report_sha256"], row["final_report_sha256"]) for row in observations}) == 1
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
