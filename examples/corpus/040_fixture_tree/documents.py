"""Bounded documents, relative names and stable filesystem observations."""

from py2rust.stdlib import (
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_size,
    json_canonical,
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
    path_stat,
    pretty,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    write_text_atomic,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and json_keys(value) == sorted(names), "invalid document fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def absolute(value: str) -> str:
    assert value != "" and "\x00" not in value, "invalid filesystem path"
    return path_join(path_resolve(path_parent(value)), path_name(value))


def relative(value: str) -> str:
    assert value != "" and len(value.encode()) <= 1024 and "\x00" not in value, "invalid relative name"
    parts: list[str] = value.split("/")
    assert len(parts) <= 16, "path exceeds 16 components"
    for part in parts:
        assert part not in ["", ".", ".."] and len(part.encode()) <= 255, "invalid path component"
    return value


def identity(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "directory", "expected a real directory: " + path
    return {"device": value["device"], "inode": value["inode"]}


def document(path: str) -> Json:
    assert json_string(path_stat(path, False)["kind"]) == "file", "document must be regular"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 8388608, "document exceeds 8 MiB"
        data: bytes = b""
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= 8388608, "document grew beyond 8 MiB"
        return json_loads(data.decode())


def observe(path: str, kind: str) -> Json:
    if kind == "directory":
        return identity(path)
    before: Json = path_stat(path, False)
    assert json_string(before["kind"]) == "file", "expected a regular file: " + path
    state: Sha256 = sha256_new()
    total: int = 0
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 1048576, "fixture exceeds 1 MiB"
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            total = total + len(chunk)
            assert total <= 1048576, "fixture grew beyond 1 MiB"
            state = sha256_update(state, chunk)
    after: Json = path_stat(path, False)
    del before["atime_ns"]
    del after["atime_ns"]
    assert json_equal(before, after), "fixture changed while reading"
    del after["ctime_ns"]
    after["sha256"] = sha256_digest(state)
    return after


def save(path: str, body: Json) -> None:
    text: str = pretty({"checksum": digest(body), "receipt": body})
    assert len(text.encode()) <= 8388608, "receipt exceeds 8 MiB"
    write_text_atomic(path, text)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def checkpoint(label: str, step: int) -> None:
    token: str = label + ":" + str(step)
    assert env_get("FIXTURE_FAIL", "") != token, "injected failure: " + token
    if env_get("FIXTURE_PAUSE", "") == token:
        print("PAUSED " + token)
        signal: str = env_get("FIXTURE_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
