"""Rebuild and edit exported templates and JSON data across Python/Rust engines."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from corpus import CORPUS, evidence_root, fingerprint
from corpus_checks.common import Application
from corpus_checks.template_renderer import (
    fixture,
    inputs,
    sample,
    sample_expected,
    success,
)

# Match the default typed fingerprint and verified native executables.
BUILD = evidence_root("typed")


def exercise(writer: Application, updater: Application, reader: Application, directory: Path) -> dict:
    first = fixture(directory, "first", *sample())
    original = success(writer, first, sample_expected())
    files = {path.name: path.read_bytes() for path in first.output.iterdir()}
    second = fixture(directory, "second", {}, [], project=str(first.output / "project.json"))
    assert success(updater, second, sample_expected()) == original
    third = fixture(directory, "third", {}, [], project=str(second.output / "project.json"))
    assert success(reader, third, sample_expected()) == original
    assert files == {path.name: path.read_bytes() for path in third.output.iterdir()}
    project, templates, data = inputs(third)
    templates["item"] = b"<li><b>{{ item.name }}</b>: {% if item.done %}done{% else %}<i>pending</i>{% endif %}</li>"
    value = json.loads(data["index"])
    value["title"] = 'Updated <notes> & "files"'
    value["items"].append({"name": "Image <&>", "done": False})
    tasks = [
        (row["id"], row["template"], json.dumps(value, ensure_ascii=False).encode(), row["steps"])
        for row in project["jobs"]
    ]
    edited = fixture(directory, "edited", templates, tasks)
    expected = {
        "index": (
            "<h1>Updated &lt;notes&gt; &amp; &quot;files&quot;</h1>\n<ul><li><b>First</b>: done</li><li><b>世界</b>: <i>pending</i></li><li><b>Image &lt;&amp;&gt;</b>: <i>pending</i></li></ul>\nouter binding preserved\n",
            34,
        )
    }
    changed = success(updater, edited, expected)
    final = fixture(directory, "final", {}, [], project=str(edited.output / "project.json"))
    assert success(reader, final, expected) == changed
    assert {path.name: path.read_bytes() for path in edited.output.iterdir()} == {
        path.name: path.read_bytes() for path in final.output.iterdir()
    }
    assert files == {path.name: path.read_bytes() for path in first.output.iterdir()}
    return {
        "writer": writer.engine,
        "updater": updater.engine,
        "reader": reader.engine,
        "html_sha256": hashlib.sha256(files["index.html"]).hexdigest(),
        "edited_sha256": hashlib.sha256((final.output / "index.html").read_bytes()).hexdigest(),
        "actual_export_paths": True,
        "edited_include_and_json_data": True,
        "preserved_source_bytes": True,
        "unchanged_source_bundles": True,
    }


def main() -> int:
    program = next(row for row in json.loads((CORPUS / "catalog.json").read_text())["programs"] if row["id"] == "073")
    current = fingerprint(program)
    evidence = json.loads((BUILD / "073/result.json").read_text())
    assert evidence["status"] == "verified" and evidence["fingerprint"] == current
    fingerprints = {"073": current}
    checker_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    directory = BUILD / "template-renderer"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / "result.json"
    report.write_text(
        json.dumps({"status": "in_progress", "fingerprints": fingerprints, "checker_sha256": checker_hash})
    )
    apps = [
        Application([sys.executable, "-u", str(CORPUS / program["path"] / "main.py")], "python"),
        Application([str(BUILD / "073/corpus_073")], "rust"),
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
                print(name + " template exported source/data and edited include: passed", flush=True)
    for field in ["html_sha256", "edited_sha256"]:
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
