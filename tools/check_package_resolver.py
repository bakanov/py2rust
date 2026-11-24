"""Consume actual index, lock and replay bundles through eight Python/Rust engine combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.package_resolver import fixture, lock_fixture, run, save
from corpus_checks.resolver_fixture import SELECTED

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in root.iterdir()}


def consume(app: Application, bundle: dict[str, bytes], request: str, work: Path) -> tuple[dict, dict[str, bytes]]:
    work.mkdir(parents=True)
    for name, data in bundle.items():
        (work / name).write_bytes(data)
    config = json.loads(bundle[request])
    save(work / "resolver-job.json", config)
    report = run(app, work, config)
    for name, data in bundle.items():
        assert (work / name).read_bytes() == data
    return report, snapshot(work / config["output"])


def exercise(writer: Application, verifier: Application, replayer: Application, root: Path) -> dict:
    work = root / "resolved"
    first = run(writer, work, fixture(work))
    original = snapshot(work / "result")
    second, verified = consume(verifier, original, "verify.json", root / "verify")
    third, repeated = consume(replayer, original, "replay.json", root / "replay")
    assert second["outcome"]["status"] == "valid_lock"
    assert first == third and first["outcome"]["selected"] == SELECTED
    assert original["lock.json"] == verified["lock.json"] == repeated["lock.json"]
    assert original == repeated
    assert snapshot(work / "result") == original
    hashes = {}
    for label in ["unsatisfiable", "invalid-lock"]:
        work = root / label
        if label == "unsatisfiable":
            config = fixture(
                work,
                {
                    "version": 1,
                    "packages": {
                        "A": [
                            {"version": "1.0.0", "dependencies": {"A": "^2.0.0"}},
                            {"version": "2.0.0", "dependencies": {"A": "^1.0.0"}},
                        ]
                    },
                },
                {"A": "*"},
            )
        else:
            config = lock_fixture(work, index_sha256="0" * 64)
        report = run(writer, work, config)
        bundle = snapshot(work / "result")
        again, middle = consume(verifier, bundle, "replay.json", root / (label + "-second"))
        final, exported = consume(replayer, middle, "replay.json", root / (label + "-third"))
        assert report == again == final and bundle == middle == exported
        assert snapshot(work / "result") == bundle
        assert "lock.json" not in bundle
        hashes[label] = hashlib.sha256(bundle["report.json"]).hexdigest()
    return {
        "writer": writer.engine,
        "verifier": verifier.engine,
        "replayer": replayer.engine,
        "actual_indexes_locks_and_replay_requests_consumed": True,
        "resolved_unsatisfiable_and_invalid_lock_bundles_identical": True,
        "lock_sha256": hashlib.sha256(original["lock.json"]).hexdigest(),
        "report_sha256": hashes,
    }


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "096")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "096/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "package-resolver"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    save(report, {"status": "in_progress", "fingerprints": {"096": current}, "checker_sha256": checker_hash})
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "096/corpus_096")], "rust"),
    ]
    observations = []
    for writer in apps:
        for verifier in apps:
            for replayer in apps:
                name = f"{writer.engine}-{verifier.engine}-{replayer.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, verifier, replayer, work))
                print(name + " index/lock/replay exchange: passed", flush=True)
    assert len({row["lock_sha256"] for row in observations}) == 1
    assert len({json.dumps(row["report_sha256"], sort_keys=True) for row in observations}) == 1
    assert fingerprint(program) == current
    report.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"096": current},
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
