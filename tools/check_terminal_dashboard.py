"""Exchange task snapshots, edited layouts and actual replay requests across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.terminal_dashboard import (
    consume,
    edit_export,
    files_at,
    fixture,
    run,
)
from corpus_checks.terminal_fixture import canonical, digest

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, watcher: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[k] == v for k, v in exported.items() if k not in ["report.json", "manifest.json"])
    third = root / "watcher"
    restore(replayed, third)
    assert consume(watcher, third, "watch.json") == archive
    original = json.loads(exported["snapshot.json"])
    changed = json.loads(canonical(original))
    changed["title"] = "Edited network tasks 東京"
    changed["sequence"] += 1
    changed["tasks"].reverse()
    changed["tasks"][0].update(label="Edited 👩🏽‍💻 upload", state="done", done=11, total=11)
    edited = edit_export(watcher, third, changed, 40, "edited")
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == edited
    relayout = edit_export(replayer, fourth, changed, 12, "relayout")
    assert consume(watcher, fourth / "relayout", "replay.json") == relayout
    assert relayout["events"][0]["columns"] < edited["events"][0]["columns"]
    restored = edit_export(writer, fourth / "relayout", original, archive["settings"]["columns"], "restored")
    assert restored == archive
    assert (fourth / "relayout/restored/transcript.txt").read_bytes() == exported["transcript.txt"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "watcher": watcher.engine,
        "actual_exported_requests_consumed": True,
        "edited_snapshot_and_layout_replayed": True,
        "original_snapshot_and_frames_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(edited)),
        "transcript_sha256": digest(exported["transcript.txt"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "117")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "117/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "terminal-dashboard"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"117": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "117/corpus_117")], "rust"),
    ]
    observations = []
    for writer, replayer, watcher in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{watcher.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, watcher, work))
        print(name + " terminal exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "transcript_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"117": current},
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
