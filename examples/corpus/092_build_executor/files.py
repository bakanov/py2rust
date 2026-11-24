"""Bounded file fingerprints and atomic control writes; metadata guards detect concurrent edits."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from py2rust.stdlib import (
    Json, Sha256, env_get, file_open, file_read, file_sync, file_write, json_equal, json_int, json_keys,
    json_string, path_exists, path_is_symlink, path_join, path_name, path_parent, path_resolve, path_stat,
    remove_dir, remove_file, replace_file, sha256_digest, sha256_new, sha256_update, sleep, sync_directory,
)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith("/" if root == "/" else root + "/")


def regular(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file" and json_int(value["links"]) == 1, "expected unaliased regular file"
    del value["atime_ns"]
    return value


def hashed(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def read(path: str, limit: int) -> bytes:
    before: Json = regular(path)
    size: int = json_int(before["size"])
    assert size <= limit, "file byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            part: bytes = file_read(handle, min(65536, size - len(data)))
            assert len(part) > 0, "file shrank while reading"
            data = data + part
    assert json_equal(before, regular(path)), "file changed while reading"
    return data


def scan(path: str) -> Json:
    before: Json = regular(path)
    remaining: int = json_int(before["size"])
    assert remaining <= 4194304, "artifact/input exceeds 4 MiB"
    digest: Sha256 = sha256_new()
    with file_open(path, "rb") as handle:
        while remaining > 0:
            part: bytes = file_read(handle, min(65536, remaining))
            assert len(part) > 0, "file shrank while hashing"
            digest = sha256_update(digest, part)
            remaining = remaining - len(part)
    assert json_equal(before, regular(path)), "file changed while hashing"
    return {
        "stamp": before,
        "value": {"bytes": before["size"], "mode": before["mode"], "sha256": sha256_digest(digest)},
    }


def unchanged(guards: Json) -> None:
    for path in json_keys(guards):
        assert json_equal(guards[path], regular(path)), "input changed before commit"
    return


def checkpoint(label: str) -> None:
    assert env_get("BUILD_FAULT", "") != label, "injected failure: " + label
    if env_get("BUILD_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("BUILD_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def discard(path: str) -> None:
    if present(path):
        if json_string(path_stat(path, False)["kind"]) == "directory":
            remove_dir(path)
        else:
            remove_file(path)
    return


def atomic(path: str, data: bytes, guards: Json, label: str) -> None:
    assert len(data) <= 2097152, "control file exceeds 2 MiB"
    temporary: str = path_join(path_parent(path), "control.tmp")
    for item in [path, temporary]:
        if present(item):
            regular(item)
    with file_open(temporary, "w+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    written: Json = regular(temporary)
    checkpoint("staged:" + label)
    unchanged(guards)
    assert json_equal(written, regular(temporary)), "staged control changed"
    if present(path):
        regular(path)
    replace_file(temporary, path)
    sync_directory(path_parent(path))
    checkpoint("committed:" + label)
    return
