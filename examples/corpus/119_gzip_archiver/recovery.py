"""Finish a durable pending transaction; discard an unprepared stream for a safe retry."""

from documents import checkpoint, discard, load, present
from index import commit, verify_entry
from validation import entry

from py2rust.stdlib import (
    Json,
    json_equal,
    json_int,
    json_string,
    path_join,
    rename_no_replace,
    sync_directory,
)


def recover(root: str, rows: list[Json], settings: Json) -> list[Json]:
    pending_path: str = path_join(root, "pending.json")
    staged: str = path_join(root, ".stage.gz")
    if present(pending_path):
        pending: Json = entry(load(pending_path, 65536))
        destination: str = path_join(root, json_string(pending["id"]) + ".gz")
        found: bool = False
        total: int = json_int(pending["size"])
        for row in rows:
            if json_string(row["id"]) == json_string(pending["id"]):
                assert json_equal(row, pending), "pending ID conflicts with completed index"
                found = True
            else:
                total = total + json_int(row["size"])
        assert total <= json_int(settings["total_bytes"]), "pending transaction exceeds aggregate limit"
        if present(staged):
            assert not found and not present(destination), "pending publication collision"
            verify_entry(staged, pending, settings)
            rename_no_replace(staged, destination)
            sync_directory(root)
            checkpoint("published")
        verify_entry(destination, pending, settings)
        if not found:
            assert len(rows) < 128, "completed archive count limit"
            rows.append(pending)
            commit(root, rows)
            checkpoint("indexed")
        discard(root, "pending.json")
    else:
        discard(root, ".stage.gz")
    discard(root, ".index.json.tmp")
    discard(root, ".pending.json.tmp")
    return rows
