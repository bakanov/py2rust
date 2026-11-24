"""Exchange original PNG bytes, reports and edited images across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.png_fixture import canonical, digest, image, rich_parts
from corpus_checks.png_inspector import consume, edit_export, files_at, fixture, run

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, inspector: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first), codes=[])
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed = files_at(second / "replayed")
    assert all(replayed[key] == exported[key] for key in ["archive.json", "image.png", "report.html", "chunks.json"])
    third = root / "inspector"
    restore(replayed, third)
    assert consume(inspector, third, "inspect.json") == archive
    parts = rich_parts()
    parts[6] = (b"tEXt", b"Author\0Edited <metadata> & caf\xe9")
    revised = edit_export(inspector, third, image(parts), "edited", [])
    assert revised["results"]["chunks"][6]["metadata"]["text"] == "Edited <metadata> & café"
    assert revised["results"]["chunks"][6]["data_sha256"] != archive["results"]["chunks"][6]["data_sha256"]
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    corrupt = bytearray((fourth / "image.png").read_bytes())
    corrupt[29] ^= 1
    broken = edit_export(writer, fourth / "replayed", bytes(corrupt), "corrupt", ["crc"])
    assert consume(replayer, fourth / "replayed/corrupt", "replay.json") == broken
    restored = edit_export(inspector, fourth / "replayed/corrupt/replayed", exported["image.png"], "restored", [])
    assert restored == archive
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "inspector": inspector.engine,
        "actual_exported_requests_consumed": True,
        "edited_png_metadata_replayed": True,
        "crc_findings_replayed_with_exit_one": True,
        "original_binary_and_findings_restored": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "corrupt_archive_sha256": digest(canonical(broken)),
        "html_sha256": digest(exported["report.html"]),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "111")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "111/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "png-inspector"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"111": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "111/corpus_111")], "rust"),
    ]
    observations = []
    for writer, replayer, inspector in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{inspector.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, inspector, work))
        print(name + " PNG exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "corrupt_archive_sha256", "html_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"111": current},
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
