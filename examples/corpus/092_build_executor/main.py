"""Build in deterministic dependency order, retaining successful independent targets after a failure."""

# ruff: noqa: I001, BLE001, LOG015, PLR1711 - process boundary and explicit subset returns
import logging
from building import build
from configuration import load
from files import absolute, atomic, discard, hashed, present, regular
from storage import load as load_cache, save
from py2rust.stdlib import (
    Json, env_get, file_lock, json_array, json_canonical, json_int, json_keys, json_string, path_join,
    path_resolve, process_exit,
)


def run() -> int:
    config: Json = load(absolute(env_get("BUILD_CONFIG", "build-job.json"), path_resolve(".")))
    root: str = json_string(config["state"])
    lock: str = root + ".lock"
    if present(lock):
        regular(lock)
    with file_lock(lock) as _guard:
        regular(lock)
        entries: Json = load_cache(config)
        save(config, entries, "initial")
        records: list[Json] = []
        successful: set[str] = set()
        interrupted: int = 0
        summary: Json = {"cached": 0, "rebuilt": 0, "failed": 0, "blocked": 0}
        for item in json_array(config["order"]):
            name: str = json_string(item)
            row: Json = config["targets"][name]
            blocked: bool = interrupted != 0
            for dependency in json_array(row["dependencies"]):
                blocked = blocked or json_string(dependency) not in successful
            record: Json = {
                "id": name,
                "status": "blocked",
                "reason": "interrupted" if interrupted != 0 else "dependency_failed",
                "outcome": None,
                "stdout_base64": "",
                "stderr_base64": "",
                "error": "",
                "interrupt_signal": 0,
            }
            if blocked:
                if interrupted == 0:
                    if name in json_keys(entries):
                        del entries[name]
                    save(config, entries, "blocked:" + name)
            else:
                result: tuple[Json, Json] = build(config, row, entries)
                entries = result[0]
                record = result[1]
                interrupted = json_int(record["interrupt_signal"])
            status: str = json_string(record["status"])
            if status in ["cached", "rebuilt"]:
                successful.add(name)
            summary[status] = json_int(summary[status]) + 1
            records.append(record)
            print(json_canonical(record))
        save(config, entries, "final")
        report: Json = {
            "version": 1,
            "summary": summary,
            "targets": records,
            "cache_sha256": hashed(json_canonical(entries).encode()),
        }
        atomic(path_join(root, "report.json"), (json_canonical(report) + "\n").encode(), config["guards"], "report")
        discard(path_join(root, "artifact.tmp"))
        print(json_canonical(summary))
        if interrupted != 0:
            return 128 + interrupted
        return 1 if json_int(summary["failed"]) + json_int(summary["blocked"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
