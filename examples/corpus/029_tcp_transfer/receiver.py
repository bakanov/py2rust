"""A serial receiver with bounded sessions and a durable acknowledgement after every chunk."""

from storage import fault, paths, prepare, publish, restore, save
from wire import Connection, connection, read_json, receive, send_json

from py2rust.stdlib import (
    Json,
    Sha256,
    env_get,
    file_open,
    file_seek,
    file_size,
    file_sync,
    file_write,
    json_int,
    json_keys,
    json_string,
    mkdir_all,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    sha256_digest,
    sha256_new,
    sha256_update,
    tcp_accept_timeout,
    tcp_listen,
    tcp_port,
)


def receipt(state: Json, policy: dict[str, int]) -> Json:
    return {
        "ok": True,
        "offset": state["offset"],
        "prefix": state["prefix"],
        "complete": json_string(state["phase"]) == "published",
        "chunk_bytes": policy["chunk_bytes"],
    }


def session(wire: Connection, root: str, policy: dict[str, int]) -> None:
    state: Json = prepare(root, read_json(wire), policy)
    names: tuple[str, str, str] = paths(root, json_string(state["file"]["name"]))
    if json_string(state["phase"]) != "receiving":
        state = publish(state, names)
        send_json(wire, receipt(state, policy))
        return
    digest: Sha256 = restore(state, names)
    send_json(wire, receipt(state, policy))
    while True:
        request: Json = read_json(wire)
        operation: str = json_string(request["op"])
        if operation == "finish":
            assert json_keys(request) == ["op"], "invalid finish fields"
            state = publish(state, names)
            send_json(wire, receipt(state, policy))
            return
        assert operation == "chunk" and json_keys(request) == ["offset", "op", "sha256"], "invalid chunk fields"
        offset: int = json_int(state["offset"])
        assert json_int(request["offset"]) == offset, "chunk offset mismatch"
        data: bytes = receive(wire, policy["chunk_bytes"])
        assert offset + len(data) <= json_int(state["file"]["size"]), "chunk exceeds file size"
        assert sha256_digest(sha256_update(sha256_new(), data)) == json_string(
            request["sha256"]
        ), "chunk digest mismatch"
        with file_open(names[1], "r+b") as output:
            assert file_size(output) == offset, "partial file size changed"
            file_seek(output, offset, 0)
            file_write(output, data)
            file_sync(output)
        fault("after_write")
        digest = sha256_update(digest, data)
        state["offset"] = offset + len(data)
        state["prefix"] = sha256_digest(digest)
        save(state, names)
        fault("after_checkpoint")
        send_json(wire, receipt(state, policy))
    return


def serve(policy: dict[str, int]) -> None:
    root: str = env_get("XFER_ROOT", "received")
    mkdir_all(root)
    root = path_resolve(root)
    stage: str = path_join(root, ".incoming")
    assert not path_is_symlink(stage), "staging directory is a symlink"
    mkdir_all(stage)
    for value in [env_get("XFER_CONFIG", "transfer.json"), env_get("XFER_STOP", "")]:
        if value != "":
            absolute: str = path_join(path_resolve(path_parent(value)), path_name(value))
            assert not absolute.startswith(root + "/"), "control files must be outside received files"
    with tcp_listen("127.0.0.1", policy["port"]) as listener:
        print("LISTENING tcp://127.0.0.1:" + str(tcp_port(listener)))
        while True:
            marker: str = env_get("XFER_STOP", "")
            if marker != "" and path_exists(marker):
                break
            try:
                with tcp_accept_timeout(listener, 100, policy["io_ms"]) as stream:
                    wire: Connection = connection(stream, policy)
                    try:
                        session(wire, root, policy)
                    except Exception as error:  # noqa: BLE001 - reject one connection without losing checkpoints
                        send_json(wire, {"ok": False, "error": str(error)[:256]})
            except Exception:  # noqa: BLE001, S112 - accept timeouts and disconnected replies are routine
                continue
    return  # noqa: PLR1711 - explicit return required by repository guidelines
