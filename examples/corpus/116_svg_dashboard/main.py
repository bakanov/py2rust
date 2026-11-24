"""Load a complete dashboard job or recompute and verify its portable archive."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal job boundary and explicit returns

import logging

from charts import calculate
from documents import Document, absolute, present, publish, read
from model import encoded, exact, text
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


def run() -> None:
    request: Document = read(absolute(env_get("DASHBOARD_CONFIG", "dashboard-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    mode: str = text(config["mode"])
    assert json_int(config["version"]) == 1 and mode in ["render", "verify"], "unsupported request version or mode"
    exact(
        config,
        (
            ["version", "mode", "input", "output", "columns"]
            if mode == "render"
            else ["version", "mode", "input", "output"]
        ),
    )
    output: str = absolute(text(config["output"]), path_parent(request.path))
    assert not present(output), "output already exists"
    document: Document = read(
        absolute(text(config["input"]), path_parent(request.path)), 16777216 if mode == "verify" else 2097152
    )
    source: bytes = document.data
    columns: int = json_int(config["columns"]) if mode == "render" else 1
    definition: Json = None
    if mode == "verify":
        definition = json_loads_unique(source.decode())
        exact(definition, ["version", "source_hex", "columns", "results"])
        assert json_int(definition["version"]) == 1, "unsupported archive version"
        spelling: str = text(definition["source_hex"])
        assert len(spelling) <= 4194304, "source byte limit"
        source = bytes.fromhex(spelling)
        assert source.hex() == spelling, "expected canonical lowercase hex"
        columns = json_int(definition["columns"])
    results: Json = calculate(json_loads_unique(source.decode()), columns)
    if mode == "verify":
        assert encoded(definition["results"]) == encoded(results), "archive differs from recomputed dashboard"
    publish(output, bundle(mode, source, columns, results), [request, document])
    print(json_canonical({"width": results["width"], "height": results["height"]}))
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
