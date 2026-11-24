"""Snapshot inputs, stage reports, then atomically commit the locked ledger before publishing reports."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns/iteration
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
    replace_file,
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
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file" and json_int(value["links"]) == 1, "expected unaliased regular file"
    del value["atime_ns"]
    return value


def read(path: str, limit: int) -> Document:
    before: Json = stamp(path)
    assert json_int(before["size"]) <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < json_int(before["size"]):
            chunk: bytes = file_read(handle, min(65536, json_int(before["size"]) - len(data)))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    return Document(path, before, data)


def checkpoint(label: str) -> None:
    assert env_get("INVENTORY_FAULT", "") != label, "injected failure: " + label
    if env_get("INVENTORY_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("INVENTORY_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def unchanged(document: Document) -> None:
    if document.stamp is None:
        assert not present(document.path), "ledger appeared before commit"
    else:
        assert json_equal(document.stamp, stamp(document.path)), "input changed before commit"
    return


def finish(
    output: str, files: dict[str, bytes], request: Document, store: Document, data: bytes, changed: bool
) -> None:
    staging: str = path_join(path_parent(output), ".inventory-report-" + random_token())
    temporary: str = path_join(path_parent(store.path), ".inventory-state-" + random_token())
    created: bool = False
    mkdir_new(staging)
    try:
        for name in files:
            with file_open(path_join(staging, name), "x+b") as handle:
                file_write(handle, files[name])
                file_sync(handle)
        sync_directory(staging)
        if changed:
            with file_open(temporary, "x+b") as handle:
                created = True
                file_write(handle, data)
                file_sync(handle)
        checkpoint("prepared")
        unchanged(request)
        unchanged(store)
        assert not present(output), "output appeared before commit"
        if changed:
            if store.stamp is None:
                rename_no_replace(temporary, store.path)
            else:
                replace_file(temporary, store.path)
            sync_directory(path_parent(store.path))
            checkpoint("committed")
        rename_no_replace(staging, output)
        sync_directory(path_parent(output))
        checkpoint("published")
    except Exception:
        if created and present(temporary):
            remove_file(temporary)
        if present(staging):
            for name in files:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
    return
