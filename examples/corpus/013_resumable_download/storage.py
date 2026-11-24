"""Verified prefixes, crash recovery, and no-clobber publication of complete files."""

import sys

from model import strong_etag

from py2rust.stdlib import (
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_size,
    file_sync,
    file_truncate,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    link_file,
    path_exists,
    path_is_symlink,
    path_parent,
    path_same,
    pretty,
    read_text,
    remove_file,
    sha256_digest,
    sha256_new,
    sha256_update,
    sync_directory,
    write_text_atomic,
)


def target(state: Json) -> str:
    return json_string(state["policy"]["target"])


def stop(point: str) -> None:
    if env_get("DOWNLOAD_STOP", "") == point:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def validate_paths(policy: Json) -> None:
    output: str = json_string(policy["target"])
    paths: list[str] = [
        env_get("DOWNLOAD_CONFIG", "download.json"),
        output,
        output + ".part",
        output + ".download.json",
        output + ".report.json",
    ]
    for index in range(1, len(paths)):
        assert not path_is_symlink(paths[index]), "download paths must not be symlinks"
    for first in range(len(paths)):
        for second in range(first + 1, len(paths)):
            assert paths[first] != paths[second], "download paths overlap"
            # A ready publication may legitimately link the final and part files.
            if (first != 1 or second != 2) and path_exists(paths[first]) and path_exists(paths[second]):
                assert not path_same(paths[first], paths[second]), "download paths alias"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json) -> None:
    write_text_atomic(target(state) + ".download.json", pretty(state))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def load(policy: Json) -> Json:
    output: str = json_string(policy["target"])
    text: str = read_text(output + ".download.json")
    assert len(text.encode()) <= 65536, "checkpoint exceeds 64 KiB"
    state: Json = json_loads(text)
    assert json_keys(state) == [
        "etag",
        "offset",
        "phase",
        "policy",
        "prefix",
        "total",
        "version",
    ], "invalid checkpoint fields"
    assert json_int(state["version"]) == 1 and json_equal(state["policy"], policy), "checkpoint policy mismatch"
    offset: int = json_int(state["offset"])
    total: int = json_int(state["total"])
    assert offset >= 0 and offset <= json_int(policy["max_bytes"]), "invalid offset"
    assert total >= -1 and total <= json_int(policy["max_bytes"]), "invalid remote size"
    assert total == -1 or offset <= total, "offset exceeds remote size"
    phase: str = json_string(state["phase"])
    assert phase in ["downloading", "ready", "published"], "invalid phase"
    if total == -1:
        assert offset == 0 and json_string(state["etag"]) == "" and phase == "downloading", "invalid initial checkpoint"
    else:
        assert strong_etag(json_string(state["etag"])), "invalid stored ETag"
    if offset == 0:
        assert json_string(state["prefix"]) == sha256_digest(sha256_new()), "invalid empty prefix"
    if phase != "downloading":
        assert offset == total and json_string(state["prefix"]) == json_string(
            policy["sha256"]
        ), "unverified publication"
    return state


def prepare(policy: Json) -> Json:
    validate_paths(policy)
    output: str = json_string(policy["target"])
    if not path_exists(output + ".download.json"):
        assert not path_exists(output) and not path_exists(
            output + ".part"
        ), "destination or orphan partial file already exists"
        state: Json = {
            "version": 1,
            "policy": policy,
            "offset": 0,
            "total": -1,
            "etag": "",
            "prefix": sha256_digest(sha256_new()),
            "phase": "downloading",
        }
        save(state)
    return load(policy)


def hash_prefix(path: str, length: int) -> Sha256:
    digest: Sha256 = sha256_new()
    remaining: int = length
    with file_open(path, "rb") as source:
        assert file_size(source) >= length, "file is shorter than its checkpoint"
        while remaining > 0:
            data: bytes = file_read(source, min(65536, remaining))
            assert len(data) > 0, "unexpected file EOF"
            digest = sha256_update(digest, data)
            remaining = remaining - len(data)
    return digest


def verify_file(path: str, length: int, digest: str) -> None:
    with file_open(path, "rb") as source:
        assert file_size(source) == length, "unexpected file size"
    assert sha256_digest(hash_prefix(path, length)) == digest, "file digest mismatch"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def restore(state: Json) -> Sha256:
    assert not path_exists(target(state)), "destination appeared before publication"
    partial: str = target(state) + ".part"
    offset: int = json_int(state["offset"])
    if not path_exists(partial):
        assert offset == 0, "committed partial file is missing"
        with file_open(partial, "x+b") as created:
            file_sync(created)
        sync_directory(path_parent(partial))
    digest: Sha256 = hash_prefix(partial, offset)
    assert sha256_digest(digest) == json_string(state["prefix"]), "committed prefix was changed"
    with file_open(partial, "r+b") as output:
        if file_size(output) > offset:
            file_truncate(output, offset)
            file_sync(output)
    return digest


def publish(state: Json) -> Json:
    output: str = target(state)
    partial: str = output + ".part"
    total: int = json_int(state["total"])
    expected: str = json_string(state["policy"]["sha256"])
    assert total >= 0 and json_int(state["offset"]) == total, "download is incomplete"
    if json_string(state["phase"]) == "published":
        verify_file(output, total, expected)
        assert not path_exists(partial), "unexpected partial file after publication"
        return state
    if json_string(state["phase"]) == "downloading":
        verify_file(partial, total, expected)
        state["phase"] = "ready"
        save(state)
    stop("before_publish")
    if path_exists(output):
        verify_file(output, total, expected)
    else:
        verify_file(partial, total, expected)
        link_file(partial, output)
        sync_directory(path_parent(output))
    stop("after_publish")
    if path_exists(partial):
        verify_file(partial, total, expected)
        remove_file(partial)
        sync_directory(path_parent(output))
    state["phase"] = "published"
    save(state)
    return state
