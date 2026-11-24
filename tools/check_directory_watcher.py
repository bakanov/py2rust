"""Resume actual saved pending events and journals across all Python/Rust engine combinations."""

import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.directory_watcher import (
    Fixture,
    canonical,
    fixture,
    normalize,
    poll,
    write,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def resume(previous: Fixture, work: Path) -> Fixture:
    work.mkdir(parents=True)
    (work / "state").mkdir()
    source = previous.output / "state.json"
    shutil.copyfile(source, work / "state/state.json")
    assert source.read_bytes() == (work / "state/state.json").read_bytes()
    config = dict(previous.config, root=str(previous.tree.resolve()), output="state")
    result = Fixture(work, config, copy.deepcopy(previous.model))
    result.write()
    return result


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory / "first")
    poll(writer, first, 0)
    write(first, "draft.txt", b"first", 10)
    write(first, "folder/note.txt", b"notes", 10)
    poll(writer, first, 10)
    write(first, "draft.txt", b"latest draft", 40)
    initial = poll(writer, first, 40)
    assert len(initial["pending"]) == 3 and initial["next_id"] == 1
    original = (first.output / "state.json").read_bytes()
    second = resume(first, directory / "second")
    halfway = poll(replayer, second, 110)
    assert len(halfway["pending"]) == 1 and halfway["next_id"] == 3
    (second.tree / "draft.txt").rename(second.tree / "saved.txt")
    moved = poll(replayer, second, 120)
    assert [row["kind"] for row in moved["journal"][-2:]] == ["created", "renamed"]
    write(second, "folder/note.txt", b"revised notes", 130)
    pending = poll(replayer, second, 130)
    assert pending["pending"]["folder/note.txt"]["first_ms"] == 130
    exported = (second.output / "state.json").read_bytes()
    third = resume(second, directory / "third")
    assert poll(reader, third, 229)["pending"]
    assert not poll(reader, third, 230)["pending"]
    (third.tree / "saved.txt").unlink()
    poll(reader, third, 240)
    (third.tree / "folder").rename(third.tree / "notes")
    poll(reader, third, 250)
    final = poll(reader, third, 350)
    assert final["next_id"] == 9 and len(final["journal"]) == 8 and not final["pending"]
    assert set(final["snapshot"]) == {"notes", "notes/note.txt"}
    assert original == (first.output / "state.json").read_bytes()
    assert exported == (second.output / "state.json").read_bytes()
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_saved_pending_state_consumed": True,
        "checkpoint_inputs_unchanged": True,
        "exact_quiet_window_after_restart": True,
        "renames_and_deletions_preserved": True,
        "first_checkpoint_sha256": hashlib.sha256(original).hexdigest(),
        "second_checkpoint_sha256": hashlib.sha256(exported).hexdigest(),
        "normalized_final_sha256": hashlib.sha256(canonical(normalize(final)).encode()).hexdigest(),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "087")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "087/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"087": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "directory-watcher"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "087/corpus_087")], "rust"),
    ]
    observations = []
    for writer in apps:
        for replayer in apps:
            for reader in apps:
                name = f"{writer.engine}-{replayer.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, replayer, reader, work))
                print(name + " actual checkpoint resume: passed", flush=True)
    assert len({row["normalized_final_sha256"] for row in observations}) == 1
    assert fingerprint(program) == current
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": fingerprints,
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
