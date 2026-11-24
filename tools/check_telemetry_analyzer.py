"""Exchange telemetry archives and actual replay/reanalysis requests across eight Python/Rust combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.telemetry_analyzer import (
    consume,
    files_at,
    fixture,
    invalid_series,
    run,
    save,
)
from corpus_checks.trend_fixture import canonical, digest, document, fixtures

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, analyzer: Application, root: Path) -> dict:
    first = root / "writer"
    invalid, reason = invalid_series()[-1]
    rows = fixtures()[:7] + [invalid]
    reasons = {invalid["id"]: reason}
    archive = run(writer, first, fixture(first, document(rows)), reasons)
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert canonical(consume(replayer, second, "replay.json", reasons)) == canonical(archive)
    third = root / "analyzer"
    restore(files_at(second / "replayed"), third)
    assert canonical(consume(analyzer, third, "analyze.json", reasons)) == canonical(archive)
    changed = json.loads((third / "telemetry.json").read_bytes())
    changed["series"] = changed["series"][:1]
    changed["settings"].update(window=2, warmup=2)
    changed["series"][0]["samples"].append({"at": "2026-01-01T00:00:14Z", "value": 300})
    save(third / "changed-telemetry.json", changed)
    request = json.loads((third / "analyze.json").read_bytes())
    request.update(input="changed-telemetry.json", output="changed")
    save(third / "changed-job.json", request)
    revised = run(analyzer, third, request, selected="changed-job.json")
    assert revised["results"][0]["points"][-1]["decision"]["status"] == "constant_shift"
    assert revised["results"][0]["points"][-1]["baseline"]["statistics"]["count"] == 2
    fourth = root / "return-to-writer"
    restore(files_at(third / "changed"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    assert files_at(first / "output") == exported
    for directory in [second, third]:
        assert (directory / "archive.json").read_bytes() == exported["archive.json"]
        assert (directory / "telemetry.json").read_bytes() == exported["telemetry.json"]
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "analyzer": analyzer.engine,
        "series": len(rows),
        "rejected_series": 1,
        "actual_exported_requests_consumed": True,
        "every_window_and_decision_checked": True,
        "changed_settings_and_samples_replayed": True,
        "input_archives_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "105")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "105/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "telemetry-analyzer"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"105": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "105/corpus_105")], "rust"),
    ]
    observations = []
    for writer, replayer, analyzer in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{analyzer.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, analyzer, work))
        print(name + " telemetry exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"105": current},
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
