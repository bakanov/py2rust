"""Validate a bounded single-range HTTP download with a supplied SHA-256 digest."""

from py2rust.stdlib import (
    HttpReader,
    Json,
    env_get,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    read_text,
    regex_fullmatch,
)


def setting(name: str, default: int) -> int:
    return json_int(json_loads(env_get(name, str(default))))


def decimal(value: str) -> int:
    assert regex_fullmatch("0|[1-9][0-9]{0,9}", value), "invalid byte count"
    return json_int(json_loads(value))


def strong_etag(value: str) -> bool:
    return len(value) <= 256 and regex_fullmatch('"[\\x21\\x23-\\x7e]*"', value)


def normalize_url(value: str) -> str:
    assert len(value) <= 2048, "URL exceeds 2048 characters"
    assert regex_fullmatch(
        "https?://[A-Za-z0-9.-]+(:[1-9][0-9]{0,4})?/[A-Za-z0-9._~!$&'()*+,;=:@/?%-]*", value
    ), "invalid URL"
    scheme: str = value.split(":")[0]
    authority: str = value.split("/")[2].lower()
    host: str = authority.split(":")[0]
    assert len(host) <= 253, "hostname too long"
    for label in host.split("."):
        assert len(label) <= 63 and regex_fullmatch("[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?", label), "invalid hostname"
    if regex_fullmatch("[0-9.]+", host):
        assert len(host.split(".")) == 4, "IPv4 needs four octets"
        for octet in host.split("."):
            assert regex_fullmatch("0|[1-9][0-9]{0,2}", octet) and decimal(octet) <= 255, "invalid IPv4 octet"
    if ":" in authority:
        port: int = decimal(authority.split(":")[1])
        assert port <= 65535, "invalid port"
        if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
            authority = host
    pieces: list[str] = value.split("%")
    for index in range(1, len(pieces)):
        assert len(pieces[index]) >= 2 and regex_fullmatch(
            "[0-9A-Fa-f]{2}", pieces[index][:2]
        ), "invalid percent escape"
    return scheme + "://" + authority + value[len(scheme) + 3 + len(value.split("/")[2]) :]


def configuration() -> Json:
    text: str = read_text(env_get("DOWNLOAD_CONFIG", "download.json"))
    assert len(text.encode()) <= 65536, "configuration exceeds 64 KiB"
    value: Json = json_loads(text)
    for key in json_keys(value):
        assert key in ["url", "target", "sha256", "max_bytes", "chunk_size", "timeout_ms"], "unknown setting"
    path: str = json_string(value["target"])
    assert not path.endswith("/"), "target requires a file name"
    target: str = path_join(path_resolve(path_parent(path)), path_name(path))
    digest: str = json_string(value["sha256"]).lower()
    assert regex_fullmatch("[0-9a-f]{64}", digest), "expected a SHA-256 digest"
    maximum: int = json_int(json_get(value, "max_bytes", 1073741824))
    chunk: int = json_int(json_get(value, "chunk_size", 1048576))
    timeout: int = json_int(json_get(value, "timeout_ms", 5000))
    assert maximum >= 0 and maximum <= 1073741824, "file limit must be 0..1 GiB"
    assert chunk >= 1 and chunk <= 16777216, "range size must be 1..16 MiB"
    assert timeout >= 1 and timeout <= 60000, "invalid timeout"
    return {
        "url": normalize_url(json_string(value["url"])),
        "target": target,
        "sha256": digest,
        "max_bytes": maximum,
        "chunk_size": chunk,
        "timeout_ms": timeout,
    }


def response_range(response: HttpReader, state: Json, requested_end: int) -> tuple[int, int, str]:
    etag: str = response.headers.get("etag", "")
    assert strong_etag(etag), "a strong ETag is required"
    previous: str = json_string(state["etag"])
    assert previous == "" or previous == etag, "remote ETag changed"
    assert response.headers.get("content-encoding", "identity").lower() == "identity", "encoded representation rejected"
    header: str = response.headers.get("content-range", "")
    offset: int = json_int(state["offset"])
    if response.status == 416 and header == "bytes */0" and offset == 0 and json_int(state["total"]) == -1:
        return (0, 0, etag)
    assert response.status == 206, "expected a partial response; server may have changed or ignored Range"
    assert regex_fullmatch("bytes [0-9]+-[0-9]+/[0-9]+", header), "invalid Content-Range"
    interval: str = header.split(" ")[1].split("/")[0]
    start: int = decimal(interval.split("-")[0])
    end: int = decimal(interval.split("-")[1])
    total: int = decimal(header.split("/")[1])
    assert start == offset and end >= start and end <= requested_end and end < total, "unexpected byte range"
    assert total <= json_int(state["policy"]["max_bytes"]), "remote file exceeds size limit"
    assert json_int(state["total"]) == -1 or json_int(state["total"]) == total, "remote length changed"
    expected: int = end - start + 1
    length: str = response.headers.get("content-length", "")
    assert length == "" or decimal(length) == expected, "Content-Length disagrees with range"
    return (total, expected, etag)
