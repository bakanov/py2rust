"""Durable prefixes, uncommitted-tail recovery and publication without overwrite."""

import sys

from model import hash_prefix, manifest, verify

from py2rust.stdlib import (
    Json,
    Sha256,
    env_get,
    file_open,
    file_size,
    file_sync,
    file_truncate,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    link_file,
    list_dir,
    path_exists,
    path_is_symlink,
    path_join,
    path_parent,
    path_same,
    pretty,
    read_text,
    regex_fullmatch,
    remove_file,
    sha256_digest,
    sha256_new,
    sync_directory,
    write_text_atomic,
)


def paths(root: str, name: str) -> tuple[str, str, str]:
    stage: str = path_join(root, ".incoming")
    return (path_join(root, name), path_join(stage, name + ".part"), path_join(stage, name + ".json"))


def fault(point: str) -> None:
    if env_get("XFER_FAULT", "") == point:
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def save(state: Json, names: tuple[str, str, str]) -> None:
    write_text_atomic(names[2], pretty(state))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def prepare(root: str, wanted: Json, policy: dict[str, int]) -> Json:
    manifest(wanted, policy)
    names: tuple[str, str, str] = paths(root, json_string(wanted["name"]))
    for path in names:
        assert not path_is_symlink(path), "transfer paths must not be symlinks"
    for other in [names[0], names[1]]:
        if path_exists(names[2]) and path_exists(other):
            assert not path_same(names[2], other), "checkpoint aliases data"
    if not path_exists(names[2]):
        assert not path_exists(names[0]) and not path_exists(names[1]), "destination or orphan partial already exists"
        count: int = 0
        for name in list_dir(path_parent(names[2])):
            if name.endswith(".json"):
                count = count + 1
        assert count < policy["max_files"], "file capacity exhausted"
        save(
            {"version": 1, "file": wanted, "offset": 0, "prefix": sha256_digest(sha256_new()), "phase": "receiving"},
            names,
        )
    with file_open(names[2], "rb") as handle:
        assert file_size(handle) <= 8192, "checkpoint too large"
    state: Json = json_loads(read_text(names[2]))
    assert json_keys(state) == ["file", "offset", "phase", "prefix", "version"], "invalid checkpoint fields"
    assert json_int(state["version"]) == 1 and json_equal(state["file"], wanted), "checkpoint belongs to another file"
    offset: int = json_int(state["offset"])
    prefix: str = json_string(state["prefix"])
    phase: str = json_string(state["phase"])
    assert offset >= 0 and offset <= json_int(wanted["size"]), "invalid checkpoint offset"
    assert regex_fullmatch("[0-9a-f]{64}", prefix) and phase in [
        "receiving",
        "ready",
        "published",
    ], "invalid checkpoint"
    if offset == 0:
        assert prefix == sha256_digest(sha256_new()), "invalid empty prefix"
    if phase != "receiving":
        assert offset == json_int(wanted["size"]) and prefix == json_string(wanted["sha256"]), "unverified publication"
    return state


def restore(state: Json, names: tuple[str, str, str]) -> Sha256:
    assert not path_exists(names[0]), "destination appeared before publication"
    offset: int = json_int(state["offset"])
    if not path_exists(names[1]):
        assert offset == 0, "committed partial is missing"
        with file_open(names[1], "x+b") as created:
            file_sync(created)
        sync_directory(path_parent(names[1]))
    with file_open(names[1], "r+b") as output:
        assert file_size(output) >= offset and file_size(output) <= json_int(
            state["file"]["size"]
        ), "invalid partial size"
        digest: Sha256 = hash_prefix(output, offset)
        assert sha256_digest(digest) == json_string(state["prefix"]), "committed prefix changed"
        file_truncate(output, offset)
        file_sync(output)
        return digest


def publish(state: Json, names: tuple[str, str, str]) -> Json:
    size: int = json_int(state["file"]["size"])
    digest: str = json_string(state["file"]["sha256"])
    assert json_int(state["offset"]) == size and json_string(state["prefix"]) == digest, "transfer is incomplete"
    if json_string(state["phase"]) == "published":
        verify(names[0], size, digest)
        assert not path_exists(names[1]), "unexpected partial after publication"
        return state
    if json_string(state["phase"]) == "receiving":
        verify(names[1], size, digest)
        state["phase"] = "ready"
        save(state, names)
    fault("before_publish")
    if path_exists(names[0]):
        verify(names[0], size, digest)
        if path_exists(names[1]):
            assert path_same(names[0], names[1]), "destination belongs to another file"
    else:
        verify(names[1], size, digest)
        link_file(names[1], names[0])
        sync_directory(path_parent(names[0]))
    fault("after_publish")
    if path_exists(names[1]):
        remove_file(names[1])
        sync_directory(path_parent(names[1]))
    fault("after_cleanup")
    state["phase"] = "published"
    save(state, names)
    return state
