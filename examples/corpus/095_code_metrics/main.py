"""Build a static project browser and raw source archive from a complete source-tree snapshot."""
# ruff: noqa: I001, BLE001, LOG015, PLR1711, PLC0206 - compact imports and application boundary
import logging
from documents import Document, absolute, publish, read
from links import connect
from metrics import analyze
from pages import overview, render
from project import Project, Source, digest, load
from py2rust.stdlib import (
    Json, base64_encode, env_get, json_canonical, json_int, json_string, path_resolve, process_exit,
)


def run() -> None:
    config: Document = read(absolute(env_get("METRICS_CONFIG", "metrics-job.json"), path_resolve(".")), 65536)
    project: Project = load(config)
    modules: list[Json] = []
    for index in range(len(project.sources)):
        modules.append(analyze(project.sources[index], "module-" + str(index) + ".html", project.thresholds))
    modules = connect(modules)
    summary: Json = {"modules": len(modules), "functions": 0, "classes": 0, "statements": 0, "flagged_functions": 0}
    files: dict[str, bytes] = {}
    archive: list[Json] = []
    inputs: list[Document] = [config]
    for index in range(len(modules)):
        module: Json = modules[index]
        source: Source = project.sources[index]
        for key in ["functions", "classes", "statements", "flagged_functions"]:
            summary[key] = json_int(summary[key]) + json_int(module[key])
        files[json_string(module["page"])] = render(source, module, modules)
        archive.append({"path": source.relative, "data": base64_encode(source.document.data)})
        inputs.append(source.document)
    report: Json = {"version": 1, "package": project.prefix, "thresholds": project.thresholds,
                    "summary": summary, "modules": modules}
    files["index.html"] = overview(modules, summary)
    files["report.json"] = (json_canonical(report) + "\n").encode()
    snapshot: Json = {"version": 1, "package": project.prefix, "exclude": project.excluded,
                      "thresholds": project.thresholds, "files": archive}
    files["sources.json"] = (json_canonical(snapshot) + "\n").encode()
    manifest: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 16777216, "report bundle exceeds 16 MiB"
        manifest[name] = {"bytes": len(files[name]), "sha256": digest(files[name])}
    files["manifest.json"] = (json_canonical(manifest) + "\n").encode()
    publish(project.output, files, inputs, project.root, project.excluded, project.paths)
    print(json_canonical(summary))
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
