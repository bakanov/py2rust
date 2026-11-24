"""A baseline represents an observed common state, not a forced winner."""

from documents import checksum, document, fields, relative

from py2rust.stdlib import (
    Json,
    json_equal,
    json_int,
    json_keys,
    json_string,
    path_exists,
    path_parent,
    regex_fullmatch,
)


def read(config: Json) -> tuple[dict[str, Json], str]:
    entries: dict[str, Json] = {}
    path: str = json_string(config["baseline"])
    if not path_exists(path):
        return (entries, "")
    envelope: Json = document(path)
    fields(envelope, ["id", "baseline"])
    body: Json = envelope["baseline"]
    assert json_string(envelope["id"]) == checksum(body), "baseline checksum mismatch"
    fields(body, ["format", "source", "destination", "exclude", "entries"])
    assert json_int(body["format"]) == 1, "unknown baseline format"
    for key in ["source", "destination", "exclude"]:
        assert json_equal(body[key], config[key]), "baseline belongs to another tree pair or exclusion policy"
    names: list[str] = json_keys(body["entries"])
    assert len(names) > 0 and len(names) <= 10000 and names[0] == "", "invalid baseline entries"
    for name in names:
        relative(name)
        row: Json = body["entries"][name]
        kind: str = json_string(row["kind"])
        if kind == "file":
            fields(row, ["kind", "mode", "size", "sha256"])
            assert json_int(row["size"]) >= 0 and json_int(row["size"]) <= 1099511627776, "invalid size"
            assert regex_fullmatch("[0-9a-f]{64}", json_string(row["sha256"])), "invalid digest"
        elif kind == "symlink":
            fields(row, ["kind", "target"])
            target: str = json_string(row["target"])
            assert target != "" and "\x00" not in target and len(target.encode()) <= 4096, "invalid target"
        else:
            assert kind == "directory", "unsupported baseline kind"
            fields(row, ["kind", "mode"])
        if kind != "symlink":
            assert json_int(row["mode"]) >= 0 and json_int(row["mode"]) <= 511, "invalid mode"
        if name == "":
            assert kind == "directory", "root must be a directory"
        else:
            parent: str = path_parent(name)
            parent = "" if parent == "." else parent
            assert parent in entries and json_string(entries[parent]["kind"]) == "directory", "missing parent"
        entries[name] = row
    return (entries, json_string(envelope["id"]))
