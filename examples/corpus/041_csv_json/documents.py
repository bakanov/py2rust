"""Bounded input snapshots and atomic publication of data with its rejection report."""

from dataclasses import dataclass

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_size,
    json_equal,
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
    write_text_atomic,
)


@dataclass
class Document:
    path: str
    stamp: Json
    data: bytes


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid document path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file", "input must be a regular file"
    del result["atime_ns"]
    return result


def read(path: str, limit: int) -> Document:
    before: Json = stamp(path)
    data: bytes = b""
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= limit, "input byte limit exceeded"
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= limit, "input grew beyond byte limit"
    assert json_equal(before, stamp(path)), "input changed while reading"
    data.decode()
    return Document(path, before, data)


def checkpoint(label: str) -> None:
    assert env_get("CONVERT_FAIL", "") != label, "injected failure: " + label
    if env_get("CONVERT_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("CONVERT_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def publish(output: str, filename: str, data: str, report: str) -> None:
    assert not present(output), "output directory already exists"
    parent: str = path_parent(output)
    staging: str = path_join(parent, ".csv-json-" + random_token())
    mkdir_new(staging)
    try:
        checkpoint("stage")
        write_text_atomic(path_join(staging, filename), data)
        checkpoint("data")
        write_text_atomic(path_join(staging, "report.json"), report)
        checkpoint("report")
        sync_directory(staging)
        checkpoint("ready")
        rename_no_replace(staging, output)
        checkpoint("published")
        sync_directory(parent)
    except Exception:
        if present(staging):
            for name in [filename, "report.json"]:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise
