"""Exchange original datasets, edited layouts and actual replay requests across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.dashboard_fixture import canonical, digest
from corpus_checks.svg_dashboard import consume, edit_export, files_at, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, renderer: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[k] == v for k, v in exported.items() if k not in ["report.json", "manifest.json"])
    third = root / "renderer"
    restore(replayed, third)
    assert consume(renderer, third, "render.json") == archive
    original = json.loads(exported["data.json"])
    changed = json.loads(canonical(original))
    changed["title"] = "Edited <network> & latency"
    changed["charts"].reverse()
    changed["charts"][0]["points"] = [{"label": "new 🐍", "value": -37.5}, {"label": "next", "value": 22}]
    edited = edit_export(renderer, third, changed, 3, "edited")
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == edited
    relayout = edit_export(replayer, fourth, changed, 1, "relayout")
    assert consume(renderer, fourth / "relayout", "replay.json") == relayout
    assert relayout["results"]["height"] > edited["results"]["height"]
    assert relayout["results"]["width"] < edited["results"]["width"]
    restored = edit_export(writer, fourth / "relayout", original, archive["columns"], "restored")
    assert restored == archive
    assert (fourth / "relayout/restored/dashboard.svg").read_bytes() == exported["dashboard.svg"]
    assert (fourth / "relayout/restored/index.html").read_bytes() == exported["index.html"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "renderer": renderer.engine,
        "actual_exported_requests_consumed": True,
        "edited_dataset_and_layout_replayed": True,
        "original_data_and_markup_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(edited)),
        "svg_sha256": digest(exported["dashboard.svg"]),
        "html_sha256": digest(exported["index.html"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "116")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "116/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "svg-dashboard"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"116": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "116/corpus_116")], "rust"),
    ]
    observations = []
    for writer, replayer, renderer in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{renderer.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, renderer, work))
        print(name + " dashboard exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "svg_sha256", "html_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"116": current},
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
