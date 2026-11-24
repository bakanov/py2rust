# ruff: noqa: PLR1711, BLE001, LOG015 - explicit returns and supported subset operations
"""Replay autocomplete commands, then publish consistent snapshots, dictionary exports and events."""

import logging

from commands import apply
from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from persistence import restore, save
from trie import Index, capacity, empty, entries, exact, summary

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
    mode: str = env_get("AUTOCOMPLETE_MODE", "preview")
    assert mode in ["preview", "write"], "invalid autocomplete mode"
    path: str = absolute(env_get("AUTOCOMPLETE_CONFIG", "autocomplete-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["trace", "state", "capacity", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    documents: list[Document] = [configuration]
    index: Index = empty(capacity(config["capacity"]))
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, base), 8388608)
        documents.append(original)
        index = restore(json_loads(original.data.decode()), index.capacity)
    trace: Document = read(absolute(json_string(config["trace"]), base), 4194304)
    documents.append(trace)
    commands: list[Json] = json_array(json_loads(trace.data.decode()))
    assert len(commands) <= 2000, "trace exceeds 2000 commands"
    before: int = index.steps
    events: list[str] = []
    event_bytes: int = 0
    for position in range(len(commands)):
        try:
            result: tuple[Index, Json] = apply(index, commands[position])
            index = result[0]
            encoded: str = json_canonical(result[1]) + "\n"
            event_bytes = event_bytes + len(encoded.encode())
            assert event_bytes <= 16777216, "events exceed 16 MiB"
            events.append(encoded)
        except Exception as error:
            assert False, "command " + str(position + 1) + ": " + str(error)
    state: str = save(index)
    assert len(state.encode()) <= 8388608, "state exceeds 8 MiB"
    report: Json = {
        "before_steps": before,
        "after_steps": index.steps,
        "commands": len(commands),
        "index": summary(index),
    }
    files: dict[str, str] = {
        "state.json": state,
        "dictionary.json": json_canonical(entries(index.root, "")) + "\n",
        "events.jsonl": "".join(events),
        "report.json": pretty(report) + "\n",
    }
    checkpoint("validated")
    unchanged(documents)
    if mode == "write":
        publish(output, files, documents)
    print(pretty(report))
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
