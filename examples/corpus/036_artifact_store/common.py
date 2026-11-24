"""Validation, bounded documents and explicit interruption boundaries."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_size,
    file_sync,
    file_write,
    json_canonical,
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


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(names), "invalid fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def identifier(value: str) -> str:
    assert regex_fullmatch("[0-9a-f]{64}", value), "invalid SHA-256 identifier"
    return value


def name(value: str) -> str:
    assert regex_fullmatch("[A-Za-z0-9_-]{1,64}", value), "invalid reference name"
    return value


def stamp(path: str) -> Json:
    info: Json = path_stat(path, False)
    del info["atime_ns"]
    return info


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def outside(path: str, repo: str) -> str:
    result: str = path_join(path_resolve(path_parent(path)), path_name(path))
    assert result != repo and not result.startswith(repo + "/"), "path must be outside repository"
    return result


def document(path: str) -> Json:
    assert json_string(stamp(path)["kind"]) == "file", "document must be regular"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 1048576, "document exceeds 1 MiB"
        data: bytes = b""
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= 1048576, "document grew beyond 1 MiB"
        return json_loads(data.decode())


def encode(value: Json) -> bytes:
    data: bytes = json_canonical(value).encode()
    assert len(data) <= 1048576, "document exceeds 1 MiB"
    return data


def write_document(path: str, value: Json) -> None:
    with file_open(path, "x+b") as handle:
        file_write(handle, encode(value))
        file_sync(handle)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def checksum(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), encode(value)))


def configuration() -> Json:
    config: Json = document(env_get("STORE_CONFIG", "store.json"))
    fields(config, ["repository", "max_nodes", "max_bytes", "max_blob_bytes"])
    repo: str = path_resolve(json_string(config["repository"]))
    assert repo != "/" and json_string(stamp(repo)["kind"]) == "directory", "invalid repository"
    config["repository"] = repo
    for key in ["max_nodes", "max_bytes", "max_blob_bytes"]:
        maximum: int = 10000 if key == "max_nodes" else 1099511627776
        assert json_int(config[key]) >= 1 and json_int(config[key]) <= maximum, "invalid limit"
    assert json_int(config["max_blob_bytes"]) <= json_int(config["max_bytes"]), "blob limit exceeds store limit"
    return config


def checkpoint(label: str) -> None:
    assert env_get("STORE_FAIL", "") != label, "injected interruption: " + label
    if env_get("STORE_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("STORE_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and path_exists(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
