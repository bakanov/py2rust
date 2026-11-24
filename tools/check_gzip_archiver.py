"""Move real gzip archives and interrupted transactions between all eight engine triples."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.gzip_archiver import (
    digest,
    fixture,
    operation,
    run,
    save,
    snapshot,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def transfer(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    shutil.copytree(source / "archives", target / "archives")
    return  # noqa: PLR1711


def fault(app: Application, root: Path, config: dict, point: str) -> None:
    save(root / "gzip-job.json", config)
    result = app.run(root, {"GZIP_FAULT": point}, timeout=30)
    assert result.returncode == 2 and not result.stdout and "injected failure" in result.stderr, result
    return  # noqa: PLR1711


def exercise(writer: Application, recoverer: Application, inspector: Application, root: Path) -> dict:
    first = root / "writer"
    config, expected = fixture(first, {"first": b"GET /messages 200\n" * 40})
    run(writer, first, config, expected)
    expected["prepared"] = b"pending binary bytes\0\xff" * 3000
    (first / "prepared.log").write_bytes(expected["prepared"])
    config["inputs"] = [{"id": "prepared", "path": "prepared.log"}]
    fault(writer, first, config, "prepared")
    before = snapshot(first)

    second = root / "recoverer"
    transfer(first, second)
    run(recoverer, second, operation(config, "recover"), expected)
    assert not list(second.glob("*.log")), "prepared recovery must not depend on original log files"
    recovered = snapshot(second)

    third = root / "inspector"
    transfer(second, third)
    run(inspector, third, operation(config, "verify"), expected)
    expected["appended"] = "new saved notes 世界\n".encode() * 100
    (third / "appended.log").write_bytes(expected["appended"])
    append = dict(config, inputs=[{"id": "appended", "path": "appended.log"}], level=1)
    run(recoverer, third, append, expected)
    run(inspector, third, operation(config, "verify"), expected)
    expected["retry"] = b"a partially compressed rotation\n" * 3000
    (third / "retry.log").write_bytes(expected["retry"])
    retry = dict(config, inputs=[{"id": "retry", "path": "retry.log"}], level=9)
    fault(inspector, third, retry, "streaming")

    fourth = root / "retry"
    transfer(third, fourth)
    (fourth / "retry.log").write_bytes(expected["retry"])
    run(writer, fourth, retry, expected)
    run(inspector, fourth, operation(config, "verify"), expected)
    assert snapshot(first) == before and snapshot(second) == recovered
    index = json.loads((fourth / "archives/index.json").read_bytes())
    logical = [{key: row[key] for key in ["id", "source", "size", "sha256", "level"]} for row in index["entries"]]
    assert len(logical) == 4
    return {
        "writer": writer.engine,
        "recoverer": recoverer.engine,
        "inspector": inspector.engine,
        "actual_archives_and_pending_index_transferred": True,
        "prepared_recovery_without_original_sources": True,
        "unprepared_stream_reencoded_after_transfer": True,
        "mixed_encoder_archives_verified": True,
        "original_exports_preserved": True,
        "logical_index_sha256": digest(json.dumps(logical, sort_keys=True).encode()),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "119")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "119/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "gzip-archiver"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"119": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "119/corpus_119")], "rust"),
    ]
    observations = []
    for writer, recoverer, inspector in itertools.product(apps, repeat=3):
        name = f"{writer.engine}-{recoverer.engine}-{inspector.engine}"
        work = directory / name
        if work.exists():
            shutil.rmtree(work)
        observations.append(exercise(writer, recoverer, inspector, work))
        print(name + " gzip archive/recovery exchange: passed", flush=True)
    assert len({row["logical_index_sha256"] for row in observations}) == 1
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"119": current},
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
