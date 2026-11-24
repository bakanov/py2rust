"""Bounded input snapshots and atomic publication of complete report directories."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns and subset dictionary iteration
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_sync,
    file_write,
    json_equal,
    json_int,
    json_string,
    mkdir_new,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    random_token,
    remove_dir,
    remove_file,
    rename_no_replace,
    sleep,
    sync_directory,
)


@dataclass
class Document:
    path: str
    stamp: Json
    data: bytes


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file" and json_int(result["links"]) == 1, "expected unaliased regular input"
    del result["atime_ns"]
    return result


def read(path: str, limit: int) -> Document:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            chunk: bytes = file_read(handle, min(65536, size - len(data)))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    return Document(path, before, data)


def checkpoint(label: str) -> None:
    assert env_get("PPM_FAULT", "") != label, "injected failure: " + label
    if env_get("PPM_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("PPM_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def publish(output: str, files: dict[str, bytes], inputs: list[Document]) -> None:
    parent: str = path_parent(output)
    staging: str = path_join(parent, ".ppm-" + random_token())
    mkdir_new(staging)
    try:
        for name in files:
            with file_open(path_join(staging, name), "x+b") as handle:
                for start in range(0, len(files[name]), 65536):
                    file_write(handle, files[name][start : start + 65536])
                file_sync(handle)
        sync_directory(staging)
        checkpoint("staged")
        for document in inputs:
            assert json_equal(document.stamp, stamp(document.path)), "input changed before publication"
        rename_no_replace(staging, output)
        sync_directory(parent)
        checkpoint("published")
    except Exception:
        if present(staging):
            for name in files:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
    return
