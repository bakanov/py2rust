"""Concurrent foreground supervision with bounded restart policy and complete group shutdown."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - compact imports and process boundary
import logging
from configuration import load
from files import absolute, checkpoint, present, regular, unchanged
from lifecycle import clock, finished, initial, poll, start
from status import publish
from py2rust.stdlib import (
    Json, env_get, file_lock, file_open, json_int, json_keys, json_string, mkdir_new, monotonic, path_join,
    path_parent, path_resolve, process_exit, process_pool, process_pool_close, process_pool_signal,
    process_signal, sleep, sync_directory,
)


def supervise(config: Json) -> int:
    root: str = json_string(config["state"])
    assert not present(root), "session directory already exists; choose a fresh state name"
    mkdir_new(root)
    sync_directory(path_parent(root))
    rows: Json = {}
    for name in sorted(json_keys(config["services"])):
        rows[name] = initial(name)
        for stream in ["stdout", "stderr"]:
            with file_open(path_join(root, name + "." + stream), "x+b") as _log:
                pass
    started: float = monotonic()
    reason: str = ""
    signal: int = 0
    stop_at: int = 0
    killed: bool = False
    next_status: int = 0
    now: int = 0
    with process_pool() as pool:
        publish(config, rows, "running", reason, now, signal)
        while True:
            now = clock(started)
            if reason == "":
                signal = process_pool_signal(pool)
                if signal != 0:
                    reason = "signal"
                elif present(json_string(config["stop"])):
                    regular(json_string(config["stop"]))
                    reason = "stop_file"
                elif now >= json_int(config["run_ms"]):
                    reason = "deadline"
                if reason != "":
                    stop_at = now
                    for name in sorted(json_keys(rows)):
                        row: Json = rows[name]
                        if json_int(row["handle"]) != 0:
                            process_signal(pool, json_int(row["handle"]), 15)
                            row["state"] = "stopping"
                        elif json_string(row["state"]) in ["waiting", "backoff"]:
                            row["state"] = "stopped"
                        rows[name] = row
                    publish(config, rows, "stopping", reason, now, signal)
            if reason != "" and not killed and now >= stop_at + json_int(config["grace_ms"]):
                for name in sorted(json_keys(rows)):
                    if json_int(rows[name]["handle"]) != 0:
                        process_signal(pool, json_int(rows[name]["handle"]), 9)
                killed = True
            for name in sorted(json_keys(rows)):
                row: Json = rows[name]
                spec: Json = config["services"][name]
                if (
                    reason == ""
                    and json_string(row["state"]) in ["waiting", "backoff"]
                    and now >= json_int(row["next_ms"])
                ):
                    unchanged(config)
                    row = start(pool, row, spec, started)
                if json_int(row["handle"]) != 0:
                    row = poll(pool, row, spec, root, started, reason != "")
                rows[name] = row
            checkpoint("cycle")
            now = clock(started)
            pending: bool = False
            for name in json_keys(rows):
                pending = pending or json_string(rows[name]["state"]) in ["waiting", "backoff", "running", "stopping"]
            if not pending:
                if reason == "":
                    reason = "completed"
                break
            if reason != "" and now >= stop_at + json_int(config["grace_ms"]) + 1000:
                process_pool_close(pool)
                for name in json_keys(rows):
                    if json_int(rows[name]["handle"]) != 0:
                        rows[name] = finished(rows[name], config["services"][name], now, True, "forced_close", None)
                break
            if now >= next_status:
                publish(config, rows, "running" if reason == "" else "stopping", reason, now, signal)
                next_status = now + 100
            sleep(0.01)
    publish(config, rows, "finished", reason, now, signal)
    if signal != 0:
        return 128 + signal
    for name in json_keys(rows):
        if json_string(rows[name]["state"]) == "failed":
            return 1
    return 0


def main() -> None:
    try:
        config: Json = load(absolute(env_get("SUPERVISOR_CONFIG", "supervisor-job.json"), path_resolve(".")))
        lock: str = json_string(config["state"]) + ".lock"
        if present(lock):
            regular(lock)
        code: int = 0
        with file_lock(lock) as _guard:
            regular(lock)
            code = supervise(config)
        process_exit(code)
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
