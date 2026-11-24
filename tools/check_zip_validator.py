"""Exchange actual ZIP inspections, edited archives and budgeted replays across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.zip_fixture import canonical, craft, digest
from corpus_checks.zip_validator import (
    DEFAULT,
    consume,
    edit_export,
    files_at,
    fixture,
    run,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, inspector: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first), codes=set())
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[k] == v for k, v in exported.items() if k not in ["report.json", "manifest.json"])
    third = root / "inspector"
    restore(replayed, third)
    assert consume(inspector, third, "inspect.json") == archive
    changed = craft([{"name": "notes/編集.txt".encode(), "flags": 2048 | 8, "data": b"Edited notes and attachments\n"}])
    edited = edit_export(inspector, third, changed, DEFAULT, "edited")
    assert not edited["results"]["errors"]
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == edited
    limited = edit_export(replayer, fourth, changed, dict(DEFAULT, entry_bytes=1), "limited")
    assert {row["code"] for row in limited["results"]["errors"]} == {"expanded_limit"}
    assert consume(inspector, fourth / "limited", "replay.json") == limited
    restored = edit_export(writer, fourth / "limited", exported["source.zip"], archive["limits"], "restored")
    assert restored == archive
    assert (fourth / "limited/restored/source.zip").read_bytes() == exported["source.zip"]
    assert (fourth / "limited/restored/report.txt").read_bytes() == exported["report.txt"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "inspector": inspector.engine,
        "actual_exported_requests_consumed": True,
        "edited_source_and_limits_replayed": True,
        "original_bytes_and_report_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(edited)),
        "limited_archive_sha256": digest(canonical(limited)),
        "report_sha256": digest(exported["report.txt"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "118")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "118/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "zip-validator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"118": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "118/corpus_118")], "rust"),
    ]
    observations = []
    for writer, replayer, inspector in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{inspector.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, inspector, work))
        print(name + " ZIP exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "limited_archive_sha256", "report_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"118": current},
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
