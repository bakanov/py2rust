"""Filter complete application logs, then analyze events across all four Python/Rust pairs."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks import event_log, jsonl_transform
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(transformer: Application, checker: Application, work: Path) -> dict:
    rows = [
        event_log.event(1, "orders", data={"name": "Ada 世界", "value": 1}),
        event_log.event(3, "orders", before="active", after="paused", data=None),
        event_log.event(2, "orders", before="paused", data={"late": True}),
        event_log.event(1, "orders", data={"name": "Ada 世界", "value": 1}),
        event_log.event(1, "orders", data={"name": "Ada 世界", "value": 1.0}),
        event_log.event(4, "orders", sequence=2, data=None),
        event_log.event(5, "orders", before="active", after="closed", data=None),
        event_log.event(6, "orders", before="new", after="closed", data={"reason": "invalid edge"}),
        event_log.event(1, "notes", time="2026-01-01T03:00:07+03:00", data=["😀", -0.0]),
        event_log.event(2, "notes", sequence=True, data=None),
    ]
    raw = (
        b'{"kind":"debug","text":"starting"}\n'
        + event_log.encoded([{**row, "kind": "event", "extra": "discard"} for row in rows], b"\r\n")
        + b"broken\xff JSON\n"
        + b'{"kind":"metric","count":12}\n'
        + b'{"kind":"event","id":"missing-fields"}'
    )
    producer = jsonl_transform.fixture(
        work,
        "filter",
        raw,
        where={"kind": "event"},
        select=[*event_log.REQUIRED, "data"],
        max_line_bytes=4096,
    )
    filtered = jsonl_transform.complete(transformer, producer)
    assert (filtered["accepted"], filtered["filtered"], filtered["rejected"]) == (10, 2, 2)
    accepted = producer.root / "accepted.jsonl"
    unchanged = jsonl_transform.snapshot(producer.root)
    # The reference has its own bytes; the application reads the producer's actual output path.
    consumer = event_log.fixture(work, "analyze", accepted.read_bytes(), input=str(accepted))
    report = event_log.run(checker, consumer)
    assert jsonl_transform.snapshot(producer.root) == unchanged
    assert report["records"] == 10 and report["checked"] == 6
    assert report["streams"]["orders"]["missing"] == [{"first": 4, "last": 4}]
    assert report["issue_counts"] == {
        "sequence_gap": 2,
        "sequence_out_of_order": 1,
        "stream_time_regression": 1,
        "global_time_regression": 1,
        "duplicate_id": 1,
        "conflicting_id": 1,
        "duplicate_sequence": 1,
        "state_mismatch": 1,
        "invalid_transition": 1,
        "invalid_record": 1,
    }
    return {
        "transformer": transformer.engine,
        "checker": checker.engine,
        "accepted": filtered["accepted"],
        "filtered": filtered["filtered"],
        "quarantined": filtered["rejected"],
        "checked": report["checked"],
        "issue_counts": report["issue_counts"],
        "accepted_sha256": jsonl_transform.hashed(accepted),
        "report_sha256": hashlib.sha256(canonical(report).encode()).hexdigest(),
        "text_sha256": jsonl_transform.hashed(consumer.output / "report.txt"),
    }


def main() -> int:
    programs = {
        row["id"]: row
        for row in json.loads((CORPUS / "catalog.json").read_text())["programs"]
        if row["id"] in ["043", "046"]
    }
    fingerprints = {key: fingerprint(program) for key, program in programs.items()}
    apps = {}
    for key, program in programs.items():
        evidence = json.loads((BUILD / key / "result.json").read_text())
        assert evidence["status"] == "verified" and evidence["fingerprint"] == fingerprints[key]
        apps[key] = [
            Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
            Application([str(BUILD / key / ("corpus_" + key))], "rust"),
        ]
    directory = BUILD / "event-log"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    observations = []
    for transformer in apps["043"]:
        for checker in apps["046"]:
            name = transformer.engine + "-" + checker.engine
            work = directory / name
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(transformer, checker, work))
            print(name + " filter/analyze: passed", flush=True)
    for key in ["accepted_sha256", "report_sha256", "text_sha256"]:
        assert len({row[key] for row in observations}) == 1
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
