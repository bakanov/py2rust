"""Build a linked static site from immutable Markdown sources and publish it as one directory."""

# ruff: noqa: PLR1711, BLE001, LOG015, PLC0206 - explicit returns and subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from layout import document, stylesheet, validate
from markdown import Page, compile_page

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_keys,
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


def label(value: Json) -> str:
    text: str = json_string(value)
    assert 1 <= len(text) <= 128 and len(text.encode()) <= 512, "invalid title length"
    for character in text:
        assert character >= " " and character != "\x7f", "title control character"
    return text


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def run() -> None:
    mode: str = env_get("SITE_MODE", "preview")
    assert mode in ["preview", "write"], "invalid site mode"
    config: Document = read(absolute(env_get("SITE_CONFIG", "site-job.json"), path_resolve(".")), 65536)
    job: Json = json_loads(config.data.decode())
    exact(job, ["site", "output"])
    output: str = absolute(json_string(job["output"]), path_parent(config.path))
    assert not present(output), "output directory already exists"
    source: Document = read(absolute(json_string(job["site"]), path_parent(config.path)), 65536)
    manifest: Json = json_loads(source.data.decode())
    exact(manifest, ["version", "title", "pages"])
    assert json_int(manifest["version"]) == 1, "unsupported site version"
    title: str = label(manifest["title"])
    entries: list[Json] = json_array(manifest["pages"])
    assert 1 <= len(entries) <= 32, "site requires 1..32 pages"
    documents: list[Document] = [config, source]
    pages: dict[str, Page] = {}
    paths: set[str] = set()
    files: dict[str, bytes] = {}
    exported: list[Json] = []
    reports: list[Json] = []
    total: int = 0
    for entry in entries:
        exact(entry, ["id", "title", "source"])
        identifier: str = json_string(entry["id"])
        assert 1 <= len(identifier) <= 64 and identifier[0] != "-", "invalid page id length or prefix"
        for character in identifier:
            assert character in "abcdefghijklmnopqrstuvwxyz0123456789-", "invalid page id character"
        assert identifier not in pages, "duplicate page id"
        page_title: str = label(entry["title"])
        path: str = absolute(json_string(entry["source"]), path_parent(source.path))
        assert path not in paths, "duplicate page source"
        paths.add(path)
        content: Document = read(path, 65536)
        documents.append(content)
        total = total + len(content.data)
        assert total <= 1048576, "combined sources exceed 1 MiB"
        page: Page = compile_page(content.data.decode(), identifier)
        pages[identifier] = page
        filename: str = "source-" + str(len(exported)) + ".md"
        files[filename] = content.data
        exported.append({"id": identifier, "title": page_title, "source": filename})
        reports.append(
            {
                "id": identifier,
                "title": page_title,
                "headings": page.headings,
                "links": page.links,
                "source_sha256": digest(content.data),
            }
        )
    validate(pages)
    for identifier in pages:
        files[identifier + ".html"] = document(title, identifier, entries, pages[identifier]).encode()
    files["style.css"] = stylesheet().encode()
    files["site.json"] = (json_canonical({"version": 1, "title": title, "pages": exported}) + "\n").encode()
    report: Json = {"version": 1, "title": title, "entry": json_string(entries[0]["id"]) + ".html", "pages": reports}
    files["report.json"] = (json_canonical(report) + "\n").encode()
    checksums: Json = {}
    total = 0
    for name in files:
        total = total + len(files[name])
        assert total <= 16777216, "site exports exceed 16 MiB"
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
