"""Import spans, execute browser commands and publish a restorable result bundle."""

# ruff: noqa: PLR1711, BLE001, LOG015 - explicit returns and recoverable subset errors

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from index import Index, apply, bounded, document, empty, exact, ordered, view
from persistence import import_events, restore, save

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
    mode: str = env_get("INTERVAL_MODE", "preview")
    assert mode in ["preview", "write"], "invalid browser mode"
    path: str = absolute(env_get("INTERVAL_CONFIG", "interval-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["records", "trace", "state", "capacity", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    documents: list[Document] = [configuration]
    size: int = bounded(config["capacity"], 1, 1024)
    index: Index = empty(size)
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, base), 8388608)
        documents.append(original)
        index = restore(json_loads(original.data.decode()), size)
    imported: Json = {"read": 0, "added": 0, "replaced": 0}
    records_path: str = json_string(config["records"])
    if records_path != "":
        source: Document = read(absolute(records_path, base), 4194304)
        documents.append(source)
        loaded: tuple[Index, Json] = import_events(index, json_loads(source.data.decode()))
        index = loaded[0]
        imported = loaded[1]
    trace: Document = read(absolute(json_string(config["trace"]), base), 4194304)
    documents.append(trace)
    commands: list[Json] = json_array(json_loads(trace.data.decode()))
    assert len(commands) <= 2048, "trace exceeds 2048 commands"
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
        "imported": imported,
        "index": view(index),
    }
    rows: list[str] = []
    for event in ordered(index.events):
        rows.append(json_canonical(document(event)) + "\n")
    files: dict[str, str] = {
        "state.json": state,
        "events.jsonl": "".join(events),
        "records.jsonl": "".join(rows),
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
