"""Inspect a complete PNG or replay its archive; publish forensic findings even for malformed images."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns

import logging

from binary import encoded, exact, text
from documents import Document, absolute, present, publish, read
from reports import bundle
from scan import inspect

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    json_loads_unique,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> int:
    request: Document = read(absolute(env_get("PNG_CONFIG", "png-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = text(config["mode"])
    assert mode in ["inspect", "verify"], "unknown mode"
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(text(config["input"]), base), 67108864 if mode == "verify" else 16777216)
    source: bytes = document.data
    archive: Json = None
    if mode == "verify":
        archive = json_loads_unique(source.decode())
        exact(archive, ["version", "source_hex", "results"])
        assert json_int(archive["version"]) == 1, "unsupported archive version"
        spelling: str = text(archive["source_hex"])
        assert len(spelling) <= 33554432, "source byte limit"
        source = bytes.fromhex(spelling)
        assert source.hex() == spelling, "expected canonical lowercase hex"
    results: Json = inspect(source)
    if mode == "verify":
        assert encoded(archive["results"]) == encoded(results), "archive findings differ from recomputed inspection"
    publish(output, bundle(mode, source, results), [request, document])
    print(json_canonical(results["summary"]))
    return 1 if json_int(results["summary"]["errors"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
