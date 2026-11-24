"""Load complete named sprite projects or their archives, then publish a reproducible sprite atlas."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal job boundary and explicit returns

import logging

from documents import Document, absolute, present, publish, read
from model import Sprite, encoded, exact, name_of, text
from packing import Atlas, pack
from ppm import decode
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
    assert len(spelling) <= 1048576, "image byte limit"
    data: bytes = bytes.fromhex(spelling)
    assert data.hex() == spelling, "expected canonical lowercase hex"
    return data


def run() -> None:
    request: Document = read(absolute(env_get("ATLAS_CONFIG", "atlas-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    mode: str = text(config["mode"])
    assert json_int(config["version"]) == 1 and mode in ["pack", "verify"], "unsupported request version or mode"
    output: str = absolute(text(config["output"]), path_parent(request.path))
    assert not present(output), "output already exists"
    project: Document = read(
        absolute(text(config["input"]), path_parent(request.path)), 33554432 if mode == "verify" else 65536
    )
    definition: Json = json_loads_unique(project.data.decode())
    exact(
        definition,
        ["version", "settings", "sprites", "results"] if mode == "verify" else ["version", "settings", "sprites"],
    )
    assert json_int(definition["version"]) == 1, "unsupported project or archive version"
    rows: list[Json] = json_array(definition["sprites"])
    assert 1 <= len(rows) <= 64, "sprite count limit"
    inputs: list[Document] = [request, project]
    sprites: list[Sprite] = []
    names: set[str] = set()
    total_bytes: int = 0
    for row in rows:
        exact(row, ["name", "source_hex"] if mode == "verify" else ["name", "path"])
        data: bytes = archived_bytes(row) if mode == "verify" else b""
        if mode == "pack":
            document: Document = read(absolute(text(row["path"]), path_parent(project.path)), 524288)
            data = document.data
            inputs.append(document)
        total_bytes = total_bytes + len(data)
        assert total_bytes <= 8388608, "combined source byte limit"
        name: str = name_of(row["name"])
        assert name not in names, "duplicate sprite name"
        names.add(name)
        sprites.append(Sprite(len(sprites), name, data, decode(data)))
    atlas: Atlas = pack(sprites, definition["settings"])
    if mode == "verify":
        assert encoded(definition["results"]) == encoded(atlas.results), "archive differs from recomputed atlas"
    publish(output, bundle(mode, sprites, definition["settings"], atlas), inputs)
    print(json_canonical({"sprites": len(sprites), "width": atlas.results["width"], "height": atlas.results["height"]}))
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
