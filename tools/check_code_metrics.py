"""Reconstruct actual exported source archives and compare browsers across eight engine combinations."""

import base64
import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.code_metrics import fixture, run
from corpus_checks.common import Application
from corpus_checks.metrics_fixture import FILES

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir()}


def restore(work: Path, exported: bytes) -> tuple[dict, dict[str, bytes]]:
    data = json.loads(exported)
    assert data["version"] == 1
    files = {row["path"]: base64.b64decode(row["data"], validate=True) for row in data["files"]}
    assert len(files) == len(data["files"])
    for path in files:
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
    config = fixture(work, files, data["package"])
    config["exclude"] = data["exclude"]
    config["thresholds"] = data["thresholds"]
    (work / "metrics-job.json").write_text(json.dumps(config) + "\n")
    return config, files


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = directory / "first"
    config = fixture(first)
    report = run(writer, first, config)
    original = snapshot(first / "inspection")
    second = directory / "second"
    replay_config, replay_files = restore(second, original["sources.json"])
    replay_report = run(replayer, second, replay_config, replay_files)
    copied = snapshot(second / "inspection")
    assert replay_report == report and copied == original
    third = directory / "third"
    final_config, final_files = restore(third, copied["sources.json"])
    final_report = run(reader, third, final_config, final_files)
    assert final_report == report and snapshot(third / "inspection") == original
    assert snapshot(first / "inspection") == original and snapshot(second / "inspection") == copied
    assert final_files == replay_files == FILES
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_source_archives_consumed": True,
        "all_html_json_and_source_bytes_identical": True,
        "report_sha256": hashlib.sha256(original["report.json"]).hexdigest(),
        "archive_sha256": hashlib.sha256(original["sources.json"]).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "095")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "095/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"095": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "code-metrics"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "095/corpus_095")], "rust"),
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
                print(name + " source archive/browser exchange: passed", flush=True)
    assert len({row["report_sha256"] for row in observations}) == 1
    assert len({row["archive_sha256"] for row in observations}) == 1
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
