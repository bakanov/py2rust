"""Pass actual sorted files through every Python/Rust writer, re-sorter and reader combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.external_sort import fixture, success

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, sorter: Application, reader: Application, directory: Path) -> dict:
    rows = [{"key": (i * 7) % 9, "group": ["世界", "a", "😀", "a"][i % 4], "id": i} for i in range(75)]
    first = fixture(directory, "first", rows, fan_in=3)
    success(writer, first)
    first_bytes = (first.output / "sorted.jsonl").read_bytes()
    second = fixture(directory, "second", [], field="group", kind="string", fan_in=8)
    second.config["inputs"] = [str(first.output / "sorted.jsonl")]
    second.save()
    success(sorter, second)
    middle_bytes = (second.output / "sorted.jsonl").read_bytes()
    third = fixture(directory, "third", [], field="group", kind="string", record_bytes=256, fan_in=2)
    third.config["inputs"] = [str(second.output / "sorted.jsonl"), str(first.output / "sorted.jsonl")]
    third.save()
    final = success(reader, third)
    actual = [json.loads(line) for line in (third.output / "sorted.jsonl").read_bytes().splitlines()]
    initial = sorted(rows, key=lambda row: row["key"])
    middle = sorted(initial, key=lambda row: row["group"])
    assert actual == sorted(middle + initial, key=lambda row: row["group"])
    assert (first.output / "sorted.jsonl").read_bytes() == first_bytes
    assert (second.output / "sorted.jsonl").read_bytes() == middle_bytes
    # A stable re-sort is byte-idempotent, even with a different merge geometry.
    fourth = fixture(directory, "fourth", [], field="group", kind="string", chunk_bytes=4194304, record_bytes=65536)
    fourth.config["inputs"] = [str(third.output / "sorted.jsonl")]
    fourth.save()
    success(writer, fourth)
    assert (fourth.output / "sorted.jsonl").read_bytes() == (third.output / "sorted.jsonl").read_bytes()
    return {
        "writer": writer.engine,
        "sorter": sorter.engine,
        "reader": reader.engine,
        "first_sha256": hashlib.sha256(first_bytes).hexdigest(),
        "middle_sha256": hashlib.sha256(middle_bytes).hexdigest(),
        "final_sha256": final["output_sha256"],
        "rows": final["rows"],
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "057")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "057/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"057": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "external-sort"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "057/corpus_057")], "rust"),
    ]
    observations = []
    for writer in apps:
        for sorter in apps:
            for reader in apps:
                name = f"{writer.engine}-{sorter.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, sorter, reader, work))
                print(name + " stable sort pipeline: passed", flush=True)
    for field in ["first_sha256", "middle_sha256", "final_sha256"]:
        assert len({row[field] for row in observations}) == 1
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
