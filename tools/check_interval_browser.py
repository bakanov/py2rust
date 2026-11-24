"""Update and query actual interval snapshots across every Python/Rust engine combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.interval_browser import event, fixture, point, query, sample, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first_trace = [{"op": "PUT", "event": event("wide", -100, 100, "wide")}, query(99, 100), point(100)]
    second_trace = [
        {"op": "DELETE", "id": "wide"},
        {"op": "PUT", "event": event("outer", -1, 1, "shrunk")},
        {"op": "DELETE", "id": "old"},
        query(99, 100),
    ]
    third_trace = [
        {"op": "PUT", "event": event("new", -50, -40, "世界")},
        query(-45, -44),
        query(20, 21),
        point(10),
        {"op": "GET", "id": "empty"},
        query(0, 10, "STRASSE"),
    ]
    first = fixture(directory, "first", sample(), first_trace)
    success(writer, first)
    first_bytes = (first.output / "state.json").read_bytes()
    second = fixture(directory, "second", [], second_trace, state=str(first.output / "state.json"))
    middle = success(updater, second)
    assert middle[1][-1]["result"]["visited_nodes"] == 0
    second_bytes = (second.output / "state.json").read_bytes()
    third = fixture(directory, "third", [], third_trace, state=str(second.output / "state.json"))
    observed = success(reader, third)
    assert [row["id"] for row in observed[1][1]["result"]["hits"]] == ["new"]
    assert observed[1][2]["result"]["hits"] == []
    assert [row["id"] for row in observed[1][3]["result"]["hits"]] == ["b"]
    assert observed[1][4]["found"] and observed[1][4]["event"]["start_ms"] == observed[1][4]["event"]["end_ms"]
    whole = fixture(directory, "whole", sample(), first_trace + second_trace + third_trace)
    expected = success(reader, whole)
    assert observed[0] == expected[0]
    for name in ["state.json", "records.jsonl"]:
        assert (third.output / name).read_bytes() == (whole.output / name).read_bytes()
    events = b"".join((fix.output / "events.jsonl").read_bytes() for fix in [first, second, third])
    assert events == (whole.output / "events.jsonl").read_bytes()
    assert (first.output / "state.json").read_bytes() == first_bytes
    assert (second.output / "state.json").read_bytes() == second_bytes
    merged = fixture(
        directory,
        "merged",
        [event("new", 18, 19, "replacement")],
        [query(-45, -44), query(18, 19)],
        state=str(third.output / "state.json"),
    )
    final = success(writer, merged)
    assert final[2]["imported"] == {"read": 1, "added": 0, "replaced": 1}
    assert final[1][0]["result"]["count"] == 0
    assert any(row["id"] == "new" for row in final[1][1]["result"]["hits"])
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
        "events_sha256": hashlib.sha256(events).hexdigest(),
        "merged_sha256": hashlib.sha256((merged.output / "state.json").read_bytes()).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "059")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "059/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"059": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "interval-browser"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "059/corpus_059")], "rust"),
    ]
    observations = []
    for writer in apps:
        for updater in apps:
            for reader in apps:
                name = f"{writer.engine}-{updater.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, updater, reader, work))
                print(name + " interval import/update/query: passed", flush=True)
    for field in ["state_sha256", "events_sha256", "merged_sha256"]:
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
