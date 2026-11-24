"""Solve a circuit collection or independently replay an archive, then publish a complete report bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns

import logging

from documents import Document, absolute, present, publish, read
from model import cases, exact, text
from reduction import evaluate
from reports import bundle, encoded, summary

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
    request: Document = read(absolute(env_get("CIRCUIT_CONFIG", "circuit-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = text(config["mode"])
    assert mode in ["solve", "verify"], "unknown mode"
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    document: Document = read(absolute(text(config["input"]), base), 4194304 if mode == "verify" else 1048576)
    source: Json = json_loads_unique(document.data.decode())
    if mode == "verify":
        exact(source, ["version", "cases", "results"])
    rows: list[Json] = cases({"version": source["version"], "cases": source["cases"]})
    if mode == "solve":
        exact(source, ["version", "cases"])
    results: list[Json] = evaluate(rows)
    if mode == "verify":
        assert encoded(source["results"]) == encoded(results), "archive results do not match recomputed reductions"
    files: dict[str, bytes] = bundle(mode, rows, results)
    publish(output, files, [request, document])
    counts: Json = summary(results)
    print(json_canonical(counts))
    return 1 if json_int(counts["rejected"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
