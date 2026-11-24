"""Bounded regular-file snapshots and explicit filesystem paths."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from py2rust.stdlib import (
    Json, env_get, file_open, file_read, json_equal, json_int, json_string, path_exists, path_is_symlink,
    path_join, path_name, path_parent, path_resolve, path_stat, sha256_digest, sha256_new, sha256_update, sleep,
)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith("/" if root == "/" else root + "/")


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    del result["atime_ns"]
    return result


def regular(path: str) -> Json:
    result: Json = stamp(path)
    assert (
        json_string(result["kind"]) == "file" and json_int(result["links"]) == 1
    ), "expected unaliased regular control"
    return result


def read(path: str, limit: int) -> bytes:
    before: Json = regular(path)
    size: int = json_int(before["size"])
    assert size <= limit, "control byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            part: bytes = file_read(handle, min(65536, size - len(data)))
            assert len(part) > 0, "control shrank while reading"
            data = data + part
    assert json_equal(before, stamp(path)), "control changed while reading"
    return data


def hashed(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def identity(entry: Json) -> str:
    return str(json_int(entry["device"])) + ":" + str(json_int(entry["inode"])) + ":" + json_string(entry["kind"])


def checkpoint(label: str) -> None:
    assert env_get("WATCH_FAULT", "") != label, "injected failure: " + label
    if env_get("WATCH_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("WATCH_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
