"""Capture a bounded stable tree, hashing files and recording symlinks without following them."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLC0206 - supported dictionary iteration
from configuration import relative
from files import checkpoint, identity, stamp
from py2rust.stdlib import (
    Json, Sha256, directory_names, file_open, file_read, json_equal, json_int, json_string, path_join, read_link,
    sha256_digest, sha256_new, sha256_update,
)


def capture(config: Json) -> Json:
    root: str = json_string(config["root"])
    before: dict[str, Json] = {"": stamp(root)}
    assert identity(before[""]) == json_string(config["identity"]), "observed root was replaced"
    pending: list[str] = [""]
    entries: Json = {}
    total: int = 0
    cursor: int = 0
    while cursor < len(pending):
        parent: str = pending[cursor]
        cursor = cursor + 1
        for name in directory_names(path_join(root, parent), 256):
            key: str = name if parent == "" else parent + "/" + name
            relative(key)
            assert len(before) <= 256, "tree exceeds 256 entries"
            path: str = path_join(root, key)
            info: Json = stamp(path)
            before[key] = info
            kind: str = json_string(info["kind"])
            assert kind in ["file", "directory", "symlink"], "unsupported filesystem entry"
            size: int = json_int(info["size"]) if kind == "file" else 0
            digest: str = ""
            target: str = ""
            if kind == "directory":
                pending.append(key)
            elif kind == "symlink":
                target = read_link(path)
                assert len(target.encode()) <= 1024, "symlink target exceeds 1024 bytes"
            else:
                assert size <= 1048576, "file exceeds 1 MiB"
                total = total + size
                assert total <= 4194304, "scan exceeds 4 MiB"
                state: Sha256 = sha256_new()
                remaining: int = size
                with file_open(path, "rb") as handle:
                    while remaining > 0:
                        part: bytes = file_read(handle, min(65536, remaining))
                        assert len(part) > 0, "file shrank during scan"
                        state = sha256_update(state, part)
                        remaining = remaining - len(part)
                digest = sha256_digest(state)
            entries[key] = {
                "kind": kind,
                "device": info["device"],
                "inode": info["inode"],
                "mode": info["mode"],
                "links": info["links"] if kind == "file" else 0,
                "size": size,
                "mtime_ns": 0 if kind == "directory" else info["mtime_ns"],
                "digest": digest,
                "target": target,
            }
    checkpoint("scanned")
    for key in before:
        assert json_equal(before[key], stamp(path_join(root, key))), "tree changed during scan"
    return entries
