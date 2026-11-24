"""Exchange exact tariff bills, actual requests and edited tariff definitions across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.tariff_fixture import at, canonical, digest, document
from corpus_checks.tariff_simulator import consume, files_at, fixture, run, save

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, simulator: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first, document()))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    third = root / "simulator"
    restore(files_at(second / "replayed"), third)
    assert consume(simulator, third, "simulate.json") == archive
    changed = json.loads((third / "usage.json").read_bytes())
    changed["intervals"].append({"start": at(111600), "end": at(111601), "kwh": "2"})
    changed["tariffs"][0]["bands"][0]["rate"] = "1.5"
    save(third / "changed-usage.json", changed)
    request = json.loads((third / "simulate.json").read_bytes())
    request.update(input="changed-usage.json", output="changed")
    save(third / "changed-job.json", request)
    revised = run(simulator, third, request, selected="changed-job.json")
    assert revised["results"]["ranking"] == ["twin", "time", "flat"]
    assert revised["results"]["bills"][0]["rounded_total"] == "16.00"
    fourth = root / "return-to-writer"
    restore(files_at(third / "changed"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    assert files_at(first / "output") == exported
    for directory in [second, third]:
        assert (directory / "archive.json").read_bytes() == exported["archive.json"]
        assert (directory / "usage.json").read_bytes() == exported["usage.json"]
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "simulator": simulator.engine,
        "tariffs": 3,
        "initial_intervals": 3,
        "revised_intervals": 4,
        "actual_exported_requests_consumed": True,
        "every_segment_and_allocation_checked": True,
        "changed_tariffs_and_usage_replayed": True,
        "input_archives_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "106")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "106/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "tariff-simulator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"106": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "106/corpus_106")], "rust"),
    ]
    observations = []
    for writer, replayer, simulator in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{simulator.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, simulator, work))
        print(name + " tariff exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"106": current},
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
