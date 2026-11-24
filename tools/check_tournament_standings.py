"""Exchange tournaments, edited fixtures and shared sporting ranks across all eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.tournament_fixture import canonical, digest, document
from corpus_checks.tournament_standings import (
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


def exercise(writer: Application, replayer: Application, ranker: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first, document()))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    third = root / "ranker"
    replayed_exports = files_at(second / "replayed")
    restore(replayed_exports, third)
    assert consume(ranker, third, "rank.json") == archive
    changed = json.loads((third / "fixtures.json").read_bytes())
    changed["fixtures"][2].update(home_score=0, away_score=2)
    tied = edit_export(ranker, third, changed, "tied")
    assert [(r["id"], r["rank"]) for r in tied["results"]["standings"]] == [("C", 1), ("A", 2), ("D", 2), ("B", 4)]
    changed = json.loads((third / "tied/fixtures.json").read_bytes())
    changed["fixtures"][0].update(home_score=0, away_score=2)
    broken = edit_export(ranker, third / "tied", changed, "broken")
    assert [(r["id"], r["rank"]) for r in broken["results"]["standings"]] == [("B", 1), ("C", 2), ("D", 3), ("A", 4)]
    fourth = root / "return-to-writer"
    restore(files_at(third / "tied/broken"), fourth)
    assert consume(writer, fourth, "replay.json") == broken
    changed = json.loads((fourth / "replayed/fixtures.json").read_bytes())
    changed["fixtures"][0].update(home_score=2, away_score=0)
    changed["fixtures"][2].update(home_score=None, away_score=None)
    assert edit_export(writer, fourth / "replayed", changed, "restored") == archive
    assert files_at(first / "output") == exported
    for directory, original in [(second, exported), (third, replayed_exports)]:
        assert all((directory / name).read_bytes() == raw for name, raw in original.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "ranker": ranker.engine,
        "teams": 4,
        "fixtures": 6,
        "initial_played": 5,
        "edited_played": 6,
        "actual_exported_requests_consumed": True,
        "shared_rank_created_and_broken": True,
        "original_season_restored_from_export": True,
        "every_metric_and_contribution_checked": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "tied_archive_sha256": digest(canonical(tied)),
        "broken_archive_sha256": digest(canonical(broken)),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "108")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "108/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "tournament-standings"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"108": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "108/corpus_108")], "rust"),
    ]
    observations = []
    for writer, replayer, ranker in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{ranker.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, ranker, work))
        print(name + " tournament exchange: passed", flush=True)
    for key in ["archive_sha256", "tied_archive_sha256", "broken_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"108": current},
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
