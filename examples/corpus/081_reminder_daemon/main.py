"""Run persistent reminders on a real clock or replay an explicit clock trace."""

# ruff: noqa: BLE001, LOG015, PLR1711 - recoverable boundary and explicit subset returns
import logging

from documents import Document, absolute, present, read, stamp
from model import MAX_CLOCK, Reminder, advance, definitions, exact, integer, report
from persistence import checkpoint, load, save

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    floor,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_loads,
    json_string,
    log,
    log_configure,
    path_parent,
    path_resolve,
    path_same,
    process_exit,
    sleep,
    unix_time,
)


def run() -> None:
    mode: str = env_get("REMINDER_MODE", "trace")
    assert mode in ["trace", "run", "inspect"], "invalid reminder mode"
    config: Document = read(absolute(env_get("REMINDER_CONFIG", "reminder-job.json"), path_resolve(".")), 65536)
    value: Json = json_loads(config.data.decode())
    exact(value, ["version", "store", "reminders"])
    assert json_int(value["version"]) == 1, "unsupported job version"
    reminders: list[Reminder] = definitions(value["reminders"])
    store: str = absolute(json_string(value["store"]), path_parent(config.path))
    lock: str = store + ".lock"
    documents: list[Document] = [config]
    times: list[int] = []
    if mode == "trace":
        source: Document = read(absolute(env_get("REMINDER_TRACE", "clock.json"), path_parent(config.path)), 65536)
        documents.append(source)
        values: list[Json] = json_array(json_loads(source.data.decode()))
        assert len(values) <= 1000, "clock trace exceeds 1000 ticks"
        for entry in values:
            times.append(integer(entry, 0, MAX_CLOCK))
    polls: int = integer(json_loads(env_get("REMINDER_POLLS", "0")), 0, 100000)
    interval: int = integer(json_loads(env_get("REMINDER_INTERVAL_MS", "250")), 10, 60000)
    stop: str = env_get("REMINDER_STOP", "")
    if stop != "":
        stop = absolute(stop, path_parent(config.path))
    for path in [store, lock]:
        if present(path):
            metadata: Json = stamp(path)
            assert json_int(metadata["links"]) == 1, "state and lock must not have hard-link aliases"
        for document in documents:
            assert path != document.path, "state overlaps input"
            if present(path):
                assert not path_same(path, document.path), "state aliases input"
        assert path != stop, "stop path overlaps state"
    if present(store) and present(lock):
        assert not path_same(store, lock), "state aliases lock"
    log_configure(logging.INFO)
    with file_lock(lock) as _handle:
        state: Json = load(store, reminders)
        for document in documents:
            assert json_equal(document.stamp, stamp(document.path)), "input changed"
        if mode == "inspect":
            assert present(store), "no saved state"
        else:
            index: int = 0
            while mode == "run" or index < len(times):
                if mode == "run" and (polls > 0 and index >= polls or stop != "" and present(stop)):
                    break
                observed: int = floor(unix_time()) if mode == "run" else times[index]
                changed: tuple[Json, list[Json]] = advance(state, reminders, observed)
                state = changed[0]
                save(store, state)
                for event in changed[1]:
                    log(logging.INFO, "REMINDER " + json_canonical(event))
                checkpoint("after_log")
                index = index + 1
                if mode == "run" and (polls == 0 or index < polls):
                    sleep(float(interval) / 1000.0)
            if not present(store):
                save(store, state)
        print(json_canonical(report(state)))
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
