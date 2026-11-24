"""Publish highlighted pages, diagnostics and exact source bytes as a complete new bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711, PLC0206 - boundary errors and explicit subset operations
import logging

from documents import Document, absolute, publish, read, stamp
from lexing import describe
from pages import STYLE, index_page, render
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


def run() -> int:
    config: Document = read(absolute(env_get("HIGHLIGHT_CONFIG", "highlight-job.json"), path_resolve(".")), 65536)
    project: Project = load(config)
    reports: list[Json] = []
    entries: list[Json] = []
    files: dict[str, bytes] = {"style.css": STYLE.encode(), "index.html": index_page(project)}
    errors: int = 0
    for index in range(len(project.sources)):
        source: Source = project.sources[index]
        report: Json = describe(source.highlight)
        report["label"] = source.label
        report["page"] = "file-" + str(index) + ".html"
        report["source"] = "file-" + str(index) + ".source"
        reports.append(report)
        errors = errors + len(source.highlight.diagnostics)
        filename: str = "file-" + str(index)
        files[filename + ".html"] = render(source, index, project)
        files[filename + ".source"] = source.document.data
        entries.append({"label": source.label, "source": filename + ".source"})
    result: Json = {"version": 1, "theme": project.theme, "diagnostics": errors, "files": reports}
    files["report.json"] = (json_canonical(result) + "\n").encode()
    files["highlight-job.json"] = (
        json_canonical({"version": 1, "theme": project.theme, "files": entries, "output": "rebuilt"}) + "\n"
    ).encode()
    checksums: Json = {}
    total: int = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 16777216, "rendered bundle exceeds 16 MiB"
        checksums[name] = {"bytes": len(files[name]), "sha256": sha256_digest(sha256_update(sha256_new(), files[name]))}
    files["manifest.json"] = (json_canonical({"version": 1, "files": checksums}) + "\n").encode()
    assert json_equal(config.stamp, stamp(config.path)), "configuration changed"
    for source in project.sources:
        assert json_equal(source.document.stamp, stamp(source.document.path)), "source changed"
    publish(project.output, files)
    print(json_canonical(result))
    return 1 if errors > 0 else 0


def main() -> None:
    status: int = 2
    try:
        status = run()
    except Exception as error:
        logging.error(str(error))
    process_exit(status)
    return


if __name__ == "__main__":
    main()
