"""Exchange P6 originals, edited pipelines and actual filtered output across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.ppm_filters import (
    consume,
    crop,
    edit_export,
    files_at,
    fixture,
    run,
    threshold,
)
from corpus_checks.ppm_fixture import canonical, digest

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, processor: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[k] == v for k, v in exported.items() if k not in ["report.json", "manifest.json"])
    third = root / "processor"
    restore(replayed, third)
    assert consume(processor, third, "process.json") == archive
    revised = edit_export(processor, third, [{"op": "invert"}, crop(0, 0, 2, 3), threshold(90)], "edited")
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    transformed = (fourth / "filtered.ppm").read_bytes()
    stable = edit_export(replayer, fourth, [threshold(90)], "stable", transformed)
    assert stable["results"]["output"]["raster_sha256"] == revised["results"]["output"]["raster_sha256"]
    inverted = edit_export(processor, fourth / "stable", [{"op": "invert"}], "inverted", transformed)
    original_again = edit_export(
        writer,
        fourth / "stable/inverted",
        [{"op": "invert"}],
        "again",
        (fourth / "stable/inverted/filtered.ppm").read_bytes(),
    )
    assert original_again["results"]["output"]["raster_sha256"] == revised["results"]["output"]["raster_sha256"]
    assert consume(replayer, fourth / "stable/inverted", "replay.json") == inverted
    restored = edit_export(
        writer, fourth / "stable/inverted/again", archive["pipeline"], "restored", exported["original.ppm"]
    )
    assert restored == archive
    assert (fourth / "stable/inverted/again/restored/filtered.ppm").read_bytes() == exported["filtered.ppm"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "processor": processor.engine,
        "actual_exported_requests_consumed": True,
        "edited_pipeline_replayed": True,
        "actual_output_reused": True,
        "inversion_and_threshold_identities": True,
        "original_binary_and_pipeline_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "filtered_sha256": digest(exported["filtered.ppm"]),
        "preview_sha256": digest(exported["preview.svg"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "114")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "114/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "ppm-filters"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"114": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "114/corpus_114")], "rust"),
    ]
    observations = []
    for writer, replayer, processor in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{processor.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, processor, work))
        print(name + " PPM exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "filtered_sha256", "preview_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"114": current},
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
