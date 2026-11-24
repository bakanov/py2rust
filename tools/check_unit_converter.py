"""Exchange actual unit-conversion notebooks, continuation requests and replay across all eight engine combinations."""

import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.unit_converter import consume, files_at, fixture, run, save
from corpus_checks.units_fixture import canonical, conversion, digest, fixtures

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], root: Path) -> None:
    root.mkdir(parents=True)
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    return  # noqa: PLR1711


def exercise(writer: Application, follower: Application, verifier: Application, root: Path) -> dict:
    first = root / "writer"
    rows = fixtures()
    original_entries, _ = run(writer, first, fixture(first, rows), ["converted"] * len(rows))
    original = files_at(first / "output")
    second = root / "follower"
    restore(original, second)
    unchanged, _ = consume(follower, second, "continue.json", original_entries)
    assert unchanged == original_entries
    next_request = json.loads(original["continue.json"])
    more = [
        conversion("continued_length", "12.5 ft", "m"),
        conversion("continued_heat", "212 degF", "degC"),
        rows[0],
        conversion("incompatible", "1 kg", "m"),
    ]
    next_request.update(output="advanced", conversions=more)
    save(second / "next.json", next_request)
    advanced, report = run(
        follower,
        second,
        next_request,
        ["converted", "converted", "duplicate", "rejected"],
        original_entries,
        "next.json",
        reasons={3: "incompatible dimensions"},
    )
    assert report["summary"] == {"converted": 2, "duplicate": 1, "rejected": 1}
    advanced_files = files_at(second / "advanced")
    third = root / "verifier"
    restore(advanced_files, third)
    verified, _ = consume(verifier, third, "replay.json", advanced)
    assert verified == advanced
    reverse = [
        conversion(
            "reverse" + str(i),
            canonical(row["result"]["converted"]).decode().strip() + " " + row["request"]["to"],
            row["result"]["source_unit"],
        )
        for i, row in enumerate(advanced[-2:])
    ]
    followup = json.loads(advanced_files["continue.json"])
    followup["conversions"] = reverse
    save(third / "reverse.json", followup)
    reversed_entries, _ = run(verifier, third, followup, ["converted", "converted"], advanced, "reverse.json")
    for original_entry, back in zip(advanced[-2:], reversed_entries[-2:]):
        original_value, recovered = original_entry["result"]["value"], back["result"]["converted"]
        assert abs(original_value - recovered) <= max(1e-12, abs(original_value) * 1e-12)
    assert (second / "notebook.json").read_bytes() == original["notebook.json"]
    assert files_at(first / "output") == original and files_at(second / "advanced") == advanced_files
    assert (third / "notebook.json").read_bytes() == advanced_files["notebook.json"]
    return {
        "writer": writer.engine,
        "follower": follower.engine,
        "verifier": verifier.engine,
        "actual_notebooks_and_requests_consumed": True,
        "imported_history_preserved": True,
        "cross_engine_reverse_conversions": True,
        "duplicate_and_incompatible_rows_checked": True,
        "initial_entries": len(original_entries),
        "continued_entries": len(advanced),
        "initial_notebook_sha256": digest(original["notebook.json"]),
        "continued_notebook_sha256": digest(advanced_files["notebook.json"]),
        "reverse_notebook_sha256": digest(canonical({"version": 1, "entries": reversed_entries})),
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "103")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "103/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    directory = BUILD / "unit-converter"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = digest(Path(__file__).read_bytes())
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"103": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "103/corpus_103")], "rust"),
    ]
    observations = []
    for writer in apps:
        for follower in apps:
            for verifier in apps:
                name = f"{writer.engine}-{follower.engine}-{verifier.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, follower, verifier, work))
                print(name + " unit notebook exchange: passed", flush=True)
    for key in ["initial_notebook_sha256", "continued_notebook_sha256", "reverse_notebook_sha256"]:
        assert all(row[key] == observations[0][key] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"103": current},
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
