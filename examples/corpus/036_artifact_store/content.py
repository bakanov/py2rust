"""Bounded streaming reads and exclusive copies with source-change guards."""

from common import stamp

from py2rust.stdlib import (
    Json,
    Sha256,
    file_open,
    file_read,
    file_sync,
    file_write,
    json_equal,
    json_int,
    json_string,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest(path: str, size: int) -> str:
    before: Json = stamp(path)
    assert json_string(before["kind"]) == "file" and json_int(before["size"]) == size, "invalid blob"
    hashed: Sha256 = sha256_new()
    count: int = 0
    with file_open(path, "rb") as handle:
        while count < size:
            data: bytes = file_read(handle, min(65536, size - count))
            assert len(data) > 0, "unexpected EOF"
            hashed = sha256_update(hashed, data)
            count = count + len(data)
        assert file_read(handle, 1) == b"", "blob grew"
    assert json_equal(stamp(path), before), "blob changed"
    return sha256_digest(hashed)


def copy(source: str, destination: str, size: int) -> str:
    before: Json = stamp(source)
    assert json_string(before["kind"]) == "file" and json_int(before["size"]) == size, "invalid copy source"
    hashed: Sha256 = sha256_new()
    count: int = 0
    with file_open(source, "rb") as incoming:  # noqa: SIM117 - one scoped resource per statement
        with file_open(destination, "x+b") as output:
            while count < size:
                data: bytes = file_read(incoming, min(65536, size - count))
                assert len(data) > 0, "unexpected EOF"
                file_write(output, data)
                hashed = sha256_update(hashed, data)
                count = count + len(data)
            assert file_read(incoming, 1) == b"", "source grew"
            file_sync(output)
    assert json_equal(stamp(source), before), "source changed"
    return sha256_digest(hashed)
