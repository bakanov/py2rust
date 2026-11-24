"""Exchange warehouse traces, continuation programs and full rewind requests across eight engine combinations."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.warehouse_fixture import canonical, digest, document
from corpus_checks.warehouse_simulator import (
    consume,
    edit_export,
    exported_programs,
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
    third = root / "simulator"
    replayed_exports = files_at(second / "replayed")
    restore(replayed_exports, third)
    assert consume(simulator, third, "simulate.json") == archive
    exported_programs(simulator, third, archive)
    changed = json.loads((third / "continuation.json").read_bytes())
    changed["commands"] += ["undo"] * len(changed["commands"]) + ["up", "right", "right", "undo"]
    revised = edit_export(simulator, third, changed, "edited")
    assert revised["results"]["final"]["robot"] == [1, 3]
    assert revised["results"]["active_commands"] == ["up", "right"]
    assert revised["results"]["summary"] == {
        "commands": 16,
        "walks": 6,
        "pushes": 3,
        "undos": 7,
        "blocked": 0,
        "history_depth": 2,
    }
    fourth = root / "return-to-writer"
    restore(files_at(third / "edited"), fourth)
    assert consume(writer, fourth, "replay.json") == revised
    rewound = consume(writer, fourth / "replayed", "rewind-job.json")
    assert rewound["results"]["final"] == archive["results"]["initial"]
    assert files_at(first / "output") == exported
    for directory, original in [(second, exported), (third, replayed_exports)]:
        assert all((directory / name).read_bytes() == raw for name, raw in original.items())
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "simulator": simulator.engine,
        "original_commands": 15,
        "edited_commands": 16,
        "edited_history_depth": 2,
        "actual_replay_continue_rewind_restart_requests": True,
        "every_trace_state_checked": True,
        "edited_continuation_replayed": True,
        "full_rewind_restores_original_geometry": True,
        "input_exports_preserved": True,
        "archive_sha256": digest(canonical(archive)),
        "edited_archive_sha256": digest(canonical(revised)),
        "rewound_archive_sha256": digest(canonical(rewound)),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "109")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "109/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "warehouse-simulator"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"109": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "109/corpus_109")], "rust"),
    ]
    observations = []
    for writer, replayer, simulator in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{replayer.engine}-{simulator.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, replayer, simulator, work))
        print(name + " warehouse exchange: passed", flush=True)
    for key in ["archive_sha256", "edited_archive_sha256", "rewound_archive_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"109": current},
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
