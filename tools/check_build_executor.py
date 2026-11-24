"""Exchange real build caches and artifacts between Python and standalone Rust."""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.build_executor import Fixture, cache, canonical, digest, fixture, run
from corpus_checks.build_fixture import build_fixture
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def exercise(writer: Application, replayer: Application, reader: Application, directory: Path) -> dict:
    helper = build_fixture(directory)
    first = fixture(directory / "first", helper)
    run(writer, first, set("ABCDEF"))
    first_files = snapshot(first.root)
    shutil.copytree(first.root, directory / "second")
    second = Fixture(directory / "second", json.loads(first.source.read_bytes()))
    run(replayer, second, set())
    assert cache(first) == cache(second)
    second_files = snapshot(second.root)
    shutil.copytree(second.root, directory / "third")
    third = Fixture(directory / "third", json.loads(second.source.read_bytes()))
    source = third.root / "a.txt"
    before = source.stat()
    source.write_bytes(b"a9\n")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    run(reader, third, set("ACDE"))
    assert snapshot(first.root) == first_files and snapshot(second.root) == second_files
    return {
        "writer": writer.engine,
        "replayer": replayer.engine,
        "reader": reader.engine,
        "actual_cache_and_artifact_files_consumed": True,
        "unchanged_replay_commands": 0,
        "changed_source_commands": ["A", "C", "D", "E"],
        "initial_cache_sha256": digest(canonical(cache(first))),
        "final_cache_sha256": digest(canonical(cache(third))),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "092")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "092/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"092": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "build-executor"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "092/corpus_092")], "rust"),
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
                print(name + " cache/artifact exchange: passed", flush=True)
    assert len({(row["initial_cache_sha256"], row["final_cache_sha256"]) for row in observations}) == 1
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
