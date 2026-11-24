"""Convert a bounded batch, replay any imported notebook and publish a complete new notebook bundle."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal request boundary and explicit returns
import logging

from conversion import text
from documents import Document, absolute, present, publish, read
from notebook import attempt, exact, load
from reports import bundle
from units import Unit, catalog

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


def run() -> int:
    request: Document = read(absolute(env_get("UNITS_CONFIG", "units-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = text(config["mode"])
    assert mode in ["convert", "verify"], "unknown notebook mode"
    exact(
        config,
        (
            ["version", "mode", "notebook", "output", "conversions"]
            if mode == "convert"
            else ["version", "mode", "notebook", "output"]
        ),
    )
    base: str = path_parent(request.path)
    output: str = absolute(text(config["output"]), base)
    assert not present(output), "output already exists"
    available: dict[str, Unit] = catalog()
    entries: list[Json] = []
    inputs: list[Document] = [request]
    if config["notebook"] is not None:
        document: Document = read(absolute(text(config["notebook"]), base), 1048576)
        entries = load(json_loads_unique(document.data.decode()), available)
        inputs.append(document)
    else:
        assert mode == "convert", "verification requires a notebook"
    before: int = len(entries)
    outcomes: list[Json] = []
    if mode == "convert":
        conversions: list[Json] = json_array(config["conversions"])
        assert len(conversions) <= 64, "batch conversion limit"
        for index in range(len(conversions)):
            result: tuple[list[Json], Json] = attempt(entries, conversions[index], index, available)
            entries = result[0]
            outcomes.append(result[1])
    files: dict[str, bytes] = bundle(mode, before, entries, outcomes, available)
    publish(output, files, inputs)
    summary: Json = json_loads_unique(files["report.json"].decode())["summary"]
    print(json_canonical(summary))
    return 1 if json_int(summary["rejected"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
