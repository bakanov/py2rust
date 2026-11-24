"""Generate and apply exact text patches as one complete transpiled project."""

# ruff: noqa: BLE001, LOG015, PLR1711 - explicit error boundary
import logging
from dataclasses import dataclass

from alignment import create
from documents import Document, absolute, present, publish, read
from patching import apply
from reports import bundle, encoded
from text_model import exact, integer

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    json_loads_unique,
    json_string,
    path_parent,
    path_resolve,
    process_exit,
)


@dataclass
class Prepared:
    after: bytes
    patch: Json
    serialized: bytes


def prepare(config: Json, before: bytes, other: bytes) -> Prepared:
    if json_string(config["mode"]) == "diff":
        context: int = integer(config["context"], 0, 16)
        patch: Json = create(before, other, context)
        return Prepared(other, patch, encoded(patch))
    parsed: Json = json_loads_unique(other.decode())
    return Prepared(apply(before, parsed), parsed, other)


def run() -> int:
    document: Document = read(absolute(env_get("PATCH_CONFIG", "patch-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(document.data.decode())
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = json_string(config["mode"])
    assert mode in ["diff", "apply"], "unknown patch operation"
    if mode == "diff":
        exact(config, ["version", "mode", "base", "target", "context", "output"])
    else:
        exact(config, ["version", "mode", "base", "patch", "output"])
    parent: str = path_parent(document.path)
    output: str = absolute(json_string(config["output"]), parent)
    assert not present(output), "output already exists"
    before: Document = read(absolute(json_string(config["base"]), parent), 65536)
    other: Document = read(
        absolute(json_string(config["target"] if mode == "diff" else config["patch"]), parent),
        65536 if mode == "diff" else 1048576,
    )
    prepared: Prepared = prepare(config, before.data, other.data)
    files: dict[str, bytes] = bundle(mode, before.data, prepared.after, prepared.patch, prepared.serialized)
    publish(output, files, [document, before, other])
    print(json_canonical(json_loads_unique(files["report.json"].decode())["statistics"]))
    return 1 if mode == "diff" and before.data != prepared.after else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
