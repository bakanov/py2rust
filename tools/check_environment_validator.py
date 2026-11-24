"""Consume actual recheck requests across eight Python/Rust validation combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.environment_fixture import OTHER, schema
from corpus_checks.environment_validator import (
    consume,
    digest,
    fixture,
    run,
    secret_free,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}


def restore(files: dict[str, bytes], directory: Path) -> None:
    directory.mkdir(parents=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return  # noqa: PLR1711


def exercise(writer: Application, reader: Application, rechecker: Application, root: Path) -> dict:
    document = schema()
    first = root / "first"
    valid_environment = {"EV_REQUIRED": '"configured"'}
    initial = run(writer, first, fixture(first, document), document, valid_environment)
    assert initial["valid"]
    source_bytes = (first / "schema.json").read_bytes()
    exported = snapshot(first / "output")
    second = root / "second"
    restore(exported, second)
    changed, second_output = consume(reader, second, document, {**valid_environment, "EV_TOKEN": json.dumps(OTHER)})
    assert not changed["valid"] and changed["diagnostics"] == [
        {"field": "feature", "env": "EV_FEATURE", "code": "dependency", "dependency": "token"}
    ]
    assert initial["effective"]["token"] == changed["effective"]["token"] == "<redacted>"
    exported_changed = snapshot(second_output)
    third = root / "third"
    restore(exported_changed, third)
    final, third_output = consume(rechecker, third, document, valid_environment)
    assert final == initial
    assert (third_output / "report.json").read_bytes() == exported["report.json"]
    assert (first / "schema.json").read_bytes() == source_bytes
    assert snapshot(first / "output") == exported and snapshot(second_output) == exported_changed
    for files in [exported, exported_changed, snapshot(third_output)]:
        for raw in files.values():
            secret_free(raw)
    return {
        "writer": writer.engine,
        "reader": reader.engine,
        "rechecker": rechecker.engine,
        "actual_recheck_requests_consumed": True,
        "original_external_schema_preserved": True,
        "changed_environment_revalidated": True,
        "secret_predicate_uses_unredacted_internal_value": True,
        "all_exported_bytes_secret_scanned": True,
        "valid_report_sha256": digest(exported["report.json"]),
        "invalid_report_sha256": digest(exported_changed["report.json"]),
    }


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "099")
    current = fingerprint(program)
    result = json.loads((BUILD / "099/result.json").read_text())
    assert result["status"] == "verified" and result["fingerprint"] == current
    directory = BUILD / "environment-validator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"099": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "099/corpus_099")], "rust"),
    ]
    observations = []
    for writer in apps:
        for reader in apps:
            for rechecker in apps:
                name = f"{writer.engine}-{reader.engine}-{rechecker.engine}"
                root = directory / name
                if root.exists():
                    shutil.rmtree(root)
                observations.append(exercise(writer, reader, rechecker, root))
                print(name + " environment/recheck exchange: passed", flush=True)
    assert len({row["valid_report_sha256"] for row in observations}) == 1
    assert len({row["invalid_report_sha256"] for row in observations}) == 1
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"099": current},
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
