"""Streaming hashes and copies: unchanged objects are read, never rewritten."""

from common import stamp, unchanged

from py2rust.stdlib import (
    Json,
    Sha256,
    file_open,
    file_read,
    file_size,
    file_sync,
    file_write,
    json_int,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(path: str, size: int) -> str:
    before: Json = stamp(path)
    assert json_string(before["kind"]) == "file" and json_int(before["size"]) == size, "invalid object"
    state: Sha256 = sha256_new()
    count: int = 0
    with file_open(path, "rb") as handle:
        assert file_size(handle) == size, "file size changed"
        while count < size:
            data: bytes = file_read(handle, min(65536, size - count))
            assert len(data) > 0, "unexpected EOF"
            count = count + len(data)
            state = sha256_update(state, data)
        assert file_read(handle, 1) == b"", "file grew"
    unchanged(path, before)
    return sha256_digest(state)


def copy(source: str, destination: str, size: int) -> str:
    before: Json = stamp(source)
    assert json_string(before["kind"]) == "file" and json_int(before["size"]) == size, "invalid copy source"
    state: Sha256 = sha256_new()
    count: int = 0
    with file_open(source, "rb") as incoming:  # noqa: SIM117 - one scoped resource per statement
        with file_open(destination, "x+b") as output:
            while count < size:
                data: bytes = file_read(incoming, min(65536, size - count))
                assert len(data) > 0, "unexpected EOF"
                file_write(output, data)
                count = count + len(data)
                state = sha256_update(state, data)
            assert file_read(incoming, 1) == b"", "copy source grew"
            file_sync(output)
    unchanged(source, before)
    return sha256_digest(state)
