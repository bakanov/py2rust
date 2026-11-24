"""Owned database files, crash-recoverable initialization and bounded input reads."""

# ruff: noqa: PLR1711, F401 - explicit returns and filesystem facade reexports

from py2rust.stdlib import (
    FileHandle,
    Json,
    env_get,
    file_lock,
    file_open,
    file_read,
    file_seek,
    file_size,
    file_sync,
    file_truncate,
    file_write,
    json_canonical,
    json_equal,
    json_int,
    json_string,
    list_dir,
    mkdir_new,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    remove_file,
    replace_file,
    sleep,
    sync_directory,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file", "expected a regular file"
    del value["atime_ns"]
    return value


def take(handle: FileHandle, count: int) -> bytes:
    data: bytes = b""
    while len(data) < count:
        part: bytes = file_read(handle, count - len(data))
        if len(part) == 0:
            break
        data = data + part
    return data


def read(path: str, limit: int) -> bytes:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        data = take(handle, size)
    assert len(data) == size and json_equal(before, stamp(path)), "input changed while reading"
    return data


def checkpoint(label: str, sequence: int) -> None:
    point: str = label + ":" + str(sequence)
    assert env_get("DB_FAIL", "") != point, "injected failure: " + point
    if env_get("DB_PAUSE", "") == point:
        print("PAUSED " + point)
        signal: str = env_get("DB_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def prepare(directory: str) -> None:
    if not present(directory):
        mkdir_new(directory)
        sync_directory(path_parent(directory))
    assert json_string(path_stat(directory, False)["kind"]) == "directory", "database must be a directory"
    for name in list_dir(directory):
        assert name in ["owner.json", ".lock", "journal.bin", "state.json", "snapshot.next"], "unknown database file"
        assert json_int(stamp(path_join(directory, name))["links"]) == 1, "database file has hard links"
    if not present(path_join(directory, "owner.json")):
        names: list[str] = list_dir(directory)
        assert len(names) == 0 or names == [".lock"], "unowned database is not empty"
    return


def initialize(directory: str, capacity: int) -> None:
    marker: str = path_join(directory, "owner.json")
    journal: str = path_join(directory, "journal.bin")
    expected: bytes = (
        json_canonical({"format": "py2rust-mini-db-v1", "database": directory, "capacity": capacity}) + "\n"
    ).encode()
    observed: bytes = read(marker, 65536) if present(marker) else b""
    if observed == expected:
        assert present(journal), "initialized database is missing its journal"
        return
    assert expected.startswith(observed), "database ownership or capacity mismatch"
    for name in list_dir(directory):
        assert name in ["owner.json", ".lock", "journal.bin"], "incomplete initialization has unexpected files"
    if present(journal):
        assert json_int(stamp(journal)["size"]) == 0, "incomplete owner has a nonempty journal"
    with file_open(marker, "w+b") as handle:
        file_write(handle, expected[:8])
        file_sync(handle)
    sync_directory(directory)
    checkpoint("owner-prefix", 0)
    if not present(journal):
        with file_open(journal, "x+b") as handle:
            file_sync(handle)
    sync_directory(directory)
    checkpoint("journal-created", 0)
    with file_open(marker, "w+b") as handle:
        file_write(handle, expected)
        file_sync(handle)
    sync_directory(directory)
    checkpoint("owner-complete", 0)
    return
