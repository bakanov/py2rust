"""Eight mixed-engine CSV conversion/join/import pipelines using complete native projects."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_join import fixture as join_fixture
from corpus_checks.csv_join import run as join_run
from corpus_checks.csv_json import column, csv_rows, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, joiner: Application, reader: Application, work: Path) -> dict:
    columns = [column("key"), column("value")]
    left = [
        {"key": "a,世界", "value": "first\nrow"},
        {"key": "a,世界", "value": 'second "quoted"'},
        {"key": "missing", "value": "\\N"},
        {"key": "", "value": ""},
    ]
    right = [
        {"key": "a,世界", "value": "α"},
        {"key": "a,世界", "value": "😀\r\nline"},
        {"key": "", "value": "empty key"},
        {"key": "unused", "value": "not selected"},
    ]
    exports = []
    for side, records in [("left", left), ("right", right)]:
        fix = fixture(work, "export-" + side, "json-to-csv", columns, json.dumps(records, ensure_ascii=False).encode())
        run(writer, fix, records)
        exports.append((fix.output / "data.csv").read_bytes())
    joined = join_fixture(work, "joined")
    for side, data in zip(["left", "right"], exports):
        (joined.work / (side + ".csv")).write_bytes(data)
    report = join_run(joiner, joined)
    assert report["matched_pairs"] == 5 and report["output_rows"] == 6
    data = (joined.output / "joined.csv").read_bytes()
    imported = fixture(work, "import", "csv-to-json", [column("L"), column("R")], data)
    expected = [
        {"L": "first\nrow", "R": "α"},
        {"L": "first\nrow", "R": "😀\r\nline"},
        {"L": 'second "quoted"', "R": "α"},
        {"L": 'second "quoted"', "R": "😀\r\nline"},
        {"L": "\\N", "R": ""},
        {"L": "", "R": "empty key"},
    ]
    imported_report = run(reader, imported, expected)
    assert len(csv_rows(data.decode())) == 7
    return {
        "writer": writer.engine,
        "joiner": joiner.engine,
        "reader": reader.engine,
        "joined_rows": 6,
        "matched_pairs": 5,
        "csv_sha256": report["data_sha256"],
        "json_sha256": imported_report["data_sha256"],
        "complete_application_pipeline": True,
    }


def main() -> int:
    programs = {
        row["id"]: row
        for row in json.loads((CORPUS / "catalog.json").read_text())["programs"]
        if row["id"] in ["041", "044"]
    }
    fingerprints = {identifier: fingerprint(program) for identifier, program in programs.items()}
    for identifier, current in fingerprints.items():
        evidence = json.loads((BUILD / identifier / "result.json").read_text())
        assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "verify current corpus first"
    directory = BUILD / "csv-join"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        identifier: {
            "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
            "rust": Application([str(BUILD / identifier / ("corpus_" + identifier))], "rust"),
        }
        for identifier, program in programs.items()
    }
    observations = []
    for writer in apps["041"].values():
        for joiner in apps["044"].values():
            for reader in apps["041"].values():
                name = writer.engine + "-" + joiner.engine + "-" + reader.engine
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, joiner, reader, work))
                print(name + " conversion/join/import pipeline: passed", flush=True)
    assert len({row["csv_sha256"] for row in observations}) == len({row["json_sha256"] for row in observations}) == 1
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
