"""Feed real CSV-import artifacts through queries and back to CSV in eight engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.csv_json import canonical, column, csv_text, encode
from corpus_checks.csv_json import fixture as conversion_fixture
from corpus_checks.csv_json import run as convert
from corpus_checks.json_query import fixture as query_fixture
from corpus_checks.json_query import oracle, success, text

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(importer: Application, query: Application, exporter: Application, work: Path) -> dict:
    columns = [column("team"), column("points", "number"), column("active", "boolean")]
    rows = [
        {"team": 'Network, "世界"\n', "points": 14, "active": True},
        {"team": "Tools", "points": 9.5, "active": True},
        {"team": 'Network, "世界"\n', "points": 7.25, "active": True},
        {"team": "Tools", "points": 30, "active": False},
        {"team": "Big", "points": 9007199254740993, "active": True},
    ]
    header = [column["name"] for column in columns]
    csv = csv_text([header, *[[encode(row[c["name"]], c["type"]) for c in columns] for row in rows]])
    imported = conversion_fixture(work, "import", "csv-to-json", columns, csv.encode())
    convert(importer, imported, rows)
    saved_input = imported.output / "data.json"
    before_input = saved_input.read_bytes()
    stages = [
        ("filter", ("==", "/active", True)),
        ("group", [("/team", "team")], [("/points", "points")]),
        ("select", [("/key/team", "team"), ("/count", "count"), ("/sums/points", "points")]),
        ("order", [("/points", True)]),
    ]
    expected = oracle(rows, stages)
    selected = query_fixture(work, "query", [], text(stages), input=str(saved_input))
    success(query, selected, expected)
    before_result = selected.output.read_bytes()
    exported = conversion_fixture(
        work,
        "export",
        "json-to-csv",
        [column("team"), column("count", "integer"), column("points", "number")],
        before_result,
        input=str(selected.output),
    )
    report = convert(exporter, exported, expected)
    assert saved_input.read_bytes() == before_input and selected.output.read_bytes() == before_result
    return {
        "importer": importer.engine,
        "query": query.engine,
        "exporter": exporter.engine,
        "input_rows": len(rows),
        "groups": len(expected),
        "result_sha256": hashlib.sha256(canonical(expected).encode()).hexdigest(),
        "csv_sha256": report["data_sha256"],
        "actual_artifact_paths": True,
    }


def main() -> int:
    programs = {
        row["id"]: row
        for row in json.loads((CORPUS / "catalog.json").read_text())["programs"]
        if row["id"] in {"041", "049"}
    }
    fingerprints = {identifier: fingerprint(program) for identifier, program in programs.items()}
    for identifier, current in fingerprints.items():
        evidence = json.loads((BUILD / identifier / "result.json").read_text())
        assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "json-query"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        identifier: [
            Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
            Application([str(BUILD / identifier / ("corpus_" + identifier))], "rust"),
        ]
        for identifier, program in programs.items()
    }
    observations = []
    for importer in apps["041"]:
        for query in apps["049"]:
            for exporter in apps["041"]:
                name = f"{importer.engine}-{query.engine}-{exporter.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(importer, query, exporter, work))
                print(name + " CSV import/query/export: passed", flush=True)
    assert len({row["result_sha256"] for row in observations}) == len({row["csv_sha256"] for row in observations}) == 1
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
