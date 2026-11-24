"""Bounded snapshots, input guards and observable transaction boundaries."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from dataclasses import dataclass
from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    json_equal,
    json_int,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
)


@dataclass
class Document:
    path: str
    metadata: Json
    data: bytes


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def inside(path: str, root: str) -> bool:
    return path == root or path.startswith("/" if root == "/" else root + "/")


def regular(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file" and json_int(value["links"]) == 1, "expected unaliased regular file"
    del value["atime_ns"]
    return value


def read(path: str, limit: int) -> Document:
    before: Json = regular(path)
    size: int = json_int(before["size"])
    assert size <= limit, "file byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            part: bytes = file_read(handle, min(65536, size - len(data)))
            assert len(part) > 0, "file shrank during read"
            data = data + part
    assert json_equal(before, regular(path)), "file changed during read"
    return Document(path, before, data)


def unchanged(documents: list[Document]) -> None:
    for document in documents:
        assert json_equal(document.metadata, regular(document.path)), "input changed before commit"
    return


def hashed(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def checkpoint(phase: str, completed: int) -> None:
    label: str = phase + ":" + str(completed)
    assert env_get("BATCH_FAULT", "") != label, "injected failure: " + label
    if env_get("BATCH_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("BATCH_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
