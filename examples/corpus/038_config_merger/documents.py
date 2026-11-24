"""Stable bounded reads and publication paths that cannot replace an input."""

from dataclasses import dataclass

from model import locations

from py2rust.stdlib import (
    Json,
    file_open,
    file_read,
    file_size,
    json_equal,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    path_stat,
    sha256_digest,
    sha256_new,
    sha256_update,
)


@dataclass
class Document:
    path: str
    present: bool
    stamp: Json
    digest: str
    value: Json
    size: int
    nodes: int


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(names), "invalid fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    if not present(path):
        return None
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "file", "expected a regular file: " + path
    del info["atime_ns"]
    return info


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid document path"
    joined: str = path_join(base, path)
    parent: str = path_resolve(path_parent(joined))
    assert json_string(path_stat(parent, False)["kind"]) == "directory", "document parent must exist"
    return path_join(parent, path_name(joined))


def read(path: str, required: bool) -> Document:
    before: Json = stamp(path)
    if before is None:
        assert not required, "required layer is missing: " + path
        return Document(path, False, None, "", None, 0, 0)
    data: bytes = b""
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 1048576, "document exceeds 1 MiB: " + path
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= 1048576, "document grew beyond 1 MiB: " + path
    assert json_equal(before, stamp(path)), "document changed while reading: " + path
    value: Json = json_loads(data.decode())
    assert json_kind(value) == "object", "layer must be an object: " + path
    nodes: int = len(locations(value, "", 0))
    digest: str = sha256_digest(sha256_update(sha256_new(), data))
    return Document(path, True, before, digest, value, len(data), nodes)


def distinct(path: str, others: list[str]) -> None:
    for other in others:
        assert path != other, "document paths collide"
        if present(path) and present(other):
            assert not path_same(path, other), "document files alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def revalidate(documents: list[Document]) -> None:
    for document in documents:
        assert json_equal(document.stamp, stamp(document.path)), "input changed: " + document.path
    return  # noqa: PLR1711 - explicit return required by repository guidelines
