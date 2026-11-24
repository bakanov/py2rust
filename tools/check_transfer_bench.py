"""Exercise eight controller/sender/receiver combinations and cross-engine report comparisons."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.transfer_bench import compare_fixture, fixture, run
from corpus_checks.transfer_fixture import case, comparison, digest, payload

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "098")
    current = fingerprint(program)
    result = json.loads((BUILD / "098/result.json").read_text())
    assert result["status"] == "verified" and result["fingerprint"] == current
    directory = BUILD / "transfer-bench"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"098": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "098/corpus_098")], "rust"),
    ]
    cases = [
        case("empty", 0, 0),
        case("fragmented", 257, 255, send_chunk=1, receive_chunk=3),
        case("block", 8192, 99, send_chunk=257, receive_chunk=509),
        case("capacity", 1048576, 17, send_chunk=65536, receive_chunk=16384, timeout_ms=5000),
    ]
    runs = []
    for controller in apps:
        for sender in apps:
            for receiver in apps:
                name = f"{controller.engine}-{sender.engine}-{receiver.engine}"
                root = directory / name
                if root.exists():
                    shutil.rmtree(root)
                report = run(controller, root, fixture(root, sender, receiver, cases, 2), timeout=30)
                assert len(report["runs"]) == 8 and all(row["status"] == "ok" for row in report["runs"])
                runs.append((controller, sender, receiver, root, report))
                print(name + " controller/sender/receiver: passed", flush=True)
    observations = []
    for index, (controller, sender, receiver, root, report) in enumerate(runs):
        reader = next(app for app in apps if app.engine != controller.engine)
        before = runs[(index + 1) % len(runs)][4]
        work = root / "compare"
        config = compare_fixture(work, before, report)
        actual = run(reader, work, config)
        assert actual["rows"] == comparison(before, report)
        assert all(row["status"] == "comparable" for row in actual["rows"])
        replay = json.loads((work / "output/replay.json").read_bytes())
        assert run(controller, work / "output", replay) == actual
        observations.append(
            {
                "controller": controller.engine,
                "sender": sender.engine,
                "receiver": receiver.engine,
                "comparison_reader": reader.engine,
                "verified_transfers": len(report["runs"]),
                "actual_reports_consumed_and_replayed": True,
                "independent_statistics_verified": True,
                "fixture_sha256": {row["id"]: digest(payload(row)) for row in cases},
                "comparison_sha256": digest((work / "output/report.json").read_bytes()),
            }
        )
        print(root.name + " report comparison/replay: passed", flush=True)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"098": current},
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
