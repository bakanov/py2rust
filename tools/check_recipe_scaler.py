"""Exchange complete weekly plans and reusable scaled recipes across all eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.recipe_fixture import canonical, digest, document
from corpus_checks.recipe_scaler import (
    consume,
    files_at,
    fixture,
    restore_yield,
    run,
    save,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, planner: Application, root: Path) -> dict:
    first = root / "writer"
    archive = run(writer, first, fixture(first, document()))
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    assert consume(replayer, second, "replay.json") == archive
    third = root / "planner"
    replayed_exports = files_at(second / "replayed")
    restore(replayed_exports, third)
    assert consume(planner, third, "plan.json") == archive
    restored = []
    for index in range(4):
        stable = consume(planner, third, "scaled-" + str(index) + "-job.json")
        assert stable["results"]["selections"][0]["factor"] == "1"
        returned = restore_yield(planner, third, archive, index)
        restored.append(digest(canonical(returned)))
    changed = json.loads((third / "cookbook.json").read_bytes())
    changed["plan"][0]["portions"] = "7/3"
    changed["recipes"][1]["ingredients"][0].update(quantity="750", unit="g")
    changed["plan"].append({"day": 5, "recipe": "snack", "portions": "3"})
    save(third / "changed-cookbook.json", changed)
    request = json.loads((third / "plan.json").read_bytes())
    request.update(input="changed-cookbook.json", output="changed")
    save(third / "changed-job.json", request)
    revised = run(planner, third, request, selected="changed-job.json")
    totals = {(row["identity"], row["unit"]): row["quantity"] for row in revised["results"]["shopping"]}
    assert totals[("flour", "g")] == "2000/3" and totals[("water", "mL")] == "14/3"
    fourth = root / "return-to-writer"
    restore(files_at(third / "changed"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    assert files_at(first / "output") == exported
    for directory, original in [(second, exported), (third, replayed_exports)]:
        assert all((directory / name).read_bytes() == raw for name, raw in original.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "planner": planner.engine,
        "initial_selections": 4,
        "revised_selections": 5,
        "restored_exported_recipes": 4,
        "actual_exported_requests_consumed": True,
        "every_contribution_and_shopping_total_checked": True,
        "edited_units_quantities_and_portions_replayed": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "restored_archive_sha256": restored,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "107")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "107/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "recipe-scaler"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"107": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "107/corpus_107")], "rust"),
    ]
    observations = []
    for writer, replayer, planner in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{planner.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, planner, work))
        print(name + " recipe exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "restored_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"107": current},
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
