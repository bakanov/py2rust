"""Exchange original BMP projects, edited layouts and reusable thumbnails across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.bmp_fixture import canonical, digest
from corpus_checks.bmp_thumbnails import (
    consume,
    edit_export,
    files_at,
    fixture,
    layout,
    run,
)
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, builder: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[k] == v for k, v in exported.items() if k not in ["report.json", "manifest.json"])
    third = root / "builder"
    restore(replayed, third)
    assert consume(builder, third, "rebuild.json") == archive
    retiled = consume(builder, third, "retile.json")
    assert retiled["results"]["sheet_sha256"] == archive["results"]["sheet_sha256"]
    revised = edit_export(
        builder, third, layout(box_width=13, box_height=9, columns=1, fit="stretch"), "edited", reverse=True
    )
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    assert consume(replayer, fourth, "rebuild.json") == revised
    retiled = consume(builder, fourth, "retile.json")
    assert retiled["results"]["sheet_sha256"] == revised["results"]["sheet_sha256"]
    # Restore actual original project/settings/names, but consume the transported original BMP files.
    original_project = json.loads(exported["project.json"])
    for i, image in enumerate(original_project["images"]):
        image["path"] = "source-" + str(len(original_project["images"]) - i - 1) + ".bmp"
    (fourth / "restore-project.json").write_bytes(canonical(original_project))
    request = {"version": 1, "mode": "build", "input": "restore-project.json", "output": "restored"}
    (fourth / "restore-job.json").write_bytes(canonical(request))
    restored = consume(writer, fourth, "restore-job.json")
    assert restored == archive
    assert (fourth / "restored/sheet.bmp").read_bytes() == exported["sheet.bmp"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "builder": builder.engine,
        "images": len(archive["images"]),
        "actual_exported_requests_consumed": True,
        "reordered_renamed_relayout_replayed": True,
        "thumbnails_are_reusable_and_idempotent": True,
        "original_pixels_and_layout_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "sheet_sha256": digest(exported["sheet.bmp"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "113")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "113/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "bmp-thumbnails"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"113": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "113/corpus_113")], "rust"),
    ]
    observations = []
    for writer, replayer, builder in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{builder.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, builder, work))
        print(name + " BMP exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "sheet_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"113": current},
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
