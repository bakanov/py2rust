"""Compile a manifest's templates, render named jobs, and publish reproducible source and output files."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and supported subset operations
import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from graph import validate
from render import Rendered, render
from syntax import Node, compile_template, identifier, includes, node_count

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def exact(value: Json, fields: list[str]) -> None:
    assert json_keys(value) == sorted(fields), "unexpected object fields"
    return


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def run() -> None:
    mode: str = env_get("TEMPLATE_MODE", "preview")
    assert mode in ["preview", "write"], "invalid template mode"
    config: Document = read(absolute(env_get("TEMPLATE_CONFIG", "template-job.json"), path_resolve(".")), 65536)
    job: Json = json_loads(config.data.decode())
    exact(job, ["project", "output"])
    output: str = absolute(json_string(job["output"]), path_parent(config.path))
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(job["project"]), path_parent(config.path)), 65536)
    manifest: Json = json_loads(source.data.decode())
    exact(manifest, ["version", "templates", "jobs"])
    assert json_int(manifest["version"]) == 1, "unsupported template version"
    entries: list[Json] = json_array(manifest["templates"])
    jobs: list[Json] = json_array(manifest["jobs"])
    assert 1 <= len(entries) <= 32 and 1 <= len(jobs) <= 32, "template/job count outside 1..32"
    documents: list[Document] = [config, source]
    templates: dict[str, list[Node]] = {}
    graph: dict[str, dict[str, str]] = {}
    files: dict[str, bytes] = {}
    exported: list[Json] = []
    paths: set[str] = set()
    total: int = 0
    syntax_nodes: int = 0
    for entry in entries:
        exact(entry, ["id", "source"])
        name: str = json_string(entry["id"])
        assert len(name) <= 64 and identifier(name), "invalid template id"
        assert name not in templates, "duplicate template id"
        path: str = absolute(json_string(entry["source"]), path_parent(source.path))
        assert path not in paths, "duplicate template source"
        paths.add(path)
        content: Document = read(path, 65536)
        documents.append(content)
        total = total + len(content.data)
        assert total <= 1048576, "combined template sources exceed 1 MiB"
        templates[name] = compile_template(content.data.decode(), name)
        syntax_nodes = syntax_nodes + node_count(templates[name])
        assert syntax_nodes <= 4096, name + ": combined syntax nodes exceed 4096"
        graph[name] = includes(templates[name])
        filename: str = "source-" + str(len(exported)) + ".txt"
        files[filename] = content.data
        exported.append({"id": name, "source": filename})
    validate(graph)
    reports: list[Json] = []
    exported_jobs: list[Json] = []
    names: set[str] = set()
    for item in jobs:
        exact(item, ["id", "template", "data", "steps"])
        name: str = json_string(item["id"])
        assert len(name) <= 64 and identifier(name) and name not in names, "invalid or duplicate job id"
        names.add(name)
        target: str = json_string(item["template"])
        assert target in templates, "job references unknown template"
        budget: int = json_int(item["steps"])
        assert 0 <= budget <= 10000, "step budget outside 0..10000"
        data: Document = read(absolute(json_string(item["data"]), path_parent(source.path)), 1048576)
        documents.append(data)
        total = total + len(data.data)
        assert total <= 4194304, "combined input bytes exceed 4 MiB"
        value: Json = json_loads(data.data.decode())
        assert json_kind(value) == "object", "job data must be an object"
        scope: dict[str, Json] = {}
        for key in json_keys(value):
            scope[key] = value[key]
        result: Rendered = render(templates[target], templates, scope, budget, 0)
        files[name + ".html"] = result.text.encode()
        filename: str = "data-" + str(len(exported_jobs)) + ".json"
        files[filename] = data.data
        exported_jobs.append({"id": name, "template": target, "data": filename, "steps": budget})
        reports.append(
            {
                "id": name,
                "template": target,
                "steps": result.steps,
                "bytes": len(result.text.encode()),
                "sha256": digest(result.text.encode()),
            }
        )
    files["project.json"] = (
        json_canonical({"version": 1, "templates": exported, "jobs": exported_jobs}) + "\n"
    ).encode()
    report: Json = {"version": 1, "templates": len(entries), "jobs": reports}
    files["report.json"] = (json_canonical(report) + "\n").encode()
    checksums: Json = {}
    total = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 16777216, "exports exceed 16 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = (pretty({"version": 1, "files": checksums}) + "\n").encode()
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(json_canonical(report))
    return


def main() -> None:
    try:
        run()
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
