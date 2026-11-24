"""Switch Python/native writers and readers over the same persistent artifact graph."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.artifact_store import attach, collected, imported, invoke, setup
from corpus_checks.common import Application

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, reader: Application, work: Path) -> dict:
    repo, _config = setup(work)
    invoke(writer, work, "init")
    payload = "Shared artifact 世界 😀\r\n".encode() + b"\x00\xff"
    blob = imported(writer, work, "payload.bin", payload)
    leaf = attach(
        writer,
        work,
        {"asset": blob},
        [],
        "temporary",
        metadata={"ratios": [0.1, 1e-7, 5e-324, -0.0, 1.7976931348623157e308]},
    )
    assert invoke(reader, work, "show", {"manifest": leaf})["reachable"]["blobs"] == [blob["digest"]]
    root = attach(reader, work, {}, [leaf], "release", metadata={"score": 1.1})
    assert invoke(writer, work, "show", {"manifest": root})["reachable"]["blobs"] == [blob["digest"]]
    invoke(writer, work, "unpin", {"name": "temporary", "expected": leaf})
    extra = imported(writer, work, "orphan.bin", b"unreferenced temporary upload")
    assert collected(reader, work)["removed"] == ["blobs/" + extra["digest"]]
    target = work / "download.bin"
    invoke(writer, work, "get", {"digest": blob["digest"], "destination": str(target)})
    assert target.read_bytes() == payload
    assert invoke(reader, work, "list")["references"] == {"release": root}
    invoke(reader, work, "verify")
    invoke(writer, work, "unpin", {"name": "release", "expected": root})
    assert len(collected(reader, work)["removed"]) == 3
    assert list((repo / "blobs").iterdir()) == [] and list((repo / "manifests").iterdir()) == []
    return {
        "writer": writer.engine,
        "reader": reader.engine,
        "blob": blob["digest"],
        "leaf": leaf,
        "root": root,
        "retrieved_bytes": len(payload),
        "collected_orphan": True,
        "final_nodes": 0,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "036")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "036/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current, "run current corpus checks first"
    fingerprints = {"036": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "artifact-store"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = {
        "python": Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        "rust": Application([str(BUILD / "036/corpus_036")], "rust"),
    }
    observations = []
    for writer in apps.values():
        for reader in apps.values():
            work = directory / (writer.engine + "-" + reader.engine)
            if work.exists():
                shutil.rmtree(work)
            observations.append(exercise(writer, reader, work))
            print(writer.engine + " writer / " + reader.engine + " reader: passed", flush=True)
    # Metadata formatting and graph identity must agree in all engine combinations.
    assert len({(row["blob"], row["leaf"], row["root"]) for row in observations}) == 1
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
