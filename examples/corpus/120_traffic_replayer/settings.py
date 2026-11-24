"""Strict job settings and bounded, immutable snapshots of local files."""

# ruff: noqa: PLR1711 - explicit returns
from py2rust.stdlib import (
    Json,
    file_open,
    file_read,
    json_equal,
    json_int,
    json_keys,
    json_loads_unique,
    json_string,
    path_join,
    path_parent,
    path_resolve,
    path_stat,
)


def keys(value: Json, expected: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(expected), "unexpected settings fields"
    return


def integer(value: Json, lower: int, upper: int) -> int:
    result: int = json_int(value)
    assert lower <= result <= upper, "integer outside allowed range"
    return result


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file", "expected regular file without symlink"
    del value["atime_ns"]
    return value


def snapshot(path: str, maximum: int) -> bytes:
    before: Json = stamp(path)
    assert json_int(before["size"]) <= maximum, "file byte limit"
    data: bytearray = bytearray()
    with file_open(path, "rb") as stream:
        chunk: bytes = file_read(stream, 65536)
        while len(chunk) > 0:
            assert len(data) + len(chunk) <= maximum, "file grew beyond limit"
            data.extend(chunk)
            chunk = file_read(stream, 65536)
    assert json_equal(before, stamp(path)), "file changed while reading"
    return bytes(data)


def load(path: str) -> Json:
    job: Json = json_loads_unique(snapshot(path, 65536).decode("utf-8"))
    mode: str = json_string(job["mode"])
    assert mode in ["inspect", "replay"], "unknown operation"
    fields: list[str] = ["version", "mode", "fixture", "limits"]
    if mode == "replay":
        fields = fields + ["peer", "timeouts"]
    keys(job, fields)
    integer(job["version"], 1, 1)
    name: str = json_string(job["fixture"])
    assert 0 < len(name) <= 4096 and "\x00" not in name, "invalid fixture path"
    # Resolve the parent only: snapshot must still reject a final symlink.
    joined: str = path_join(path_parent(path_resolve(path)), name)
    job["fixture"] = joined
    limits: Json = job["limits"]
    keys(limits, ["fixture_bytes", "records", "payload_bytes", "scheduled_ms"])
    integer(limits["fixture_bytes"], 12, 8388608)
    integer(limits["records"], 1, 256)
    integer(limits["payload_bytes"], 0, 1048576)
    integer(limits["scheduled_ms"], 0, 60000)
    if mode == "replay":
        peer: Json = job["peer"]
        keys(peer, ["host", "port"])
        assert json_string(peer["host"]) in ["127.0.0.1", "::1"], "peer must be loopback"
        integer(peer["port"], 1, 65535)
        timeouts: Json = job["timeouts"]
        keys(timeouts, ["connect_ms", "record_ms", "total_ms"])
        integer(timeouts["connect_ms"], 1, 60000)
        integer(timeouts["record_ms"], 1, 60000)
        integer(timeouts["total_ms"], 1, 120000)
    return job
