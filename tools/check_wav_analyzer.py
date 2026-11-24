"""Exchange original WAV bytes, reports and edited images across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.wav_analyzer import (
    consume,
    edit_export,
    files_at,
    fixture,
    gain,
    run,
)
from corpus_checks.wav_fixture import canonical, digest, read_wave

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, analyzer: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(
        replayed[key] == exported[key]
        for key in ["archive.json", "original.wav", "normalized.wav", "waveform.svg", "samples.csv"]
    )
    third = root / "analyzer"
    restore(replayed, third)
    assert consume(analyzer, third, "process.json") == archive
    settings = {"method": "peak", "target": 12345}
    revised = edit_export(analyzer, third, settings, "edited")
    assert revised["results"]["output"]["peak"] == 12345
    assert revised["results"]["clipped_low"] == revised["results"]["clipped_high"] == 0
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    stable = edit_export(writer, fourth / "replayed", settings, "idempotent", (fourth / "normalized.wav").read_bytes())
    assert stable["results"]["changed_samples"] == 0
    assert (fourth / "normalized.wav").read_bytes() == (fourth / "replayed/idempotent/normalized.wav").read_bytes()
    clipped = edit_export(replayer, fourth / "replayed/idempotent", gain(1000000), "clip")
    assert clipped["results"]["clipped_low"] > 0 and clipped["results"]["clipped_high"] > 0
    assert consume(analyzer, fourth / "replayed/idempotent/clip", "replay.json") == clipped
    restored = edit_export(
        writer, fourth / "replayed/idempotent/clip/replayed", archive["settings"], "restored", exported["original.wav"]
    )
    assert restored == archive
    assert (fourth / "replayed/idempotent/clip/replayed/restored/normalized.wav").read_bytes() == exported[
        "normalized.wav"
    ]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "analyzer": analyzer.engine,
        "original_samples": len(read_wave(exported["original.wav"])[1]),
        "actual_exported_requests_consumed": True,
        "edited_gain_and_peak_replayed": True,
        "normalized_wave_is_reusable_and_idempotent": True,
        "clipping_counts_replayed": True,
        "original_binary_and_output_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "clipped_archive_sha256": digest(canonical(clipped)),
        "svg_sha256": digest(exported["waveform.svg"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "112")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "112/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "wav-analyzer"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"112": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "112/corpus_112")], "rust"),
    ]
    observations = []
    for writer, replayer, analyzer in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{analyzer.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, analyzer, work))
        print(name + " WAV exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "clipped_archive_sha256", "svg_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"112": current},
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
