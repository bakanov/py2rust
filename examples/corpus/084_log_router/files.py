"""Bounded regular-file reads and streaming verification of committed prefixes."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
from py2rust.stdlib import (
    Json, Sha256, file_open, file_read, json_int, json_string, path_exists, path_is_symlink, path_join, path_name,
    path_parent, path_resolve, path_stat, sha256_digest, sha256_new, sha256_update
)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def regular(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert (
        json_string(result["kind"]) == "file" and json_int(result["links"]) == 1
    ), "expected an unaliased regular file"
    return result


def identity(path: str) -> str:
    info: Json = regular(path)
    return str(json_int(info["device"])) + ":" + str(json_int(info["inode"]))


def read(path: str, limit: int) -> bytes:
    assert json_int(regular(path)["size"]) <= limit, "file exceeds byte limit"
    result: bytes = b""
    with file_open(path, "rb") as handle:
        while len(result) <= limit:
            part: bytes = file_read(handle, min(65536, limit + 1 - len(result)))
            result = result + part
            assert len(result) <= limit, "file grew beyond byte limit"
            if len(part) == 0:
                break
    return result


def hashed(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def prefix(path: str, size: int) -> Sha256:
    result: Sha256 = sha256_new()
    remaining: int = size
    with file_open(path, "rb") as handle:
        while remaining > 0:
            part: bytes = file_read(handle, min(remaining, 65536))
            assert len(part) > 0, "source truncated before committed offset"
            result = sha256_update(result, part)
            remaining = remaining - len(part)
    return result
