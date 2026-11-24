"""Exchange actual diff/apply/check artifacts across all eight Python/Rust combinations."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.patch_fixture import digest, fixtures
from corpus_checks.text_patch import consume, fixture, request, run, save, snapshot

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def restore(files: dict[str, bytes], directory: Path) -> None:
    directory.mkdir(parents=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return  # noqa: PLR1711


def exercise(writer: Application, applier: Application, checker: Application, root: Path) -> dict:
    available = fixtures()
    selected = ["mixed", "tie", "unicode", "nul-controls", "newline-remove", "empty"]
    hashes = {}
    for number, name in enumerate(selected):
        before, after = available[name]
        work = root / name
        first = work / "first"
        initial = run(writer, first, fixture(first, before, after, number % 4), after)
        original = snapshot(first / "output")
        second = work / "second"
        restore(original, second)
        applied, output = consume(applier, second, "apply.json", after)
        assert applied["statistics"] == initial["statistics"]
        assert (output / "result.txt").read_bytes() == after
        corrected = snapshot(output)
        third = work / "third"
        restore(original, third)
        restore(corrected, third / "applied")
        checked, checked_output = consume(checker, third, "check-applied.json", after)
        assert checked["changed"] is False and checked["statistics"]["added"] == checked["statistics"]["removed"] == 0
        assert json.loads((checked_output / "patch.json").read_bytes())["hunks"] == []
        regenerated, regenerated_output = consume(checker, third / "applied", "recheck.json", after)
        assert regenerated["statistics"] == initial["statistics"]
        assert (regenerated_output / "patch.json").read_bytes() == original["patch.json"]
        replayed, replay_output = consume(checker, second, "replay.json", after)
        assert replayed == initial and snapshot(replay_output) == original
        assert snapshot(first / "output") == original and snapshot(output) == corrected
        if before != after:
            retry = request("apply", "reapplied", "result.txt", "patch.json")
            save(third / "applied/retry.json", retry)
            result = checker.run(third / "applied", {"PATCH_CONFIG": str(third / "applied/retry.json")})
            assert result.returncode == 2 and "base identity mismatch" in result.stderr and not result.stdout
            assert not (third / "applied/reapplied").exists()
        hashes[name] = digest(original["patch.json"])
    return {
        "writer": writer.engine,
        "applier": applier.engine,
        "checker": checker.engine,
        "fixture_pairs": len(selected),
        "actual_patches_and_requests_consumed": True,
        "result_bytes_equal_original_target": True,
        "check_after_apply_has_zero_changes": True,
        "regenerated_patches_and_replay_bundles_identical": True,
        "changed_result_reapplication_rejected": True,
        "patch_sha256": hashes,
    }


def main() -> int:
    program = next(p for p in json.loads((CORPUS / "catalog.json").read_text())["programs"] if p["id"] == "100")
    current = fingerprint(program)
    result = json.loads((BUILD / "100/result.json").read_text())
    assert result["status"] == "verified" and result["fingerprint"] == current
    directory = BUILD / "text-patch"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "result.json"
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.write_text(
        json.dumps({"status": "in_progress", "fingerprints": {"100": current}, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "100/corpus_100")], "rust"),
    ]
    observations = []
    for writer in apps:
        for applier in apps:
            for checker in apps:
                name = f"{writer.engine}-{applier.engine}-{checker.engine}"
                root = directory / name
                if root.exists():
                    shutil.rmtree(root)
                observations.append(exercise(writer, applier, checker, root))
                print(name + " text patch exchange: passed", flush=True)
    assert all(row["patch_sha256"] == observations[0]["patch_sha256"] for row in observations)
    assert fingerprint(program) == current
    output.write_text(
        json.dumps(
            {
                "status": "passed",
                "fingerprints": {"100": current},
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
