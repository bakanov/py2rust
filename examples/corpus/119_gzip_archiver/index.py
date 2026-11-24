"""Validate the complete index and independently check every archived byte stream."""

# ruff: noqa: PLR1711 - explicit returns

from documents import load, present, save
from streams import decoded, digest_file
from validation import entry, integer, keys

from py2rust.stdlib import (
    Json,
    directory_names,
    json_array,
    json_equal,
    json_int,
    json_string,
    path_join,
)


def commit(root: str, rows: list[Json]) -> None:
    save(root, "index.json", {"version": 1, "format": "py2rust-gzip-log-index", "entries": rows})
    return


def read_index(root: str) -> list[Json]:
    value: Json = load(path_join(root, "index.json"), 1048576)
    keys(value, ["version", "format", "entries"])
    integer(value["version"], 1, 1)
    assert json_string(value["format"]) == "py2rust-gzip-log-index", "foreign index format"
    rows: list[Json] = json_array(value["entries"])
    assert len(rows) <= 128, "completed archive count limit"
    seen: set[str] = set()
    for row in rows:
        entry(row)
        name: str = json_string(row["id"])
        assert name not in seen, "duplicate archive ID"
        seen.add(name)
    return rows


def verify_entry(path: str, row: Json, settings: Json) -> None:
    entry(row)
    assert json_int(row["size"]) <= json_int(settings["source_bytes"]), "source byte limit"
    assert json_int(row["compressed_size"]) <= json_int(settings["compressed_bytes"]), "compressed byte limit"
    actual: Json = digest_file(path, json_int(settings["compressed_bytes"]))
    assert json_equal(
        actual, {"size": row["compressed_size"], "sha256": row["compressed_sha256"]}
    ), "archive digest mismatch"
    expanded: Json = decoded(path, json_int(row["compressed_size"]), json_int(row["size"]))
    assert json_equal(expanded, {"size": row["size"], "sha256": row["sha256"]}), "decoded log mismatch"
    return


def inventory(root: str, rows: list[Json], settings: Json) -> Json:
    total: int = 0
    compressed: int = 0
    allowed: set[str] = {".lock", "index.json", "pending.json", ".stage.gz", ".index.json.tmp", ".pending.json.tmp"}
    if present(path_join(root, "pending.json")):
        pending: Json = entry(load(path_join(root, "pending.json"), 65536))
        allowed.add(json_string(pending["id"]) + ".gz")
    for row in rows:
        total = total + json_int(row["size"])
        compressed = compressed + json_int(row["compressed_size"])
        assert total <= json_int(settings["total_bytes"]), "aggregate expansion limit"
        name: str = json_string(row["id"]) + ".gz"
        allowed.add(name)
        verify_entry(path_join(root, name), row, settings)
    for name in directory_names(root, 140):
        assert name in allowed, "unexpected file in archive directory"
    return {"completed": len(rows), "bytes": total, "compressed_bytes": compressed}
