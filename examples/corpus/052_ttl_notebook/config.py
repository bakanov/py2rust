# ruff: noqa: PLR1711 - explicit returns follow repository guidelines
"""Explicit bounds and a replaceable wall clock for reproducible expiration checks."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    json_equal,
    json_float,
    json_int,
    json_loads,
    json_string,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    unix_time,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def absolute(path: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    return path_join(path_resolve(path_parent(path)), path_name(path))


def state_path() -> str:
    return absolute(env_get("TTL_STATE", "ttl-state.json"))


def stamp(path: str) -> Json:
    result: Json = path_stat(path, False)
    assert json_string(result["kind"]) == "file", "expected a regular file"
    del result["atime_ns"]
    return result


def read(path: str, limit: int) -> bytes:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input exceeds byte limit"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            chunk: bytes = file_read(handle, size - len(data))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    return data


def timestamp(value: Json) -> float:
    result: float = json_float(value)
    assert 0.0 <= result <= 253402214400.0, "clock outside supported range"
    return result


def clock() -> float:
    path: str = env_get("TTL_CLOCK", "")
    if path != "":
        return timestamp(json_loads(read(absolute(path), 128).decode()))
    return timestamp(unix_time())


def configure() -> None:
    assert 0 <= setting("TTL_PORT", 8790) <= 65535, "invalid port"
    assert 1 <= setting("TTL_KEYS", 256) <= 256, "invalid key limit"
    assert 2 <= setting("TTL_VALUE_BYTES", 16384) <= 16384, "invalid value limit"
    assert 256 <= setting("TTL_STATE_BYTES", 8388608) <= 16777216, "invalid snapshot limit"
    path: str = env_get("TTL_CLOCK", "")
    if path != "":
        assert absolute(path) not in [state_path(), state_path() + ".lock"], "clock path overlaps state"
    for name in ["TTL_FAULT", "TTL_PAUSE"]:
        assert env_get(name, "") in ["", "before_commit", "after_commit"], "invalid checkpoint hook"
    clock()
    return
