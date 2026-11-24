"""Exchange real circuit archives and exported requests across all writer/replayer/resolver engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.circuit_calculator import (
    consume,
    files_at,
    fixture,
    invalid_trees,
    run,
    save,
)
from corpus_checks.circuit_fixture import canonical, digest, fixtures
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, replayer: Application, resolver: Application, root: Path) -> dict:
    first = root / "writer"
    invalid, reason = invalid_trees()[-1]
    rows = fixtures()[:15] + [invalid]
    reasons = {invalid["id"]: reason}
    archive = run(writer, first, fixture(first, rows), reasons)
    exported = files_at(first / "output")
    second = root / "replayer"
    restore(exported, second)
    replay = consume(replayer, second, "replay.json", reasons)
    assert canonical(replay) == canonical(archive)
    third = root / "resolver"
    restore(files_at(second / "replayed"), third)
    solved = consume(resolver, third, "solve.json", reasons)
    assert canonical(solved) == canonical(archive)
    # Edit an actual exported source tree, then compute and replay a new archive.
    changed = json.loads((third / "networks.json").read_bytes())
    changed["cases"] = changed["cases"][:1]
    changed["cases"][0]["tree"]["ohms"] = "250"
    save(third / "changed-networks.json", changed)
    request = json.loads((third / "solve.json").read_bytes())
    request.update(input="changed-networks.json", output="changed")
    save(third / "changed-job.json", request)
    revised = run(resolver, third, request, selected="changed-job.json")
    assert revised["results"][0]["equivalent"]["ohms"] == 250.0
    fourth = root / "return-to-writer"
    restore(files_at(third / "changed"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    assert files_at(first / "output") == exported
    for directory in [second, third]:
        assert (directory / "archive.json").read_bytes() == exported["archive.json"]
        assert (directory / "networks.json").read_bytes() == exported["networks.json"]
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "resolver": resolver.engine,
        "circuits": len(rows),
        "rejected_circuits": 1,
        "actual_exported_requests_consumed": True,
        "all_reduction_steps_checked": True,
        "edited_network_recomputed_and_replayed": True,
        "input_archives_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "104")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "104/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "circuit-calculator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"104": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "104/corpus_104")], "rust"),
    ]
    observations = []
    for writer, replayer, resolver in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{resolver.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, resolver, work))
        print(name + " circuit exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"104": current},
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
