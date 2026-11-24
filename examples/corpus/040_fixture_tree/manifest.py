"""Validate every payload and collision before starting to create a fixture tree."""

from dataclasses import dataclass

from documents import absolute, fields, identity, observe, present, relative

from py2rust.stdlib import (
    Json,
    base64_decode,
    json_array,
    json_int,
    json_keys,
    json_string,
    path_join,
    path_parent,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Manifest:
    receipt: Json
    payloads: dict[str, bytes]


def parse(value: Json) -> Manifest:
    fields(value, ["root", "entries", "max_entries", "max_bytes"])
    root: str = absolute(json_string(value["root"]))
    assert root != "/", "filesystem root is not a fixture root"
    maximum: int = json_int(value["max_entries"])
    budget: int = json_int(value["max_bytes"])
    assert 1 <= maximum <= 1000 and 0 <= budget <= 4194304, "invalid fixture budget"
    declared: list[Json] = json_array(value["entries"])
    assert len(declared) <= maximum, "too many declared entries"
    directories: set[str] = {""}
    seen: set[str] = set()
    payloads: dict[str, bytes] = {}
    total: int = 0
    for entry in declared:
        kind: str = json_string(entry["kind"])
        fields(entry, ["path", "kind"] if kind == "directory" else ["path", "kind", "data"])
        name: str = relative(json_string(entry["path"]))
        assert name not in seen, "duplicate fixture path"
        seen.add(name)
        if kind == "directory":
            directories.add(name)
        else:
            assert kind in ["text", "base64"], "invalid fixture kind"
            text: str = json_string(entry["data"])
            data: bytes = text.encode() if kind == "text" else base64_decode(text)
            assert len(data) <= 1048576, "fixture exceeds 1 MiB"
            total = total + len(data)
            assert total <= budget, "total fixture byte budget exceeded"
            payloads[name] = data
        parent: str = path_parent(name)
        while parent != ".":
            directories.add(parent)
            parent = path_parent(parent)
    assert len(directories) + len(payloads) <= maximum, "implicit directories exceed entry budget"
    entries: Json = {}
    for directory in directories:
        assert directory not in payloads, "a file is also required as a directory"
        entries[directory] = {"kind": "directory", "owned": True, "stamp": None, "size": 0, "sha256": ""}
    for name in payloads:  # noqa: PLC0206 - typed dictionary key iteration
        entries[name] = {
            "kind": "file",
            "owned": True,
            "stamp": None,
            "size": len(payloads[name]),
            "sha256": sha256_digest(sha256_update(sha256_new(), payloads[name])),
        }
    # A parent always sorts before its descendants, so no symlink is followed.
    for name in json_keys(entries):
        path: str = path_join(root, name)
        entry: Json = entries[name]
        if present(path):
            assert json_string(entry["kind"]) == "directory", "fixture path already exists: " + name
            entry["stamp"] = observe(path, "directory")
            entry["owned"] = False
            entries[name] = entry
    body: Json = {
        "version": 1,
        "root": root,
        "parent": identity(path_parent(root)),
        "phase": "building",
        "step": 0,
        "entries": entries,
        "bytes": total,
    }
    return Manifest(body, payloads)
