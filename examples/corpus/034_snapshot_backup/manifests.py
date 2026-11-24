"""Validate every retained manifest before using paths or deleting any objects."""

from common import checksum, document, fields, relative, stamp, version_name

from py2rust.stdlib import (
    Json,
    directory_names,
    json_array,
    json_int,
    json_string,
    path_join,
    path_parent,
    regex_fullmatch,
)


def validate(envelope: Json, name: str) -> Json:
    fields(envelope, ["id", "snapshot"])
    body: Json = envelope["snapshot"]
    assert json_string(envelope["id"]) == checksum(body), "manifest checksum mismatch"
    fields(body, ["format", "name", "sequence", "entries"])
    assert json_int(body["format"]) == 1 and json_string(body["name"]) == version_name(name), "invalid manifest"
    assert json_int(body["sequence"]) >= 1, "invalid sequence"
    rows: list[Json] = json_array(body["entries"])
    assert len(rows) > 0 and len(rows) <= 10000, "invalid entry count"
    seen: dict[str, str] = {}
    files: dict[str, Json] = {}
    for row in rows:
        name = json_string(row["path"])
        relative(name)
        kind: str = json_string(row["kind"])
        expected: list[str] = ["path", "kind", "mode", "mtime_ns"]
        if kind == "file":
            expected.extend(["size", "sha256", "link_to"])
            assert json_int(row["size"]) >= 0 and json_int(row["size"]) <= 1099511627776, "invalid size"
            assert regex_fullmatch("[0-9a-f]{64}", json_string(row["sha256"])), "invalid digest"
            original: str = json_string(row["link_to"])
            if original != "":
                assert original in files, "hard link needs an earlier file"
                assert json_string(files[original]["link_to"]) == "", "hard link chains are unsupported"
                for key in ["size", "mode", "mtime_ns", "sha256"]:
                    assert row[key] == files[original][key], "hard link metadata differs"
            files[name] = row
        elif kind == "symlink":
            expected.append("target")
            target: str = json_string(row["target"])
            assert target != "" and "\x00" not in target and len(target.encode()) <= 4096, "invalid link"
            assert json_int(row["mode"]) == 511, "invalid symlink mode"
        else:
            assert kind == "directory", "unsupported entry kind"
        fields(row, expected)
        assert json_int(row["mode"]) >= 0 and json_int(row["mode"]) <= 511, "invalid mode"
        json_int(row["mtime_ns"])
        assert name not in seen, "duplicate path"
        if len(seen) == 0:
            assert name == "" and kind == "directory", "missing root"
        else:
            parent: str = path_parent(name)
            if parent == ".":
                parent = ""
            assert parent in seen and seen[parent] == "directory", "missing parent directory"
        seen[name] = kind
    return body


def load_all(repo: str) -> dict[int, Json]:
    versions: dict[int, Json] = {}
    for name in directory_names(path_join(repo, "versions"), 1000):
        assert name.endswith(".json"), "unexpected version entry"
        body: Json = validate(document(path_join(repo, "versions/" + name)), name[:-5])
        sequence: int = json_int(body["sequence"])
        assert sequence not in versions, "duplicate sequence"
        versions[sequence] = body
    for name in directory_names(path_join(repo, "objects"), 100000):
        assert regex_fullmatch("[0-9a-f]{64}", name), "unexpected object name"
        assert json_string(stamp(path_join(repo, "objects/" + name))["kind"]) == "file", "invalid object kind"
    return versions
