"""Bounded input snapshots and atomic publication of complete report directories."""

# ruff: noqa: PLR1711, PLC0206 - explicit returns and subset dictionary iteration
from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    directory_names,
    env_get,
    file_open,
    file_read,
    file_sync,
    file_write,
    json_equal,
    json_int,
    json_string,
    mkdir_new,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    random_token,
    remove_dir,
    remove_file,
    rename_no_replace,
    sleep,
    sync_directory,
)


@dataclass
class Document:
    path: str
    stamp: Json
    data: bytes


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file" and json_int(result["links"]) == 1, "expected unaliased regular input"
    del result["atime_ns"]
    return result


def read(path: str, limit: int) -> Document:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            chunk: bytes = file_read(handle, min(65536, size - len(data)))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    return Document(path, before, data)


def checkpoint(label: str) -> None:
    assert env_get("METRICS_FAULT", "") != label, "injected failure: " + label
    if env_get("METRICS_PAUSE", "") == label:
        print("PAUSED " + label)
        release: str = env_get("METRICS_RELEASE", "")
        for attempt in range(3000):
            if release != "" and present(release):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def discover(root: str, excluded: list[str]) -> list[str]:
    pending: list[tuple[str, int]] = [("", 0)]
    sources: list[str] = []
    entries: int = 0
    while len(pending) > 0:
        item: tuple[str, int] = pending.pop()
        relative: str = item[0]
        assert item[1] <= 8, "source directory depth exceeds eight"
        directory: str = path_join(root, relative)
        assert json_string(path_stat(directory, False)["kind"]) == "directory", "source directory required"
        for name in directory_names(directory, 4096):
            entries = entries + 1
            assert entries <= 4096, "source inventory exceeds 4096 entries"
            if name.startswith(".") or name in excluded:
                continue
            child: str = name if relative == "" else relative + "/" + name
            info: Json = path_stat(path_join(root, child), False)
            kind: str = json_string(info["kind"])
            assert kind in ["file", "directory"], "unsupported source-tree entry"
            if kind == "directory":
                pending.append((child, item[1] + 1))
            elif name.endswith(".py"):
                sources.append(child)
                assert len(sources) <= 64, "at most 64 Python modules"
    return sorted(sources)


def publish(
    output: str, files: dict[str, bytes], inputs: list[Document], root: str, excluded: list[str], paths: list[str]
) -> None:
    parent: str = path_parent(output)
    staging: str = path_join(parent, ".metrics-" + random_token())
    mkdir_new(staging)
    try:
        for name in files:
            with file_open(path_join(staging, name), "x+b") as handle:
                file_write(handle, files[name])
                file_sync(handle)
        sync_directory(staging)
        checkpoint("staged")
        assert discover(root, excluded) == paths, "source inventory changed"
        for document in inputs:
            assert json_equal(document.stamp, stamp(document.path)), "input changed before publication"
        rename_no_replace(staging, output)
        sync_directory(parent)
        checkpoint("published")
    except Exception:
        if present(staging):
            for name in files:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
    return
