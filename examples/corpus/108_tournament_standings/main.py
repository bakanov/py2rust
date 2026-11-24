"""Rank a complete tournament or verify exported standings, then publish a reusable bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns
import logging

from documents import Document, absolute, present, publish, read
from model import exact, parse, text
from reports import bundle, encoded, summary
from standings import calculate

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
    request: Document = read(absolute(env_get("TOURNAMENT_CONFIG", "tournament-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = text(config["mode"])
    assert mode in ["rank", "verify"], "unknown mode"
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(text(config["input"]), base), 16777216 if mode == "verify" else 2097152)
    data: Json = json_loads_unique(document.data.decode())
    source: Json = data
    if mode == "verify":
        exact(data, ["version", "source", "results"])
        assert json_int(data["version"]) == 1, "unsupported archive version"
        source = data["source"]
    results: Json = calculate(parse(source))
    if mode == "verify":
        assert encoded(data["results"]) == encoded(results), "archive results do not match recomputed standings"
    publish(output, bundle(mode, source, results), [request, document])
    print(json_canonical(summary(results)))
    return 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
