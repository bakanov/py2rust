"""Small, explicit bounds and filesystem invariants shared by each command."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_size,
    file_sync,
    file_write,
    json_dumps,
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
    path_stat,
    regex_fullmatch,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    del value["atime_ns"]
    return value


def fields(value: Json, expected: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(expected), "invalid fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def document(path: str) -> Json:
    assert json_string(path_stat(path, False)["kind"]) == "file", "document must be regular"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 8388608, "document exceeds 8 MiB"
        data: bytes = file_read(handle, 8388609)
        assert len(data) <= 8388608, "document grew beyond 8 MiB"
        return json_loads(data.decode())


def write_document(path: str, value: Json) -> None:
    data: bytes = json_dumps(value).encode()
    assert len(data) <= 8388608, "document exceeds 8 MiB"
    with file_open(path, "x+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def checksum(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_dumps(value).encode()))


def version_name(value: str) -> str:
    assert regex_fullmatch("[A-Za-z0-9_-]{1,64}", value), "invalid version name"
    return value


def relative(value: str) -> None:
    assert len(value.encode()) <= 2048 and "\x00" not in value, "invalid relative path"
    if value != "":
        parts: list[str] = value.split("/")
        assert len(parts) <= 64, "tree exceeds depth 64"
        for part in parts:
            assert part not in ["", ".", ".."], "unsafe path component"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def outside(value: str, root: str) -> str:
    result: str = path_join(path_resolve(path_parent(value)), path_name(value))
    assert result != root and not result.startswith(root + "/"), "path must be outside repository"
    return result


def configuration() -> Json:
    raw: Json = document(env_get("BACKUP_CONFIG", "backup.json"))
    fields(raw, ["repository", "source", "keep", "max_entries", "max_bytes"])
    repo: str = path_resolve(json_string(raw["repository"]))
    assert repo != "/" and json_string(path_stat(repo, False)["kind"]) == "directory", "invalid repository"
    for key in ["keep", "max_entries", "max_bytes"]:
        value: int = json_int(raw[key])
        maximum: int = 10000
        if key == "keep":
            maximum = 1000
        if key == "max_bytes":
            maximum = 1099511627776
        assert value >= 1 and value <= maximum, "invalid limit: " + key
    raw["repository"] = repo
    return raw


def checkpoint(label: str) -> None:
    assert env_get("BACKUP_FAIL", "") != label, "injected interruption: " + label
    if env_get("BACKUP_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("BACKUP_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and path_exists(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def unchanged(path: str, before: Json) -> None:
    assert json_equal(stamp(path), before), "source changed: " + path
    return  # noqa: PLR1711 - explicit return required by repository guidelines
