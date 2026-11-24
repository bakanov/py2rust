"""Explicit limits, bounded basenames and incremental file checksums."""

from py2rust.stdlib import (
    FileHandle,
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_seek,
    file_size,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    read_text,
    regex_fullmatch,
    regex_search,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def configuration() -> dict[str, int]:
    text: str = read_text(env_get("XFER_CONFIG", "transfer.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(text)
    bounds: dict[str, tuple[int, int, int]] = {
        "max_bytes": (134217728, 0, 1073741824),
        "max_files": (128, 1, 1024),
        "chunk_bytes": (65536, 1, 65536),
        "io_ms": (3000, 50, 30000),
        "session_ms": (30000, 100, 300000),
        "attempts": (3, 1, 10),
        "pause_ms": (100, 0, 5000),
    }
    for key in json_keys(raw):
        assert key in bounds, "unknown setting"
    policy: dict[str, int] = {}
    for key in bounds:  # noqa: PLC0206 - supported dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid setting: " + key
        policy[key] = value
    policy["port"] = json_int(json_loads(env_get("XFER_PORT", "8793")))
    assert policy["port"] >= 0 and policy["port"] <= 65535, "invalid port"
    return policy


def manifest(value: Json, policy: dict[str, int]) -> Json:
    assert (
        json_keys(value) == ["name", "sha256", "size", "version"] and json_int(value["version"]) == 1
    ), "invalid manifest"
    name: str = json_string(value["name"])
    assert len(name.encode()) > 0 and len(name.encode()) <= 240 and not name.startswith("."), "invalid filename"
    assert not regex_search("[\\x00-\\x1f\\x7f\\\\/]", name), "invalid filename characters"
    size: int = json_int(value["size"])
    assert size >= 0 and size <= policy["max_bytes"], "file exceeds byte limit"
    assert regex_fullmatch("[0-9a-f]{64}", json_string(value["sha256"])), "invalid digest"
    return value


def hash_prefix(handle: FileHandle, size: int) -> Sha256:
    file_seek(handle, 0, 0)
    digest: Sha256 = sha256_new()
    remaining: int = size
    while remaining > 0:
        data: bytes = file_read(handle, min(65536, remaining))
        assert len(data) > 0, "file shorter than expected"
        digest = sha256_update(digest, data)
        remaining = remaining - len(data)
    return digest


def verify(path: str, size: int, digest: str) -> None:
    with file_open(path, "rb") as source:
        assert file_size(source) == size, "file size changed"
        assert sha256_digest(hash_prefix(source, size)) == digest, "file digest mismatch"
    return  # noqa: PLR1711 - explicit return required by repository guidelines
