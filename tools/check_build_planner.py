"""Consume canonical graph/request exports with every Python/Rust engine combination."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.build_planner import fixture, jobs, request, sample, success
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, selector: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", sample(), jobs())
    original = success(writer, first)
    assert original["cyclic"] == 1
    first_bytes = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(
        directory,
        "second",
        {},
        [request("release-only", ["package", "package"]), request("cycle", ["blocked"]), request("none", [])],
        graph=str(first.output / "graph.json"),
    )
    selected = success(selector, second)
    assert selected["plans"][0]["status"] == "ready"
    assert selected["plans"][1]["requires_path"] == ["blocked", "cycle-a"]
    assert (second.output / "graph.json").read_bytes() == first_bytes["graph.json"]
    third = fixture(
        directory,
        "third",
        {},
        [],
        graph=str(second.output / "graph.json"),
        requests=str(second.output / "requests.json"),
    )
    assert success(reader, third) == selected
    for path in second.output.iterdir():
        assert path.read_bytes() == (third.output / path.name).read_bytes()
    assert {path.name: path.read_bytes() for path in first.output.iterdir()} == first_bytes
    repaired_graph = json.loads((third.output / "graph.json").read_bytes())
    repaired_graph["edges"] = [
        row for row in repaired_graph["edges"] if row != {"target": "cycle-b", "requires": "cycle-a"}
    ]
    repaired_graph["edges"].append({"target": "cycle-b", "requires": "generate"})
    repaired = fixture(
        directory,
        "repaired",
        repaired_graph,
        [],
        requests=str(third.output / "requests.json"),
    )
    report = success(reader, repaired)
    assert report["cyclic"] == 0
    assert report["plans"][1]["order"] == ["generate", "cycle-b", "cycle-a", "blocked"]
    return {
        "writer": writer.engine,
        "selector": selector.engine,
        "reader": reader.engine,
        "graph_sha256": hashlib.sha256(first_bytes["graph.json"]).hexdigest(),
        "plan_sha256": hashlib.sha256((third.output / "plan.json").read_bytes()).hexdigest(),
        "repaired_sha256": hashlib.sha256((repaired.output / "plan.json").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "062")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "062/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"062": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "build-planner"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "062/corpus_062")], "rust"),
    ]
    observations = []
    for writer in apps:
        for selector in apps:
            for reader in apps:
                name = f"{writer.engine}-{selector.engine}-{reader.engine}"
                work = directory / name
                if work.exists():
                    shutil.rmtree(work)
                observations.append(exercise(writer, selector, reader, work))
                print(name + " graph export/reselection/replanning: passed", flush=True)
    for field in ["graph_sha256", "plan_sha256", "repaired_sha256"]:
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
