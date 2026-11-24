"""Exchange complete binary fixtures and inspection reports between engine pairs."""

import itertools
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.traffic_replayer import (
    digest,
    encode,
    fixture,
    replay,
    run,
    verify_report,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(inspector: Application, replayer: Application, root: Path) -> dict:
    rows = [(0, 0, b"saved\0notes"), (0, 1, bytes(range(256)) * 300), (30, 0, "世界".encode()), (30, 1, b"ok")]
    first = root / "inspection"
    job = fixture(first, rows)
    inspected = run(inspector, first, job)
    verify_report(inspected, rows, encode(rows))
    (first / "inspection.json").write_text(json.dumps(inspected))
    snapshot = {p.name: digest(p.read_bytes()) for p in first.iterdir()}

    second = root / "replay"
    shutil.copytree(first, second)
    assert (second / "input.traffic").read_bytes() == (first / "input.traffic").read_bytes()
    report, _job = replay(replayer, second, rows, prepare=False)
    assert report["records"] == json.loads((second / "inspection.json").read_text())["records"]
    assert report["fixture"] == inspected["fixture"]
    assert (second / "input.traffic").read_bytes() == (first / "input.traffic").read_bytes()

    edited = list(rows)
    edited[2] = (30, 0, b"edited source")
    third = root / "edited"
    changed = fixture(third, edited)
    changed_report = run(replayer, third, changed)
    assert changed_report["fixture"]["sha256"] != inspected["fixture"]["sha256"]
    replay(inspector, root / "reverse", edited)
    assert {p.name: digest(p.read_bytes()) for p in first.iterdir()} == snapshot
    return {
        "inspector": inspector.engine,
        "replayer": replayer.engine,
        "fixture_sha256": digest(encode(rows)),
        "edited_fixture_sha256": digest(encode(edited)),
        "portable_inspection_matches_replay": True,
        "reverse_replay_of_edited_fixture": True,
        "source_export_preserved": True,
    }


def main() -> int:
    program = json.loads((CORPUS / "catalog.json").read_text())["programs"][-1]
    assert program["id"] == "120"
    current = fingerprint(program)
    evidence = json.loads((BUILD / "120/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "traffic-replayer"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"120": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "120/corpus_120")], "rust"),
    ]
    observations = []
    for inspector, replayer in itertools.product(apps, repeat=2):
        name = inspector.engine + "-" + replayer.engine
        home = directory / name
        if home.exists():
            shutil.rmtree(home)
        observations.append(exercise(inspector, replayer, home))
        print(name + " traffic fixture exchange: passed", flush=True)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"120": current},
                "checker_sha256": checker_hash,
                "observations": observations,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
