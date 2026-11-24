"""Inspect or apply a complete source-header manifest without modifying the source files."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - compact imports and explicit application boundary
import logging
from configuration import Job, load
from documents import absolute, publish, read
from reports import build
from py2rust.stdlib import (
    Json, env_get, json_canonical, json_int, path_resolve, process_exit,
)


def run() -> int:
    request: str = absolute(env_get("HEADERS_CONFIG", "headers-job.json"), path_resolve("."))
    job: Job = load(read(request, 65536))
    result: tuple[dict[str, bytes], Json] = build(job)
    publish(job.output, result[0], job.inputs)
    print(json_canonical(result[1]))
    return 0 if json_int(result[1]["remaining"]) == 0 else 1


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
