"""Read, compress and verify logs in 64 KiB chunks; preserve source files."""

from documents import checkpoint, stamp

from py2rust.stdlib import (
    Json,
    Sha256,
    file_open,
    file_read,
    gzip_create,
    gzip_finish,
    gzip_open,
    gzip_read,
    gzip_write,
    json_equal,
    json_int,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def digest_file(path: str, maximum: int) -> Json:
    before: Json = stamp(path)
    assert json_int(before["size"]) <= maximum, "file byte limit"
    digest: Sha256 = sha256_new()
    size: int = 0
    with file_open(path, "rb") as source:
        part: bytes = file_read(source, 65536)
        while len(part) > 0:
            size = size + len(part)
            assert size <= maximum, "file grew beyond limit"
            digest = sha256_update(digest, part)
            part = file_read(source, 65536)
    assert json_equal(before, stamp(path)), "file changed while reading"
    return {"size": size, "sha256": sha256_digest(digest)}


def decoded(path: str, compressed: int, expanded: int) -> Json:
    before: Json = stamp(path)
    digest: Sha256 = sha256_new()
    size: int = 0
    with gzip_open(path, compressed, expanded) as source:
        part: bytes = gzip_read(source, 65536)
        while len(part) > 0:
            size = size + len(part)
            digest = sha256_update(digest, part)
            part = gzip_read(source, 65536)
    assert json_equal(before, stamp(path)), "archive changed while decoding"
    return {"size": size, "sha256": sha256_digest(digest)}


def compress(path: str, staging: str, level: int, compressed: int, expanded: int) -> Json:
    before: Json = stamp(path)
    assert json_int(before["size"]) <= expanded, "source exceeds expansion budget"
    digest: Sha256 = sha256_new()
    first: bool = True
    more: bool = True
    with gzip_create(staging, level, compressed, expanded) as output:
        with file_open(path, "rb") as source:
            while more:
                part: bytes = file_read(source, 65536)
                more = len(part) > 0
                if more:
                    gzip_write(output, part)
                    digest = sha256_update(digest, part)
                if first:
                    checkpoint("streaming")
                    first = False
        assert json_equal(before, stamp(path)), "source changed while archiving"
        sizes: tuple[int, int] = gzip_finish(output)
        assert sizes[1] == json_int(before["size"]), "source size changed"
        checkpoint("closed")
        return {"size": sizes[1], "sha256": sha256_digest(digest)}
