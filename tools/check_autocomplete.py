"""Trie pruning, usage counts and dictionary exports cross every Python/Rust engine combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.autocomplete import fixture, sample, success, suggest
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    trace = sample()
    first = fixture(directory, "first", trace[:6])
    initial = success(writer, first)
    assert initial[2]["index"]["nodes"] == 6
    assert initial[1][-1]["result"]["hits"][0]["term"] == "car"
    first_bytes = (first.output / "state.json").read_bytes()
    second = fixture(directory, "second", trace[6:10], state=str(first.output / "state.json"))
    middle = success(updater, second)
    assert middle[1][1]["result"]["hits"][0]["term"] == "cart"
    assert middle[2]["index"]["nodes"] == 4
    second_bytes = (second.output / "state.json").read_bytes()
    third = fixture(directory, "third", trace[10:], state=str(second.output / "state.json"))
    observed = success(reader, third)
    whole = fixture(directory, "whole", trace)
    expected = success(reader, whole)
    assert observed[0] == expected[0]
    assert (third.output / "state.json").read_bytes() == (whole.output / "state.json").read_bytes()
    dictionary = (third.output / "dictionary.json").read_bytes()
    assert dictionary == (whole.output / "dictionary.json").read_bytes()
    events = b"".join((fix.output / "events.jsonl").read_bytes() for fix in [first, second, third])
    assert events == (whole.output / "events.jsonl").read_bytes()
    assert (first.output / "state.json").read_bytes() == first_bytes
    assert (second.output / "state.json").read_bytes() == second_bytes
    fourth = fixture(directory, "resumed", [suggest("strass"), suggest("ca")], state=str(third.output / "state.json"))
    final = success(writer, fourth)
    assert final[1][0]["result"]["hits"] == [{"key": "strasse", "term": "STRASSE", "uses": 8}]
    assert final[1][1]["result"]["hits"][0]["key"] == "café"
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "state_sha256": hashlib.sha256((third.output / "state.json").read_bytes()).hexdigest(),
        "dictionary_sha256": hashlib.sha256(dictionary).hexdigest(),
        "events_sha256": hashlib.sha256(events).hexdigest(),
        "actual_artifact_paths": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "055")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "055/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"055": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "autocomplete"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "055/corpus_055")], "rust"),
    ]
    observations = []
    for writer in apps:
        for updater in apps:
            for reader in apps:
                name = f"{writer.engine}-{updater.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, updater, reader, work))
                print(name + " autocomplete save/update/suggest: passed", flush=True)
    assert (
        len({row["state_sha256"] for row in observations})
        == len({row["events_sha256"] for row in observations})
        == len({row["dictionary_sha256"] for row in observations})
        == 1
    )
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
