"""Exchange population series, plots and edited experiment requests across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.population_fixture import canonical, digest, document
from corpus_checks.population_simulator import (
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


def exercise(writer: Application, replayer: Application, simulator: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first, document()))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    replayed_exports = files_at(second / "replayed")
    assert (
        replayed_exports["plot.svg"] == exported["plot.svg"]
        and replayed_exports["series.csv"] == exported["series.csv"]
    )
    third = root / "simulator"
    restore(replayed_exports, third)
    assert consume(simulator, third, "simulate.json") == archive
    changed = json.loads((third / "experiment.json").read_bytes())
    changed["timestep"] /= 2
    changed["steps"] *= 2
    changed["cases"][0]["rate"] = 0.12
    changed["title"] = "Edited <population> & comparison"
    revised = edit_export(simulator, third, changed, "edited")
    assert revised["results"]["summary"] == {"cases": 4, "steps": 320, "points": 1284, "horizon": 20.0}
    assert revised["results"]["series"][0]["final"] > archive["results"]["series"][0]["final"]
    for old, new in zip(archive["results"]["series"][1:], revised["results"]["series"][1:]):
        assert old["final"] != new["final"]
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    restored = edit_export(
        writer, fourth / "replayed", json.loads((first / "output/experiment.json").read_bytes()), "restored"
    )
    assert restored == archive
    assert (fourth / "replayed/restored/plot.svg").read_bytes() == exported["plot.svg"]
    assert files_at(first / "output") == exported
    for directory, snapshot in [(second, exported), (third, replayed_exports)]:
        assert all((directory / name).read_bytes() == raw for name, raw in snapshot.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "simulator": simulator.engine,
        "cases": 4,
        "original_points": 644,
        "edited_points": 1284,
        "horizon_preserved": True,
        "actual_exported_requests_consumed": True,
        "edited_parameters_and_timestep_replayed": True,
        "original_experiment_restored": True,
        "all_series_and_plot_coordinates_checked": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "plot_sha256": digest(exported["plot.svg"]),
        "edited_plot_sha256": digest((third / "edited/plot.svg").read_bytes()),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "110")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "110/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "population-simulator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"110": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "110/corpus_110")], "rust"),
    ]
    observations = []
    for writer, replayer, simulator in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{simulator.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, simulator, work))
        print(name + " population exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "plot_sha256", "edited_plot_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"110": current},
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
