"""Audit a complete ZIP project or replay a bounded, source-preserving inspection bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns
import logging

from binary import encoded, exact, limits, text
from documents import Document, absolute, present, publish, read
from inspect_zip import inspect
from reports import bundle

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
    request: Document = read(absolute(env_get("ZIP_CONFIG", "zip-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    mode: str = text(config["mode"])
    assert json_int(config["version"]) == 1 and mode in ["inspect", "verify"], "request version or mode"
    fields: list[str] = ["version", "mode", "input", "output"]
    if mode == "inspect":
        fields.append("limits")
    exact(config, fields)
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(text(config["input"]), base), 67108864 if mode == "verify" else 16777216)
    source: bytes = document.data
    archive: Json = None
    settings: Json = limits(config["limits"]) if mode == "inspect" else None
    if mode == "verify":
        archive = json_loads_unique(source.decode())
        exact(archive, ["version", "source_hex", "limits", "results"])
        assert json_int(archive["version"]) == 1, "archive version"
        spelling: str = text(archive["source_hex"])
        assert len(spelling) <= 33554432, "source byte limit"
        source = bytes.fromhex(spelling)
        assert source.hex() == spelling, "expected canonical lowercase hex"
        settings = limits(archive["limits"])
    results: Json = inspect(source, settings)
    if mode == "verify":
        assert encoded(archive["results"]) == encoded(results), "archive findings differ from recomputed inspection"
    publish(output, bundle(mode, source, settings, results), [request, document])
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
