"""Independent partition, UTC, defaults, schema rejection and idempotence oracles."""

import copy
import json
from pathlib import Path

from .common import Application

SAMPLE = Path(__file__).resolve().parents[2] / "examples/corpus/042_record_cleaner"


def check(app: Application, directory: Path) -> dict:
    schema = json.loads((SAMPLE / "schema.json").read_text())
    valid = json.loads((SAMPLE / "records.json").read_text())
    bad_fields = dict(valid[0], id=True, name="x", email="invalid", joined="2023-02-29T00:00:00Z")
    missing = dict(valid[0], tag="unexpected")
    del missing["id"]
    records = [*valid, bad_fields, missing, ["not an object"], dict(valid[0], score=1.01), dict(valid[0], active=1)]
    schema_path = directory / "schema.json"
    input_path = directory / "records.json"
    output = directory / "report.json"
    settings = {"CLEAN_SCHEMA": str(schema_path), "CLEAN_INPUT": str(input_path), "CLEAN_OUTPUT": str(output)}

    def run(document: dict, rows: list, expected_status: int) -> dict:
        schema_path.write_text(json.dumps(document))
        input_path.write_text(json.dumps(rows))
        before = input_path.read_bytes()
        result = app.run(directory, settings)
        assert result.returncode == expected_status, result.stderr + result.stdout
        assert input_path.read_bytes() == before
        report = json.loads(output.read_text())
        assert json.loads(result.stdout) == report["summary"]
        return report

    report = run(schema, records, 1)
    assert report["summary"] == {"input": 7, "accepted": 2, "rejected": 5, "field_errors": 9}, report
    expected_records = [
        {
            "id": 1,
            "name": "ALICE",
            "email": "a@team.example",
            "joined": "2024-02-29T20:59:59.500000+00:00",
            "active": True,
            "score": 0.0,
        },
        {
            "id": 2,
            "name": "BOB",
            "email": "b@team.example",
            "joined": "2024-03-01T00:00:00.000000+00:00",
            "active": True,
            "score": 0.0,
            "nickname": None,
        },
    ]
    assert report["accepted"] == [{"index": i, "record": record} for i, record in enumerate(expected_records)]
    assert [row["index"] for row in report["rejected"]] == [2, 3, 4, 5, 6]
    assert [row["record"] for row in report["rejected"]] == records[2:]
    assert [[error["field"] for error in row["errors"]] for row in report["rejected"]] == [
        ["id", "name", "email", "joined"],
        ["id", "tag"],
        ["$"],
        ["score"],
        ["active"],
    ]
    repeated = run(schema, expected_records, 0)
    assert [row["record"] for row in repeated["accepted"]] == expected_records
    extra = dict(valid[0], extra={"nested": [True, 1, "世界"]})
    preserved = run(dict(schema, unknown="preserve"), [extra], 0)
    assert preserved["accepted"][0]["record"]["extra"] == extra["extra"]
    dropped = run(dict(schema, unknown="drop"), [extra], 0)
    assert "extra" not in dropped["accepted"][0]["record"]
    choice_schema = copy.deepcopy(schema)
    choice_schema["fields"][1]["choices"] = ["ALICE"]
    choice_report = run(choice_schema, [valid[1]], 1)
    assert choice_report["rejected"][0]["errors"] == [{"field": "name", "reason": "value is not in choices"}]
    previous = output.read_bytes()
    invalid_schemas = []
    duplicate = copy.deepcopy(schema)
    duplicate["fields"].append(duplicate["fields"][0])
    invalid_schemas.append(duplicate)
    for index, changes in [
        (0, {"min": 3, "max": 1}),
        (4, {"default": 1}),
        (1, {"min_length": -1}),
        (2, {"pattern": "("}),
        (1, {"choices": ["alice"]}),
        (4, {"min": 0}),
    ]:
        bad = copy.deepcopy(schema)
        bad["fields"][index].update(changes)
        invalid_schemas.append(bad)
    for bad in invalid_schemas:
        schema_path.write_text(json.dumps(bad))
        assert app.run(directory, settings).returncode != 0
        assert output.read_bytes() == previous
    schema_path.write_text(json.dumps(schema))
    before = input_path.read_bytes()
    assert app.run(directory, dict(settings, CLEAN_OUTPUT=str(input_path))).returncode != 0
    assert input_path.read_bytes() == before
    return {
        "summary": report["summary"],
        "accepted": expected_records,
        "rejections": report["rejected"],
        "idempotent": True,
        "unknown_field_policies": True,
        "invalid_schemas": len(invalid_schemas),
        "input_preserved": True,
    }
