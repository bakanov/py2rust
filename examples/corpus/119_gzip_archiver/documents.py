"""Small metadata snapshots, synced replacement, and deterministic recovery checkpoints."""

# ruff: noqa: PLR1711 - explicit returns
from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_sync,
    file_write,
    json_canonical,
    json_equal,
    json_int,
    json_loads_unique,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    remove_file,
    rename_no_replace,
    replace_file,
    sleep,
    sync_directory,
)


def absolute(path: str, base: str) -> str:
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file" and json_int(result["links"]) == 1, "expected unaliased regular file"
    del result["atime_ns"]
    return result


def load(path: str, limit: int) -> Json:
    before: Json = stamp(path)
    assert json_int(before["size"]) <= limit, "metadata byte limit"
    data: bytearray = bytearray()
    with file_open(path, "rb") as source:
        part: bytes = file_read(source, 65536)
        while len(part) > 0:
            assert len(data) + len(part) <= limit, "metadata grew beyond limit"
            data.extend(part)
            part = file_read(source, 65536)
    assert json_equal(before, stamp(path)), "metadata changed while reading"
    return json_loads_unique(bytes(data).decode("utf-8"))


def discard(root: str, name: str) -> None:
    path: str = path_join(root, name)
    if present(path):
        stamp(path)
        remove_file(path)
        sync_directory(root)
    return


def save(root: str, name: str, value: Json) -> None:
    destination: str = path_join(root, name)
    before: Json = stamp(destination) if present(destination) else None
    temporary: str = "." + name + ".tmp"
    discard(root, temporary)
    with file_open(path_join(root, temporary), "x+b") as output:
        file_write(output, (json_canonical(value) + "\n").encode())
        file_sync(output)
    current: Json = stamp(destination) if present(destination) else None
    assert json_equal(before, current), "metadata changed before replacement"
    if present(destination):
        replace_file(path_join(root, temporary), destination)
    else:
        rename_no_replace(path_join(root, temporary), destination)
    sync_directory(root)
    return


def checkpoint(label: str) -> None:
    assert env_get("GZIP_FAULT", "") != label, "injected failure: " + label
    if env_get("GZIP_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("GZIP_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
