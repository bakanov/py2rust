"""Owned log files and atomic status snapshots for one foreground supervision session."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from py2rust.stdlib import (
    Json, env_get, file_open, file_read, file_seek, file_sync, file_write, json_equal, json_int, json_string,
    path_exists, path_is_symlink, path_join, path_name, path_parent, path_resolve, path_stat, replace_file,
    sha256_digest, sha256_new, sha256_update, Sha256, sleep, sync_directory,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def regular(path: str) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "file" and json_int(info["links"]) == 1, "expected unaliased regular file"
    del info["atime_ns"]
    return info


def read(path: str, limit: int) -> bytes:
    assert json_int(regular(path)["size"]) <= limit, "file exceeds limit"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        data = file_read(handle, limit + 1)
    assert len(data) <= limit, "file exceeds limit"
    return data


def unchanged(config: Json) -> None:
    assert json_equal(regular(json_string(config["path"])), config["stamp"]), "configuration changed"
    return


def checkpoint(label: str) -> None:
    assert env_get("SUPERVISOR_FAULT", "") != label, "injected failure: " + label
    if env_get("SUPERVISOR_PAUSE", "") == label:
        print("PAUSED " + label)
        released: bool = False
        for attempt in range(3000):
            if present(env_get("SUPERVISOR_RELEASE", "")):
                released = True
                break
            sleep(0.01)
        assert released, "pause deadline"
    return


def append(path: str, data: bytes) -> None:
    regular(path)
    with file_open(path, "r+b") as handle:
        file_seek(handle, 0, 2)
        file_write(handle, data)
    return


def seal(path: str) -> Json:
    before: Json = regular(path)
    digest: Sha256 = sha256_new()
    size: int = 0
    with file_open(path, "r+b") as handle:
        while True:
            data: bytes = file_read(handle, 65536)
            if len(data) == 0:
                break
            size = size + len(data)
            assert size <= 65536, "unexpected log size"
            digest = sha256_update(digest, data)
        file_sync(handle)
    assert json_equal(before, regular(path)), "log changed"
    return {"bytes": size, "sha256": sha256_digest(digest)}


def atomic(config: Json, data: bytes, label: str) -> None:
    assert len(data) <= 262144, "status exceeds 256 KiB"
    root: str = json_string(config["state"])
    staging: str = path_join(root, "status.tmp")
    target: str = path_join(root, "status.json")
    if present(staging):
        regular(staging)
    with file_open(staging, "w+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    stamp: Json = regular(staging)
    checkpoint("staged:" + label)
    unchanged(config)
    assert json_equal(stamp, regular(staging)), "status staging changed"
    if present(target):
        regular(target)
    replace_file(staging, target)
    sync_directory(root)
    checkpoint("committed:" + label)
    return
