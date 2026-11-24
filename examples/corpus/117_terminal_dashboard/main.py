"""Watch a complete task project or replay its recorded terminal frames without Python."""

# ruff: noqa: BLE001, LOG015, PLR1711 - fatal boundary and explicit returns
import logging

from documents import Document, absolute, present, publish, read
from model import exact, settings, text
from records import replay
from reports import bundle
from session import show, watch

from py2rust.stdlib import (
    Json,
    env_get,
    json_int,
    json_loads_unique,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> int:
    request: Document = read(absolute(env_get("TASK_DASHBOARD_CONFIG", "tasks-job.json"), path_resolve(".")), 65536)
    config: Json = json_loads_unique(request.data.decode())
    mode: str = text(config["mode"])
    assert json_int(config["version"]) == 1 and mode in ["watch", "replay"], "request version or mode"
    fields: list[str] = ["version", "mode", "input", "output"]
    if mode == "watch":
        fields = fields + ["columns", "refreshes", "interval_ms"]
    exact(config, fields)
    path: str = absolute(text(config["input"]), path_parent(request.path))
    output: str = absolute(text(config["output"]), path_parent(request.path))
    assert output != path and not present(output), "output already exists"
    if mode == "watch":
        options: Json = settings(
            {"columns": config["columns"], "refreshes": config["refreshes"], "interval_ms": config["interval_ms"]}
        )
        result: tuple[list[Json], Json, int] = watch(path, options)
        return finish(output, [request], options, result[0], result[1], result[2], False)
    document: Document = read(path, 16777216)
    restored: tuple[Json, list[Json], Json, int] = replay(json_loads_unique(document.data.decode()))
    for record in restored[1]:
        show(record, False)
    return finish(output, [request, document], restored[0], restored[1], restored[2], restored[3], True)


def finish(
    output: str,
    inputs: list[Document],
    options: Json,
    events: list[Json],
    state: Json,
    interrupted: int,
    replayed: bool,
) -> int:
    publish(output, bundle(options, events, state, interrupted), inputs)
    if not replayed:
        if interrupted != 0:
            return 128 + interrupted
        for record in events:
            if text(record["status"]) not in ["updated", "unchanged"]:
                return 1
    return 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
