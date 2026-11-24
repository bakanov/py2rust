"""Validate, execute every test, then atomically publish the full suite report."""

# ruff: noqa: I001, BLE001, LOG015 - explicit process boundary and compact runtime imports
import logging
from configuration import load
from documents import Document, absolute, publish, read
from execution import execute, skipped
from reports import render, summarize
from py2rust.stdlib import Json, env_get, json_array, json_canonical, json_int, json_string, path_resolve, process_exit


def run() -> int:
    source: Document = read(absolute(env_get("RUNNER_CONFIG", "runner-job.json"), path_resolve(".")), 2097152)
    config: Json = load(source)
    records: list[Json] = []
    files: dict[str, bytes] = {}
    interrupted: int = 0
    for case in json_array(config["tests"]):
        if interrupted != 0:
            records.append(skipped(case))
        else:
            result: tuple[Json, bytes, bytes] = execute(case)
            record: Json = result[0]
            name: str = json_string(case["id"])
            files[name + ".stdout"] = result[1]
            files[name + ".stderr"] = result[2]
            records.append(record)
            interrupted = json_int(record["outcome"]["interrupt_signal"])
            print(json_canonical({"id": name, "status": record["status"], "outcome": record["outcome"]}))
    summary: Json = summarize(records, interrupted)
    publish(json_string(config["output"]), render(records, summary, files), [source])
    print(json_canonical(summary))
    if interrupted != 0:
        return 128 + interrupted
    return 1 if json_int(summary["failed"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return  # noqa: PLR1711 - explicit repository returns


if __name__ == "__main__":
    main()
