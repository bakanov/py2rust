"""Bounded input, stable identities and content guards for protected local trees."""

from py2rust.stdlib import (
    Json,
    Sha256,
    file_open,
    file_read,
    file_size,
    json_dumps,
    json_equal,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_parent,
    path_resolve,
    path_stat,
    read_link,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_dumps(value).encode()))


def document(path: str, limit: int) -> Json:
    assert not path_is_symlink(path), "document cannot be a symlink"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= limit, "document exceeds byte limit"
        data: bytes = file_read(handle, limit + 1)
        assert len(data) <= limit, "document grew beyond byte limit"
        return json_loads(data.decode())


def relative(name: str) -> str:
    assert len(name.encode()) <= 1024 and "\x00" not in name, "invalid relative path"
    for component in name.split("/"):
        assert component not in ["", ".", ".."], "unsafe relative path: " + name
        assert len(component.encode()) <= 255, "filename exceeds 255 bytes"
        assert not component.startswith(".py2rust-rename"), "reserved rename namespace"
    return name


def identity(path: str) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "directory", "parent must be a directory: " + path
    return {"device": info["device"], "inode": info["inode"]}


def signature(path: str, limit: int) -> Json:
    info: Json = path_stat(path, False)
    kind: str = json_string(info["kind"])
    assert kind in ["file", "directory", "symlink"], "unsupported entry: " + path
    result: Json = {
        "kind": kind,
        "device": info["device"],
        "inode": info["inode"],
        "mode": info["mode"],
        "mtime_ns": info["mtime_ns"],
    }
    if kind == "file":
        state: Sha256 = sha256_new()
        total: int = 0
        with file_open(path, "rb") as handle:
            assert file_size(handle) <= limit, "file exceeds hash limit: " + path
            chunk: bytes = file_read(handle, 65536)
            while len(chunk) > 0:
                total = total + len(chunk)
                assert total <= limit, "file grew beyond hash limit"
                state = sha256_update(state, chunk)
                chunk = file_read(handle, 65536)
        result["size"] = total
        result["sha256"] = sha256_digest(state)
    if kind == "symlink":
        result["target"] = read_link(path)
    after: Json = path_stat(path, False)
    for key in ["device", "inode", "kind", "size", "mode", "mtime_ns", "ctime_ns"]:
        assert json_equal(info[key], after[key]), "entry changed while inspecting: " + path
    return result


def parents(root: str, names: list[str]) -> Json:
    result: Json = {".": identity(root)}
    for name in names:
        parent: str = path_parent(name)
        while parent != ".":
            path: str = path_join(root, parent)
            assert path_resolve(path) == path, "symlinked parent: " + parent
            result[parent] = identity(path)
            parent = path_parent(parent)
    return result
