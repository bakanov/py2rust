"""A bounded retrying client verifies every offered prefix before resuming a source file."""

from model import hash_prefix, manifest
from wire import Connection, connection, read_json, send_chunk, send_json

from py2rust.stdlib import (
    FileHandle,
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_size,
    json_bool,
    json_int,
    json_keys,
    json_string,
    log,
    path_name,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    tcp_connect,
)


def reply(wire: Connection) -> Json:
    result: Json = read_json(wire)
    if not json_bool(result["ok"]):
        assert False, json_string(result["error"])
    assert json_keys(result) == ["chunk_bytes", "complete", "offset", "ok", "prefix"], "invalid acknowledgement fields"
    assert json_int(result["chunk_bytes"]) > 0 and json_int(result["chunk_bytes"]) <= 65536, "invalid remote chunk size"
    return result


def attempt(wire: Connection, source: FileHandle, wanted: Json, policy: dict[str, int]) -> int:
    send_json(wire, wanted)
    answer: Json = reply(wire)
    offset: int = json_int(answer["offset"])
    size: int = json_int(wanted["size"])
    assert offset >= 0 and offset <= size and file_size(source) == size, "invalid resume offset or source size"
    digest: Sha256 = hash_prefix(source, offset)
    assert sha256_digest(digest) == json_string(answer["prefix"]), "remote prefix differs from source"
    resumed: int = offset
    remote_chunk: int = json_int(answer["chunk_bytes"])
    if json_bool(answer["complete"]):
        assert offset == size and sha256_digest(digest) == json_string(wanted["sha256"]), "invalid completion"
        return resumed
    while offset < size:
        data: bytes = file_read(source, min(min(policy["chunk_bytes"], remote_chunk), size - offset))
        assert len(data) > 0, "source became shorter"
        send_chunk(
            wire, {"op": "chunk", "offset": offset, "sha256": sha256_digest(sha256_update(sha256_new(), data))}, data
        )
        offset = offset + len(data)
        digest = sha256_update(digest, data)
        answer = reply(wire)
        assert json_int(answer["offset"]) == offset and json_string(answer["prefix"]) == sha256_digest(
            digest
        ), "invalid chunk acknowledgement"
        assert (
            not json_bool(answer["complete"]) and json_int(answer["chunk_bytes"]) == remote_chunk
        ), "premature completion or chunk limit changed"
    assert file_size(source) == size and sha256_digest(digest) == json_string(
        wanted["sha256"]
    ), "source changed during transfer"
    send_json(wire, {"op": "finish"})
    answer = reply(wire)
    assert json_bool(answer["complete"]) and json_int(answer["offset"]) == size, "invalid final acknowledgement"
    assert (
        json_string(answer["prefix"]) == json_string(wanted["sha256"])
        and json_int(answer["chunk_bytes"]) == remote_chunk
    ), "invalid final digest or chunk size"
    return resumed


def send(policy: dict[str, int]) -> Json:
    path: str = env_get("XFER_SOURCE", "payload.bin")
    with file_open(path, "rb") as source:
        size: int = file_size(source)
        assert size <= policy["max_bytes"], "source exceeds byte limit"
        wanted: Json = manifest(
            {
                "version": 1,
                "name": env_get("XFER_NAME", path_name(path)),
                "size": size,
                "sha256": sha256_digest(hash_prefix(source, size)),
            },
            policy,
        )
        error: str = ""
        for index in range(policy["attempts"]):
            try:
                with tcp_connect(env_get("XFER_HOST", "127.0.0.1"), policy["port"], policy["io_ms"]) as stream:
                    resumed: int = attempt(connection(stream, policy), source, wanted, policy)
                    return {"file": wanted, "attempts": index + 1, "resumed_from": resumed, "complete": True}
            except Exception as failure:  # noqa: BLE001 - reconnect to the last durable prefix within the retry budget
                error = str(failure)
                log(30, "transfer attempt failed: " + error)
                if index + 1 < policy["attempts"]:
                    sleep(float(policy["pause_ms"]) * 0.001)
        assert False, error
    return {}
