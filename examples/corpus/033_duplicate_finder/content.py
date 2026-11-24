"""Streaming content checks with stable metadata before and after every read."""

import time

from py2rust.stdlib import (
    FileHandle,
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_size,
    json_array,
    json_equal,
    json_int,
    json_string,
    path_exists,
    path_join,
    path_stat,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    del result["atime_ns"]
    return result


def current(row: Json, root: str) -> None:
    for value in json_array(row["paths"]):
        assert json_equal(stamp(path_join(root, json_string(value))), row["stamp"]), "entry changed during scan"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def location(row: Json, root: str) -> str:
    return path_join(root, json_string(row["paths"][0]))


def block(handle: FileHandle, count: int) -> bytes:
    result: bytes = b""
    while len(result) < count:
        chunk: bytes = file_read(handle, count - len(result))
        assert len(chunk) > 0, "file shortened while reading"
        result = result + chunk
    return result


def hash_file(row: Json, config: Json) -> str:
    root: str = json_string(config["root"])
    current(row, root)
    remaining: int = json_int(row["stamp"]["size"])
    state: Sha256 = sha256_new()
    with file_open(location(row, root), "rb") as handle:
        assert file_size(handle) == remaining, "file size changed"
        while remaining > 0:
            chunk: bytes = block(handle, min(remaining, json_int(config["chunk_bytes"])))
            state = sha256_update(state, chunk)
            remaining = remaining - len(chunk)
        assert len(file_read(handle, 1)) == 0, "file grew while hashing"
    current(row, root)
    return sha256_digest(state)


def same_bytes(left: Json, right: Json, config: Json) -> bool:
    root: str = json_string(config["root"])
    current(left, root)
    current(right, root)
    equal: bool = True
    remaining: int = json_int(left["stamp"]["size"])
    with file_open(location(left, root), "rb") as first:  # noqa: SIM117 - one scoped resource per with in this subset
        with file_open(location(right, root), "rb") as second:
            assert file_size(first) == remaining and file_size(second) == remaining, "file size changed"
            while remaining > 0:
                count: int = min(remaining, json_int(config["chunk_bytes"]))
                if block(first, count) != block(second, count):
                    equal = False
                    break
                remaining = remaining - count
            if equal:
                assert len(file_read(first, 1)) == 0 and len(file_read(second, 1)) == 0, "file grew during comparison"
    current(left, root)
    current(right, root)
    return equal


def checkpoint(phase: str) -> None:
    if env_get("DUPLICATE_PAUSE", "") == phase:
        resume: str = env_get("DUPLICATE_CONTINUE", "")
        assert resume != "", "a test pause requires DUPLICATE_CONTINUE"
        print("PAUSED " + phase)
        for _attempt in range(3000):
            if path_exists(resume):
                return
            time.sleep(0.01)
        assert False, "test pause timed out"
    return
