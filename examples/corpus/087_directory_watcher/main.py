"""Run one observation or a cancellable polling loop; every printed journal follows a durable checkpoint."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: BLE001, LOG015, PLR1711 - process boundary and explicit subset returns
import logging
from configuration import configuration, integer
from debounce import advance
from files import absolute, inside, present, regular
from snapshot import capture
from storage import load, save
from py2rust.stdlib import (
    Json, env_get, file_lock, floor, json_array, json_canonical, json_int, json_keys, json_loads, json_string,
    monotonic, path_resolve, process_exit, sleep, unix_time,
)


def report(state: Json) -> Json:
    journal: list[Json] = json_array(state["journal"])
    return {
        "clock_ms": state["clock_ms"],
        "observed_entries": len(json_keys(state["snapshot"])),
        "pending": len(json_keys(state["pending"])),
        "first_id": json_int(state["next_id"]) - len(journal),
        "next_id": state["next_id"],
        "events": journal,
    }


def stable_scan(config: Json) -> Json:
    for attempt in range(3):
        try:
            return capture(config)
        except Exception:
            if attempt == 2:
                raise
            sleep(0.01)
    return {}


def run() -> None:
    config: Json = configuration()
    polls: int = integer(json_loads(env_get("WATCH_POLLS", "1")), 0, 100000)
    interval: int = integer(json_loads(env_get("WATCH_INTERVAL_MS", "250")), 10, 60000)
    manual: str = env_get("WATCH_NOW_MS", "")
    assert manual == "" or polls == 1, "manual clock requires one poll"
    instant: int = integer(json_loads(manual), 0, 9000000000000000) if manual != "" else 0
    stop: str = env_get("WATCH_STOP", "")
    if stop != "":
        stop = absolute(stop, path_resolve("."))
        assert not inside(stop, json_string(config["root"])) and not inside(
            stop, json_string(config["output"])
        ), "stop overlaps data"
    lock: str = json_string(config["output"]) + ".lock"
    if present(lock):
        regular(lock)
    with file_lock(lock) as _guard:
        state: Json = load(config)
        index: int = 0
        while polls == 0 or index < polls:
            if stop != "" and present(stop):
                break
            now: int = instant if manual != "" else floor(unix_time() * 1000.0)
            current: Json = stable_scan(config)
            state = advance(config, state, current, now)
            save(config, state)
            print(json_canonical(report(state)))
            index = index + 1
            if polls == 0 or index < polls:
                deadline: float = monotonic() + float(interval) / 1000.0
                while monotonic() < deadline:
                    if stop != "" and present(stop):
                        break
                    sleep(min(0.05, max(0.0, deadline - monotonic())))
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
