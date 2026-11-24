"""Publish a complete source browser and a reusable source snapshot atomically."""

# ruff: noqa: BLE001, LOG015, PLR1711, PLC0206 - boundary errors and explicit subset operations
import logging

from documents import Document, absolute, publish, read, stamp
from outline import connect, describe
from pages import index_page, render
from project import Project, Source, load

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_equal,
    path_resolve,
    process_exit,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def run() -> None:
    config: Document = read(absolute(env_get("OUTLINE_CONFIG", "outline-project.json"), path_resolve(".")), 1048576)
    project: Project = load(config)
    modules: list[Json] = []
    for source in project.modules:
        modules.append(describe(source))
    modules = connect(modules)
    files: dict[str, bytes] = {}
    entries: list[Json] = []
    for index in range(len(project.modules)):
        source: Source = project.modules[index]
        files["module-" + source.name + ".html"] = render(source, modules[index], modules)
        filename: str = "source-" + source.name + ".py"
        files[filename] = source.document.data
        entries.append({"name": source.name, "source": filename, "package": source.package})
    report: Json = {"version": 1, "modules": modules}
    files["index.html"] = index_page(modules)
    files["report.json"] = (json_canonical(report) + "\n").encode()
    files["project.json"] = (json_canonical({"version": 1, "modules": entries, "output": "rebuilt"}) + "\n").encode()
    checksums: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 16777216, "rendered bundle exceeds 16 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": checksums}) + "\n").encode()
    assert json_equal(config.stamp, stamp(config.path)), "configuration changed"
    for source in project.modules:
        assert json_equal(source.document.stamp, stamp(source.document.path)), "source changed"
    publish(project.output, files)
    print(json_canonical(report))
    return


def main() -> None:
    status: int = 0
    try:
        run()
    except Exception as error:
        logging.error(str(error))
        status = 2
    process_exit(status)
    return


if __name__ == "__main__":
    main()
