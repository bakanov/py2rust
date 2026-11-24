"""Archive an explicit rotated-log inventory, preserving immutable completed IDs."""

from documents import absolute, checkpoint, present, save, stamp
from index import commit, inventory, read_index, verify_entry
from recovery import recover
from streams import compress, digest_file
from validation import identifier, keys, pathname

from py2rust.stdlib import (
    Json,
    directory_names,
    file_lock,
    json_array,
    json_equal,
    json_int,
    json_string,
    mkdir_new,
    path_join,
    path_stat,
)


def preflight(inputs: Json, base: str, root: str) -> list[Json]:
    rows: list[Json] = json_array(inputs)
    assert len(rows) <= 128, "input count limit"
    seen: set[str] = set()
    for row in rows:
        keys(row, ["id", "path"])
        name: str = identifier(row["id"])
        assert name not in seen, "duplicate requested ID"
        seen.add(name)
        path: str = absolute(pathname(row["path"]), base)
        assert path != root and not path.startswith(root + "/"), "sources must be outside archive directory"
    return rows


def add(root: str, rows: list[Json], inputs: list[Json], base: str, settings: Json, level: int) -> list[Json]:
    for requested in inputs:
        name: str = json_string(requested["id"])
        source: str = absolute(json_string(requested["path"]), base)
        found: bool = False
        total: int = 0
        for row in rows:
            total = total + json_int(row["size"])
            if json_string(row["id"]) == name:
                actual: Json = digest_file(source, json_int(settings["source_bytes"]))
                assert json_equal(
                    actual, {"size": row["size"], "sha256": row["sha256"]}
                ), "completed ID has different source bytes"
                found = True
        if not found:
            assert len(rows) < 128, "completed archive count limit"
            allowance: int = min(json_int(settings["source_bytes"]), json_int(settings["total_bytes"]) - total)
            staged: str = path_join(root, ".stage.gz")
            expanded: Json = compress(source, staged, level, json_int(settings["compressed_bytes"]), allowance)
            packed: Json = digest_file(staged, json_int(settings["compressed_bytes"]))
            pending: Json = {
                "id": name,
                "source": json_string(requested["path"]),
                "size": expanded["size"],
                "sha256": expanded["sha256"],
                "compressed_size": packed["size"],
                "compressed_sha256": packed["sha256"],
                "level": level,
            }
            verify_entry(staged, pending, settings)
            save(root, "pending.json", pending)
            checkpoint("prepared")
            rows = recover(root, rows, settings)
    return rows


def execute(root: str, inputs: list[Json], base: str, settings: Json, level: int, mode: str) -> Json:
    if not present(root):
        assert mode == "archive", "archive directory does not exist"
        mkdir_new(root)
    assert json_string(path_stat(root, False)["kind"]) == "directory", "expected archive directory"
    if not present(path_join(root, "index.json")):
        for name in directory_names(root, 3):
            assert name in [".lock", ".index.json.tmp"], "refuse initialization of nonempty directory"
    if present(path_join(root, ".lock")):
        stamp(path_join(root, ".lock"))
    with file_lock(path_join(root, ".lock")) as _lock:
        if not present(path_join(root, "index.json")):
            assert mode == "archive", "archive index does not exist"
            for name in directory_names(root, 3):
                assert name in [".lock", ".index.json.tmp"], "refuse initialization of nonempty directory"
            commit(root, [])
        rows: list[Json] = read_index(root)
        inventory(root, rows, settings)
        if mode != "verify":
            rows = recover(root, rows, settings)
        if mode == "archive":
            rows = add(root, rows, inputs, base, settings, level)
        summary: Json = inventory(root, rows, settings)
        summary["pending"] = present(path_join(root, "pending.json")) or present(path_join(root, ".stage.gz"))
        return summary
