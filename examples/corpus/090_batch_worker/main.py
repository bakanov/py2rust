"""Run bounded batches under one lock; acknowledge only durable completed prefixes."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - explicit process boundary and subset returns
import logging
from configuration import binding, integer, jobs, load
from files import Document, absolute, checkpoint, inside, present, read, regular, unchanged
from jobs import summarize, transform
from storage import finish, load as load_state, save
from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_array,
    json_canonical,
    json_int,
    json_loads_unique,
    json_string,
    path_join,
    path_resolve,
    process_exit,
)


def status(state: Json, total: int, phase: str) -> None:
    print(
        json_canonical({"status": phase, "completed": state["completed"], "total": total, "summary": state["summary"]})
    )
    return


def run() -> None:
    document: Document = read(absolute(env_get("BATCH_CONFIG", "batch-job.json"), path_resolve(".")), 65536)
    config: Json = load(document)
    source: Document = read(json_string(config["input"]), 1048576)
    workload: list[Json] = jobs(source)
    inputs: list[Document] = [document, source]
    root: str = json_string(config["output"])
    limit: int = integer(json_loads_unique(env_get("BATCH_LIMIT", "0")), 0, 256)
    stop: str = env_get("BATCH_STOP", "")
    if stop != "":
        stop = absolute(stop, path_resolve("."))
        assert not inside(stop, root) and stop not in [root + ".lock", document.path, source.path], "stop overlaps data"
    lock: str = root + ".lock"
    if present(lock):
        regular(lock)
    with file_lock(lock) as _guard:
        regular(lock)
        state: Json = load_state(root, binding(source, len(workload)), workload)
        if not present(path_join(root, "state.json")):
            checkpoint("initial", 0)
            save(root, state, inputs)
        batches: int = 0
        while json_int(state["completed"]) < len(workload):
            if stop != "" and present(stop):
                regular(stop)
                status(state, len(workload), "cancelled")
                return
            if limit > 0 and batches >= limit:
                status(state, len(workload), "paused")
                return
            results: list[Json] = json_array(state["results"])
            end: int = min(len(workload), len(results) + json_int(config["batch_size"]))
            for index in range(len(results), end):
                results.append(transform(workload[index]))
            state["results"] = results
            state["completed"] = end
            state["summary"] = summarize(results)
            checkpoint("computed", end)
            save(root, state, inputs)
            status(state, len(workload), "progress")
            batches = batches + 1
        unchanged(inputs)
        finish(root, state, inputs)
        status(state, len(workload), "complete")
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
