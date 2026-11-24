"""Public snapshots omit internal process handles; final snapshots bind the retained log bytes."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from files import atomic, seal
from py2rust.stdlib import Json, json_canonical, json_int, json_keys, json_string, path_join


def publish(config: Json, rows: Json, phase: str, reason: str, now: int, signal: int) -> None:
    services: list[Json] = []
    for name in sorted(json_keys(rows)):
        source: Json = rows[name]
        row: Json = {}
        for key in ["id", "state", "pid", "attempts", "next_ms", "returncode", "error", "history"]:
            row[key] = source[key]
        for stream in ["stdout", "stderr"]:
            details: Json = source[stream]
            view: Json = {
                "file": details["file"],
                "bytes": details["kept"],
                "seen": details["seen"],
                "discarded": json_int(details["seen"]) - json_int(details["kept"]),
            }
            if phase == "finished":
                sealed: Json = seal(path_join(json_string(config["state"]), json_string(details["file"])))
                assert json_int(sealed["bytes"]) == json_int(details["kept"]), "log size changed"
                view["sha256"] = sealed["sha256"]
            row[stream] = view
        services.append(row)
    document: Json = {
        "version": 1,
        "phase": phase,
        "reason": reason,
        "elapsed_ms": now,
        "interrupt_signal": signal,
        "services": services,
    }
    atomic(config, (json_canonical(document) + "\n").encode(), phase)
    return
