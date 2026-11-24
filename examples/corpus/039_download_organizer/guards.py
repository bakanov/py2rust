"""Bounded documents, content signatures and safe paths inside a protected tree."""

from py2rust.stdlib import (
    Json,
    Sha256,
    file_open,
    file_read,
    file_size,
    file_sync,
    json_canonical,
    json_equal,
    json_int,
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


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(names), "invalid fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def document(path: str) -> Json:
    assert json_string(path_stat(path, False)["kind"]) == "file", "document must be regular"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 2097152, "document exceeds 2 MiB"
        data: bytes = b""
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= 2097152, "document grew beyond 2 MiB"
        return json_loads(data.decode())


def relative(name: str) -> str:
    assert len(name.encode()) <= 2048 and "\x00" not in name, "invalid relative path"
    parts: list[str] = name.split("/")
    assert len(parts) <= 8, "path exceeds eight components"
    for part in parts:
        assert part not in ["", ".", ".."] and len(part.encode()) <= 255, "invalid path component"
        assert not part.startswith(".py2rust-organize"), "reserved organizer name"
    return name


def identity(path: str) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "directory", "parent must be a directory: " + path
    return {"device": info["device"], "inode": info["inode"]}


def parents(root: str, targets: list[str]) -> Json:
    result: Json = {".": identity(root)}
    for target in targets:
        parent: str = path_parent(relative(target))
        while parent != ".":
            result[parent] = None
            parent = path_parent(parent)
    # Ancestors precede their descendants; never follow a symlinked parent.
    for parent in json_keys(result):
        if parent != ".":
            path: str = path_join(root, parent)
            result[parent] = identity(path) if present(path) else None
    return result


def signature(path: str, limit: int) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "file", "source must be regular: " + path
    state: Sha256 = sha256_new()
    count: int = 0
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= limit, "hash byte budget exceeded"
        while True:
            data: bytes = file_read(handle, 65536)
            if len(data) == 0:
                break
            count = count + len(data)
            assert count <= limit, "source grew beyond hash byte budget"
            state = sha256_update(state, data)
        file_sync(handle)
    after: Json = path_stat(path, False)
    for key in ["kind", "device", "inode", "size", "mode", "links", "mtime_ns", "ctime_ns"]:
        assert json_equal(info[key], after[key]), "source changed while hashing: " + path
    del info["atime_ns"]
    del info["ctime_ns"]
    info["sha256"] = sha256_digest(state)
    return info


def sidecar(value: str, root: str) -> str:
    path: str = path_join(path_resolve(path_parent(value)), path_name(value))
    assert path != root and not path.startswith(root + "/"), "sidecars must be outside the root"
    if present(path):
        info: Json = path_stat(path, False)
        assert (
            json_string(info["kind"]) == "file" and json_int(info["links"]) == 1
        ), "sidecar must be regular and unlinked elsewhere"
    return path


def distinct(paths: list[str]) -> None:
    for index in range(len(paths)):
        for other in range(index + 1, len(paths)):
            assert paths[index] != paths[other], "sidecar paths collide"
            if present(paths[index]) and present(paths[other]):
                assert not path_same(paths[index], paths[other]), "sidecar files alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
