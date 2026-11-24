"""Run the whole simulation and publish a reproducible report directory."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - compact imports and explicit process-boundary returns
import logging
from configuration import load
from documents import Document, absolute, publish, read
from reports import render, summarize
from simulation import State, simulate
from workload import resolve
from py2rust.stdlib import Json, env_get, json_canonical, json_int, json_loads, json_string, path_resolve, process_exit


def run() -> int:
    path: str = absolute(env_get("SCHEDULER_CONFIG", "scheduler-job.json"), path_resolve("."))
    document: Document = read(path, 262144)
    config: Json = load(document)
    resolved: tuple[list[Json], Json] = resolve(config["workload"])
    jobs: list[Json] = resolved[0]
    # Copy explicitly so CPython and the executable subset share value semantics.
    snapshot: list[Json] = []
    for job in jobs:
        snapshot.append(json_loads(json_canonical(job)))
    workers: int = json_int(config["workers"])
    state: State = simulate(snapshot, workers, json_int(config["queue_capacity"]))
    summary: Json = summarize(state, workers, resolved[1])
    output: str = json_string(config["output"])
    publish(output, render(config, jobs, state, summary), [document])
    print(json_canonical(summary))
    return 0


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
