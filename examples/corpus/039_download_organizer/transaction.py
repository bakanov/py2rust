"""Durable progress, exclusive moves and recovery of one unrecorded operation."""

from guards import digest, document, fields, identity, present, signature

from py2rust.stdlib import (
    Json,
    directory_names,
    env_get,
    json_array,
    json_bool,
    json_equal,
    json_int,
    json_keys,
    json_string,
    mkdir_new,
    path_join,
    path_parent,
    pretty,
    process_exit,
    rename_no_replace,
    sleep,
    sync_directory,
    write_text_atomic,
)


def checkpoint(label: str, step: int) -> None:
    token: str = label + ":" + str(step)
    if env_get("ORGANIZE_PAUSE", "") == token:
        print("PAUSED " + token)
        signal: str = env_get("ORGANIZE_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                break
            sleep(0.01)
        assert present(signal), "pause timed out"
    if env_get("ORGANIZE_STOP", "") == token:
        process_exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(path: str, receipt: Json) -> None:
    encoded: str = pretty({"checksum": digest(receipt), "receipt": receipt})
    assert len(encoded.encode()) <= 2097152, "journal exceeds 2 MiB"
    write_text_atomic(path, encoded)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def matches(root: str, row: Json, moved: bool, limit: int) -> bool:
    selected: str = json_string(row["target"] if moved else row["source"])
    absent: str = json_string(row["source"] if moved else row["target"])
    return (
        not present(path_join(root, absent))
        and present(path_join(root, selected))
        and json_equal(signature(path_join(root, selected), limit), row["signature"])
    )


def prepare(root: str, receipt: Json, path: str) -> Json:
    known: Json = receipt["parents"]
    index: int = 0
    for parent in json_keys(known):
        directory: str = path_join(root, parent)
        if known[parent] is None:
            if present(directory):
                identity(directory)
                assert len(directory_names(directory, 1)) == 0, "unrecorded directory is not empty"
            else:
                mkdir_new(directory)
            checkpoint("mkdir", index)
            sync_directory(path_parent(directory))
            known[parent] = identity(directory)
            assert json_equal(known[parent]["device"], known["."]["device"]), "cross-device directory"
            receipt["parents"] = known
            save(path, receipt)
            checkpoint("directory", index)
        else:
            assert json_equal(identity(directory), known[parent]), "directory identity changed"
        index = index + 1
    return receipt


def execute(envelope: Json, path: str) -> Json:
    plan: Json = envelope["plan"]
    root: str = json_string(plan["root"])
    rows: list[Json] = json_array(plan["rows"])
    limit: int = json_int(plan["max_bytes"])
    receipt: Json = {"id": envelope["id"], "step": 0, "complete": False, "parents": plan["parents"]}
    existing: bool = present(path)
    if existing:
        saved: Json = document(path)
        fields(saved, ["checksum", "receipt"])
        assert json_string(saved["checksum"]) == digest(saved["receipt"]), "journal checksum mismatch"
        receipt = saved["receipt"]
        fields(receipt, ["id", "step", "complete", "parents"])
        assert json_equal(receipt["id"], envelope["id"]), "journal belongs to another plan"
        assert json_keys(receipt["parents"]) == json_keys(plan["parents"]), "journal parents differ"
    else:
        for parent in json_keys(plan["parents"]):
            if plan["parents"][parent] is None:
                assert not present(path_join(root, parent)), "unplanned directory appeared"
    step: int = json_int(receipt["step"])
    assert 0 <= step <= len(rows) and (
        not json_bool(receipt["complete"]) or step == len(rows)
    ), "invalid journal progress"
    pending: bool = False
    for index in range(len(rows)):
        if not matches(root, rows[index], index < step, limit):
            assert (
                existing
                and index == step
                and not json_bool(receipt["complete"])
                and matches(root, rows[index], True, limit)
            ), "tree differs from the reviewed plan"
            pending = True
    if not existing:
        save(path, receipt)
    checkpoint("journal", step)
    receipt = prepare(root, receipt, path)
    while step < len(rows):
        row: Json = rows[step]
        if not pending:
            checkpoint("before", step)
        target: str = path_join(root, json_string(row["target"]))
        parent: str = path_parent(json_string(row["target"]))
        while True:
            assert json_equal(
                identity(path_join(root, parent)), receipt["parents"][parent]
            ), "parent changed before move"
            if parent == ".":
                break
            parent = path_parent(parent)
        if not pending:
            assert matches(root, row, False, limit), "source or destination changed before move"
            rename_no_replace(path_join(root, json_string(row["source"])), target)
            checkpoint("renamed", step)
        pending = False
        sync_directory(path_parent(target))
        sync_directory(root)
        checkpoint("synced", step)
        step = step + 1
        receipt["step"] = step
        save(path, receipt)
        checkpoint("saved", step)
    for row in rows:
        assert matches(root, row, True, limit), "organized file changed"
    receipt["complete"] = True
    save(path, receipt)
    checkpoint("complete", step)
    return {"id": envelope["id"], "status": "complete", "files": len(rows), "bytes": plan["bytes"]}
