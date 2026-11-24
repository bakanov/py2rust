"""Replay a bounded ingestion trace and atomically publish the filter, audit keys and measurements."""

# ruff: noqa: PLR1711, BLE001, LOG015, C414 - explicit returns and supported subset operations

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from filter import Filter, apply, empty, exact, summary
from persistence import restore, save

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_loads,
    json_string,
    path_parent,
    path_resolve,
    pretty,
    process_exit,
)


def run() -> None:
    mode: str = env_get("BLOOM_MODE", "preview")
    assert mode in ["preview", "write"], "invalid Bloom mode"
    path: str = absolute(env_get("BLOOM_CONFIG", "bloom-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["trace", "state", "expected", "probability_ppm", "capacity", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    documents: list[Document] = [configuration]
    index: Filter = empty(
        json_int(config["expected"]), json_int(config["probability_ppm"]), json_int(config["capacity"])
    )
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, base), 8388608)
        documents.append(original)
        index = restore(json_loads(original.data.decode()), index)
    trace: Document = read(absolute(json_string(config["trace"]), base), 4194304)
    documents.append(trace)
    commands: list[Json] = json_array(json_loads(trace.data.decode()))
    assert len(commands) <= 2000, "trace exceeds 2000 commands"
    before: int = index.steps
    events: list[str] = []
    event_bytes: int = 0
    for position in range(len(commands)):
        try:
            result: tuple[Filter, Json] = apply(index, commands[position])
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
        "filter": summary(index),
    }
    files: dict[str, bytes] = {
        "state.json": state.encode(),
        "filter.bin": bytes(index.bits),
        "keys.json": (json_canonical(sorted(list(index.keys))) + "\n").encode(),
        "events.jsonl": "".join(events).encode(),
        "report.json": (pretty(report) + "\n").encode(),
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
