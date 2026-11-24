"""Analyze a complete telemetry project input or verify an exported archive, then atomically publish the report."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns
import logging

from analysis import evaluate
from documents import Document, absolute, present, publish, read
from model import Parameters, exact, parameters, series, text
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
    request: Document = read(absolute(env_get("TREND_CONFIG", "trend-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    exact(config, ["version", "mode", "input", "output"])
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = text(config["mode"])
    assert mode in ["analyze", "verify"], "unknown mode"
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
    rows: list[Json] = series(source)
    settings: Parameters = parameters(source["settings"])
    results: list[Json] = evaluate(rows, settings)
    if mode == "verify":
        assert encoded(data["results"]) == encoded(results), "archive results do not match recomputed analysis"
    publish(output, bundle(mode, source, results), [request, document])
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
