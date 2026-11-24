"""Persist bounded stock transactions with idempotent IDs and replay-verified audit history."""

# ruff: noqa: BLE001, LOG015, PLR1711 - separate domain/persistence boundaries
import logging

from ledger import attempt, create, encoded, replay
from model import catalog, exact, integer
from reports import bundle
from storage import Document, absolute, checkpoint, finish, present, read, stamp

from py2rust.stdlib import (
    Json,
    env_get,
    file_lock,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_loads_unique,
    json_string,
    path_parent,
    path_resolve,
    process_exit,
)


def run() -> int:
    request: Document = read(absolute(env_get("INVENTORY_CONFIG", "inventory-job.json"), path_resolve(".")), 262144)
    config: Json = json_loads_unique(request.data.decode())
    assert json_int(config["version"]) == 1, "unsupported request version"
    mode: str = json_string(config["mode"])
    assert mode in ["apply", "verify"], "unknown ledger mode"
    required: list[str] = ["version", "mode", "store", "output"]
    if mode == "apply":
        required = required + ["items", "expected_revision", "operations"]
    exact(config, required)
    base: str = path_parent(request.path)
    path: str = absolute(json_string(config["store"]), base)
    lock: str = path + ".lock"
    output: str = absolute(json_string(config["output"]), base)
    assert request.path not in [path, lock] and output not in [path, lock], "paths must be distinct"
    assert not present(output), "output already exists"
    if present(lock):
        stamp(lock)
    with file_lock(lock) as _guard:
        stamp(lock)
        checkpoint("locked")
        store: Document = Document(path, None, b"")
        if present(path):
            store = read(path, 2097152)
        assert mode == "apply" or store.stamp is not None, "ledger does not exist"
        ledger: Json = (
            create(catalog(config["items"])) if store.stamp is None else json_loads_unique(store.data.decode())
        )
        replay(ledger)
        before: int = json_int(ledger["revision"])
        outcomes: list[Json] = []
        if mode == "apply":
            assert json_equal(ledger["items"], catalog(config["items"])), "item catalog differs from ledger"
            if config["expected_revision"] is not None:
                assert integer(config["expected_revision"], 0, 512) == before, "revision conflict"
            operations: list[Json] = json_array(config["operations"])
            assert len(operations) <= 128, "batch operation limit"
            for index in range(len(operations)):
                event: Json = operations[index]
                result: tuple[Json, Json] = attempt(ledger, event, index)
                ledger = result[0]
                outcomes.append(result[1])
        replay(ledger)
        changed: bool = store.stamp is None or json_int(ledger["revision"]) != before
        data: bytes = encoded(ledger) if changed else store.data
        assert len(data) <= 2097152, "ledger byte limit exceeded"
        files: dict[str, bytes] = bundle(mode, before, ledger, outcomes, data, changed)
        finish(output, files, request, store, data, changed)
        summary: Json = json_loads_unique(files["report.json"].decode())["summary"]
        print(json_canonical(summary))
        return 1 if json_int(summary["rejected"]) > 0 else 0


def main() -> None:
    try:
        process_exit(run())
    except Exception as error:
        logging.error(str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
