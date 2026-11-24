"""Exchange real replay documents and embedded reports across all three-engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint, reference_command
from corpus_checks.common import Application
from corpus_checks.rust_imports import case, fixture, run, save

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir()}


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    rows = [
        case("narrow", {"value": 256}, name="range_error"),
        case("bytes", {"data": "AP8BAg=="}, name="binary"),
        case("unicode", {"text": "世界🙂e\u0301"}, name="unicode"),
        case("nested", {"mode": "inf"}, name="nonfinite"),
        case("accept", {"text": "deny"}, name="result_error"),
        case("add", {"left": 2, "right": 3}, {"kind": "value", "value": 99}, "wrong_expectation"),
        case("roundtrip", {"value": {"items": [1, True, None]}}, name="json"),
    ]
    first = directory / "first"
    config = fixture(first, rows)
    report = run(writer, first, config, 1)
    assert report["summary"]["failed"] == 1
    original = snapshot(first / "inspection")
    second = directory / "second"
    second.mkdir()
    # Consume the actual saved file without rebuilding its cases in the test harness.
    (second / "imports-job.json").write_bytes(original["replay.json"])
    config = json.loads(original["replay.json"])
    replay = run(replayer, second, config)
    assert replay["summary"]["failed"] == 0 and replay["summary"]["native_errors"] == 3
    exported = snapshot(second / "replayed")
    third = directory / "third"
    third.mkdir()
    (third / "imports-job.json").write_bytes(exported["replay.json"])
    run(reader, third, json.loads(exported["replay.json"]))
    # A separate native Json round trip consumes the actual first report's case values.
    fourth = directory / "reader-json"
    compact = {key: report[key] for key in ["summary", "error_codes", "operations", "source_sha256"]}
    fixture(fourth, [case("roundtrip", {"value": compact}, {"kind": "value", "value": compact}, "read_report")])
    report_config = json.loads((fourth / "imports-job.json").read_bytes())
    save(fourth, report_config)
    run(reader, fourth, report_config)
    assert snapshot(first / "inspection") == original and snapshot(second / "replayed") == exported
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_replay_files_consumed": True,
        "saved_report_json_roundtripped": True,
        "intentional_mismatch_corrected_by_reference_export": True,
        "original_report_sha256": hashlib.sha256(original["report.json"]).hexdigest(),
        "replay_report_sha256": hashlib.sha256(exported["report.json"]).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "094")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "094/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"094": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "rust-imports"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [Application(reference_command(program), "python"), Application([str(BUILD / "094/corpus_094")], "rust")]
    observations = []
    for writer in apps:
        for replayer in apps:
            for reader in apps:
                name = f"{writer.engine}-{replayer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, replayer, reader, work))
                print(name + " replay/report exchange: passed", flush=True)
    assert len({row["original_report_sha256"] for row in observations}) == 1
    assert len({row["replay_report_sha256"] for row in observations}) == 1
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
