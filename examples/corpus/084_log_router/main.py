"""Poll several append-only logs; persist filtered positions and durable JSONL segments."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: BLE001, LOG015, PLR1711 - process boundary and explicit subset returns
import logging

from config import configuration, integer
from files import absolute, present, regular
from reading import collect
from routing import route
from storage import commit, open_store

from py2rust.stdlib import (
    Json, env_get, file_lock, json_canonical, json_loads, json_string, log, log_configure, path_resolve,
    process_exit, sleep
)


def run() -> None:
    config: Json = configuration()
    polls: int = integer(json_loads(env_get("ROUTER_POLLS", "1")), 0, 100000)
    interval: int = integer(json_loads(env_get("ROUTER_INTERVAL_MS", "250")), 10, 60000)
    stop: str = env_get("ROUTER_STOP", "")
    if stop != "":
        stop = absolute(stop, path_resolve("."))
    lock: str = json_string(config["output"]) + ".lock"
    if present(lock):
        regular(lock)
    log_configure(logging.INFO)
    with file_lock(lock) as _guard:
        state: Json = open_store(config)
        index: int = 0
        while polls == 0 or index < polls:
            if stop != "" and present(stop):
                break
            state = open_store(config)
            batch: tuple[Json, list[Json]] = collect(config, json_loads(json_canonical(state)))
            planned: tuple[Json, Json] = route(config, batch[0], batch[1])
            state = commit(config, state, planned[0], planned[1])
            log(logging.INFO, "committed " + str(len(batch[1])) + " input lines")
            index = index + 1
            if polls == 0 or index < polls:
                sleep(float(interval) / 1000.0)
        print(json_canonical({"sources": state["sources"], "files": state["files"], "filtered": state["filtered"]}))
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
