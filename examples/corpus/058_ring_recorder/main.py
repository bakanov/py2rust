"""Replay a sample trace and publish state, selected exports, final window and diagnostics."""

# ruff: noqa: PLR1711, BLE001, LOG015 - explicit returns and recoverable subset errors

import logging

from documents import Document, absolute, checkpoint, present, publish, read, unchanged
from model import Ring, apply, bounded, empty, exact, records, select, view
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
    mode: str = env_get("RING_MODE", "preview")
    assert mode in ["preview", "write"], "invalid recorder mode"
    path: str = absolute(env_get("RING_CONFIG", "ring-job.json"), path_resolve("."))
    configuration: Document = read(path, 65536)
    config: Json = json_loads(configuration.data.decode())
    exact(config, ["trace", "state", "capacity", "window_ms", "output"])
    base: str = path_parent(path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output directory already exists"
    documents: list[Document] = [configuration]
    size: int = bounded(config["capacity"], 1, 4096)
    window: int = bounded(config["window_ms"], 0, 31536000000)
    ring: Ring = empty(size, window)
    state_path: str = json_string(config["state"])
    if state_path != "":
        original: Document = read(absolute(state_path, base), 1048576)
        documents.append(original)
        ring = restore(json_loads(original.data.decode()), size, window)
    trace: Document = read(absolute(json_string(config["trace"]), base), 1048576)
    documents.append(trace)
    commands: list[Json] = json_array(json_loads(trace.data.decode()))
    assert len(commands) <= 8192, "trace exceeds 8192 commands"
    before: int = ring.stats["steps"]
    events: list[str] = []
    event_bytes: int = 0
    for index in range(len(commands)):
        try:
            result: tuple[Ring, Json] = apply(ring, commands[index])
            ring = result[0]
            encoded: str = json_canonical(result[1]) + "\n"
            event_bytes = event_bytes + len(encoded.encode())
            assert event_bytes <= 16777216, "events exceed 16 MiB"
            events.append(encoded)
        except Exception as error:
            assert False, "command " + str(index + 1) + ": " + str(error)
    state: str = save(ring)
    assert len(state.encode()) <= 1048576, "state exceeds 1 MiB"
    report: Json = {
        "before_steps": before,
        "after_steps": ring.stats["steps"],
        "commands": len(commands),
        "recorder": view(ring),
    }
    lines: list[str] = []
    for sample in records(select(ring, 0, ring.clock_ms)):
        lines.append(json_canonical(sample) + "\n")
    files: dict[str, str] = {
        "state.json": state,
        "events.jsonl": "".join(events),
        "window.jsonl": "".join(lines),
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
