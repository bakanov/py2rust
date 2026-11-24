# ruff: noqa: PLR1711, PLC0206 - explicit returns and supported subset operations
"""Bounded immutable input snapshots and atomic publication of a complete bloom bundle."""

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
    assert path != "" and "\x00" not in path, "invalid document path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file", "input must be a regular file"
    del result["atime_ns"]
    return result


def read(path: str, limit: int) -> Document:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            chunk: bytes = file_read(handle, size - len(data))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    data.decode()
    return Document(path, before, data)


def checkpoint(label: str) -> None:
    assert env_get("BLOOM_FAIL", "") != label, "injected failure: " + label
    if env_get("BLOOM_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("BLOOM_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def unchanged(documents: list[Document]) -> None:
    for document in documents:
        assert json_equal(document.stamp, stamp(document.path)), "input changed before publication"
    return


def publish(output: str, files: dict[str, bytes], documents: list[Document]) -> None:
    assert not present(output), "output directory already exists"
    parent: str = path_parent(output)
    staging: str = path_join(parent, ".bloom-" + random_token())
    mkdir_new(staging)
    try:
        checkpoint("stage")
        for name in files:
            with file_open(path_join(staging, name), "x+b") as handle:
                file_write(handle, files[name])
                file_sync(handle)
            checkpoint(name)
        sync_directory(staging)
        checkpoint("ready")
        unchanged(documents)
        rename_no_replace(staging, output)
        checkpoint("published")
        sync_directory(parent)
    except Exception:
        if present(staging):
            for name in files:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
    return
