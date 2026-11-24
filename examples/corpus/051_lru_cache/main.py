"""Replay a complete trace against a new or restored LRU cache, then publish one immutable bundle."""

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Cache, apply, capacity, empty, entries, exact, metrics
from persistence import restore, save

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
)


def run() -> None:
    mode: str = env_get("LRU_MODE", "preview")
    assert mode in ["preview", "write"], "invalid LRU mode"
    path: str = absolute(env_get("LRU_CONFIG", "cache-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["trace", "state", "capacity", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    documents: list[Document] = [configuration]
    cache: Cache = empty(capacity(config["capacity"]))
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, base), 8388608)
        documents.append(original)
        cache = restore(json_loads(original.data.decode()), cache.capacity)
    trace: Document = read(absolute(json_string(config["trace"]), base), 4194304)
    documents.append(trace)
    commands: list[Json] = json_array(json_loads(trace.data.decode()))
    assert len(commands) <= 2000, "trace exceeds 2000 commands"
    before: int = cache.stats["steps"]
    events: list[str] = []
    event_bytes: int = 0
    for index in range(len(commands)):
        try:
            result: tuple[Cache, Json] = apply(cache, commands[index])
            cache = result[0]
            encoded: str = json_canonical(result[1]) + "\n"
            event_bytes = event_bytes + len(encoded.encode())
            assert event_bytes <= 16777216, "events exceed 16 MiB"
            events.append(encoded)
        except Exception as error:  # noqa: BLE001 - retain the failing trace command number
            assert False, "command " + str(index + 1) + ": " + str(error)
    state: str = save(cache)
    assert len(state.encode()) <= 8388608, "state exceeds 8 MiB"
    report: Json = {
        "before_steps": before,
        "after_steps": cache.stats["steps"],
        "commands": len(commands),
        "capacity": cache.capacity,
        "entries": entries(cache.values),
        "stats": metrics(cache.stats),
    }
    files: dict[str, str] = {"state.json": state, "events.jsonl": "".join(events), "report.json": pretty(report) + "\n"}
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(pretty(report))
    return  # noqa: PLR1711


def main() -> None:
    try:
        run()
    except Exception as error:  # noqa: BLE001 - CLI failures use exit status 2
        logging.error(str(error))  # noqa: LOG015 - supported logging facade
        process_exit(2)
    return  # noqa: PLR1711


if __name__ == "__main__":
    main()
