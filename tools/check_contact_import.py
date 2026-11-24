"""Import, extend and re-import real contact books in all eight Python/Rust combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.contact_import import fixture, row, run, sample
from corpus_checks.csv_json import canonical

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, repeater: Application, work: Path) -> dict:
    initial = fixture(work, "initial", sample())
    before = run(writer, initial)
    before_bytes = (initial.output / "book.json").read_bytes()
    additions = [
        row("new", name="新しい", email="new@example.com"),
        row("1", name="Updated José", email="jose@example.com"),
        sample()[0],
    ]
    update = fixture(work, "update", additions, state=str(initial.output / "book.json"))
    changed = run(updater, update)
    changed_bytes = (update.output / "book.json").read_bytes()
    assert (initial.output / "book.json").read_bytes() == before_bytes
    assert changed["report.json"]["added"] == 2 and changed["report.json"]["replayed"] == 1
    original_variants = {canonical(record) for record in before["book.json"]["state"]["records"]}
    assert original_variants <= {canonical(record) for record in changed["book.json"]["state"]["records"]}
    repeated = fixture(work, "repeated", additions, state=str(update.output / "book.json"))
    result = run(repeater, repeated)
    assert (update.output / "book.json").read_bytes() == changed_bytes
    assert (repeated.output / "book.json").read_bytes() == changed_bytes
    assert result["report.json"]["added"] == 0 and result["report.json"]["replayed"] == 3
    assert result["contacts.json"] == changed["contacts.json"] and result["review.json"] == changed["review.json"]
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "repeater": repeater.engine,
        "variants": result["report.json"]["variants"],
        "contacts": result["report.json"]["contacts"],
        "review_groups": result["report.json"]["review_groups"],
        "book_sha256": hashlib.sha256(changed_bytes).hexdigest(),
        "contacts_sha256": hashlib.sha256(canonical(result["contacts.json"]).encode()).hexdigest(),
        "review_sha256": hashlib.sha256(canonical(result["review.json"]).encode()).hexdigest(),
        "exact_reimport": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "048")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "048/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"048": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "contact-import"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "048/corpus_048")], "rust"),
    ]
    observations = []
    for writer in apps:
        for updater in apps:
            for repeater in apps:
                name = f"{writer.engine}-{updater.engine}-{repeater.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, updater, repeater, work))
                print(name + " import/update/reimport: passed", flush=True)
    for key in ["book_sha256", "contacts_sha256", "review_sha256"]:
        assert len({row[key] for row in observations}) == 1
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
