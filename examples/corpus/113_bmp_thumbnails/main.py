"""Load complete named BMP projects or their archives, then publish a reproducible contact sheet."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal job boundary and explicit returns

import logging

from documents import Document, absolute, present, publish, read
from layout import Sheet, compose
from model import Source, encoded, exact, name_of, text
from reports import bundle

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_loads_unique,
    path_parent,
    path_resolve,
    process_exit,
)


def archived_bytes(row: Json) -> bytes:
    spelling: str = text(row["source_hex"])
    assert len(spelling) <= 4194304, "image byte limit"
    data: bytes = bytes.fromhex(spelling)
    assert data.hex() == spelling, "expected canonical lowercase hex"
    return data


def run() -> None:
    request: Document = read(absolute(env_get("BMP_CONFIG", "bmp-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    mode: str = text(config["mode"])
    assert json_int(config["version"]) == 1 and mode in ["build", "verify"], "unsupported request version or mode"
    output: str = absolute(text(config["output"]), path_parent(request.path))
    assert not present(output), "output already exists"
    project: Document = read(
        absolute(text(config["input"]), path_parent(request.path)), 33554432 if mode == "verify" else 65536
    )
    definition: Json = json_loads_unique(project.data.decode())
    exact(
        definition,
        ["version", "settings", "images", "results"] if mode == "verify" else ["version", "settings", "images"],
    )
    assert json_int(definition["version"]) == 1, "unsupported project or archive version"
    rows: list[Json] = json_array(definition["images"])
    assert 1 <= len(rows) <= 16, "image count limit"
    inputs: list[Document] = [request, project]
    sources: list[Source] = []
    total_bytes: int = 0
    for row in rows:
        exact(row, ["name", "source_hex"] if mode == "verify" else ["name", "path"])
        data: bytes = archived_bytes(row) if mode == "verify" else b""
        if mode == "build":
            document: Document = read(absolute(text(row["path"]), path_parent(project.path)), 2097152)
            data = document.data
            inputs.append(document)
        total_bytes = total_bytes + len(data)
        assert total_bytes <= 8388608, "combined source byte limit"
        sources.append(Source(name_of(row["name"]), data))
    sheet: Sheet = compose(sources, definition["settings"])
    if mode == "verify":
        assert encoded(definition["results"]) == encoded(sheet.results), "archive differs from recomputed sheet"
    publish(output, bundle(mode, sources, definition["settings"], sheet), inputs)
    print(json_canonical({"images": len(sources), "width": sheet.results["width"], "height": sheet.results["height"]}))
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
