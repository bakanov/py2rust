"""Round-trip typed records through CSV across all Python/native engine pairs."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import column, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, reader: Application, work: Path) -> dict:
    columns = [
        column("name", nullable=True),
        column("count", "integer"),
        column("ratio", "number"),
        column("active", "boolean"),
        column("metadata", "json", nullable=True),
    ]
    rows = [
        {
            "name": 'Hello, 世界\r\n"quoted"',
            "count": -(2**63),
            "ratio": -0.0,
            "active": True,
            "metadata": [1, None, "😀"],
        },
        {"name": None, "count": 2**63 - 1, "ratio": 1.25e-7, "active": False, "metadata": {"note": "\\N", "nul": "\0"}},
        {"name": "\\N", "count": 7, "ratio": 9007199254740993, "active": True, "metadata": None},
        {"name": "", "count": 0, "ratio": 5e-324, "active": False, "metadata": ""},
    ]
    export = fixture(
        work, "export", "json-to-csv", columns, json.dumps(rows, ensure_ascii=False).encode(), delimiter=";"
    )
    csv_report = run(writer, export, rows)
    source = (export.output / "data.csv").read_bytes()
    imported = fixture(work, "import", "csv-to-json", columns, source, delimiter=";")
    json_report = run(reader, imported, rows)
    assert json.loads((imported.output / "data.json").read_bytes()) == rows
    return {
        "writer": writer.engine,
        "reader": reader.engine,
        "records": len(rows),
        "csv_sha256": csv_report["data_sha256"],
        "json_sha256": json_report["data_sha256"],
        "typed_roundtrip": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "041")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "041/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"041": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "csv-json"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "041/corpus_041")], "rust"),
    }
    observations = []
    for writer in apps.values():
        for reader in apps.values():
            work = directory / (writer.engine + "-" + reader.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(writer, reader, work))
            print(writer.engine + " CSV writer / " + reader.engine + " JSON writer: passed", flush=True)
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
