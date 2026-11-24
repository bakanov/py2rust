"""Transfer actual supervisor status/log files through all Python/Rust engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.process_supervisor import fixture, run, service
from corpus_checks.supervisor_fixture import build_fixture

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    helper = build_fixture(directory)
    first = fixture(directory / "first", helper)
    a = service(first.root, helper, "binary")
    a["argv"][4:6] = ["8193", "101"]
    b = service(first.root, helper, "failed", restarts=0)
    b["argv"][7] = "99"
    first.config["services"] = [a, b]
    first.save()
    doc = run(writer, first, 1)
    assert [row["state"] for row in doc["services"]] == ["exited", "failed"]
    first_files = snapshot(first.state)
    second = fixture(directory / "second", helper)
    rows = []
    for name, filename in [("binary", "binary.stdout"), ("report", "status.json")]:
        row = service(second.root, helper, name, "copy", restarts=0)
        row["argv"].append(str(first.state / filename))
        rows.append(row)
    second.config["services"] = rows
    second.save()
    run(replayer, second)
    assert (second.state / "binary.stdout").read_bytes() == first_files["binary.stdout"]
    assert (second.state / "report.stdout").read_bytes() == first_files["status.json"]
    second_files = snapshot(second.state)
    third = fixture(directory / "third", helper)
    rows = []
    for name, filename in [
        ("binary", "binary.stdout"),
        ("original_report", "report.stdout"),
        ("next_report", "status.json"),
    ]:
        row = service(third.root, helper, name, "copy", restarts=0)
        row["argv"].append(str(second.state / filename))
        rows.append(row)
    third.config["services"] = rows
    third.save()
    run(reader, third)
    assert (third.state / "binary.stdout").read_bytes() == first_files["binary.stdout"]
    assert (third.state / "original_report.stdout").read_bytes() == first_files["status.json"]
    assert (third.state / "next_report.stdout").read_bytes() == second_files["status.json"]
    assert snapshot(first.state) == first_files and snapshot(second.state) == second_files
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_status_and_binary_log_files_consumed": True,
        "failed_service_report_preserved": True,
        "binary_sha256": hashlib.sha256(first_files["binary.stdout"]).hexdigest(),
        "original_status_sha256": hashlib.sha256(first_files["status.json"]).hexdigest(),
        "replayer_status_sha256": hashlib.sha256(second_files["status.json"]).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "093")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "093/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"093": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "process-supervisor"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "093/corpus_093")], "rust"),
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
                print(name + " status/log exchange: passed", flush=True)
    # Raw reports retain measured times; each transfer checks exact original bytes locally.
    assert len({row["binary_sha256"] for row in observations}) == 1
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
