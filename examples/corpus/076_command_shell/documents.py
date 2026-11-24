"""Read bounded snapshots and publish captured streams without replacing existing files."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns and supported subset operations
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
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
    return Document(path, before, data)


def publish(output: str, files: dict[str, bytes]) -> None:
    parent: str = path_parent(output)
    staging: str = path_join(parent, ".shell-" + random_token())
    mkdir_new(staging)
    try:
        for name in files:
            with file_open(path_join(staging, name), "x+b") as handle:
                file_write(handle, files[name])
                file_sync(handle)
        sync_directory(staging)
        rename_no_replace(staging, output)
        sync_directory(parent)
    except Exception:
        if present(staging):
            for name in files:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
    return
