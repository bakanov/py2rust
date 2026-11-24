"""Execute a JSON command batch with one durable mutation and response at a time."""

# ruff: noqa: PLR1711, BLE001, LOG015 - explicit returns and recoverable errors

import logging

import journal
import model
import storage as disk
from model import State

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_canonical,
    json_int,
    json_loads,
    json_string,
    limit_address_space,
    process_exit,
)


def execute(directory: str, capacity: int, commands: list[Json]) -> None:
    disk.prepare(directory)
    with disk.file_lock(disk.path_join(directory, ".lock")) as _lock:
        disk.initialize(directory, capacity)
        state: State = State(capacity, 0, {})
        snapshot: str = disk.path_join(directory, "state.json")
        if disk.present(snapshot):
            state = model.restore(disk.read(snapshot, 4194304), capacity)
        with disk.file_open(disk.path_join(directory, "journal.bin"), "r+b") as handle:
            recovered: tuple[State, int, int] = journal.replay(state, handle)
            state = recovered[0]
            pending: str = disk.path_join(directory, "snapshot.next")
            discarded: bool = disk.present(pending)
            if discarded:
                disk.remove_file(pending)
                disk.sync_directory(directory)
            print(
                json_canonical(
                    {
                        "op": "OPEN",
                        "sequence": state.sequence,
                        "replayed": recovered[2],
                        "trimmed_bytes": recovered[1],
                        "discarded_snapshot": discarded,
                    }
                )
            )
            for position in range(len(commands)):
                try:
                    request: Json = commands[position]
                    operation: str = model.command(request)
                    response: Json = {"op": operation}
                    if operation in ["GET", "SET", "DELETE"]:
                        name: str = model.key(request["key"])
                        response["key"] = name
                        response["found"] = name in state.values
                        response["value"] = state.values.get(name, None)
                        if operation != "GET":
                            state = journal.append(state, handle, request)
                            response["committed"] = True
                    elif operation == "COMPACT":
                        journal.compact(state, handle, directory)
                    elif operation == "DUMP":
                        response["values"] = state.values
                    else:
                        response["keys"] = len(state.values)
                        response["capacity"] = state.capacity
                        response["journal_bytes"] = disk.file_size(handle)
                    response["sequence"] = state.sequence
                    print(json_canonical(response))
                except Exception as error:
                    assert False, "command " + str(position + 1) + ": " + str(error)
    return


def run() -> None:
    limit_address_space(268435456)
    path: str = disk.absolute(env_get("DB_CONFIG", "database-job.json"), disk.path_resolve("."))
    config: Json = json_loads(disk.read(path, 65536).decode())
    model.exact(config, ["database", "trace", "capacity"])
    capacity: int = json_int(config["capacity"])
    assert 1 <= capacity <= 256, "capacity must be 1..256"
    base: str = disk.path_parent(path)
    directory: str = disk.absolute(json_string(config["database"]), base)
    trace: str = disk.absolute(json_string(config["trace"]), base)
    for protected in [path, trace]:
        assert protected != directory and not protected.startswith(directory + "/"), "database overlaps an input"
    commands: list[Json] = json_array(json_loads(disk.read(trace, 1048576).decode()))
    assert len(commands) <= 1024, "trace exceeds 1024 commands"
    execute(directory, capacity, commands)
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
