"""Inspect job deadlines and publish a replayable report without replacing prior results."""

# ruff: noqa: BLE001, LOG015, PLR1711 - process boundary and explicit subset returns
import logging

from documents import Document, absolute, publish, read
from model import inspect
from reports import render
from schedule import Inspection, load

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_int,
    path_resolve,
    process_exit,
)


def run() -> int:
    path: str = absolute(env_get("DEADLINE_CONFIG", "deadline-job.json"), path_resolve("."))
    config: Document = read(path, 65536)
    inspection: Inspection = load(config)
    result: Json = inspect(inspection)
    files: dict[str, bytes] = render(inspection, result)
    publish(inspection.output, files, inspection.inputs)
    print(json_canonical(result))
    counts: Json = result["counts"]
    return 1 if json_int(counts["late"]) + json_int(counts["missing"]) > 0 else 0


def main() -> None:
    code: int = 2
    try:
        code = run()
    except Exception as error:
        logging.error(str(error))
    process_exit(code)
    return


if __name__ == "__main__":
    main()
