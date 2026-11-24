"""Validated configuration, owned output prefixes and atomic checkpoint documents."""

from py2rust.stdlib import (
    FileHandle,
    Json,
    Sha256,
    env_get,
    file_open,
    file_read,
    file_seek,
    file_size,
    file_sync,
    file_truncate,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    mkdir_new,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    pretty,
    random_token,
    remove_dir,
    remove_file,
    rename_no_replace,
    sha256_digest,
    sha256_new,
    sha256_update,
    sleep,
    sync_directory,
    write_text_atomic,
)


def names() -> list[str]:
    return ["accepted.jsonl", "quarantine.bin", "rejected.jsonl"]


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def digest(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_canonical(value).encode()))


def identity(path: str, kind: str) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == kind, "unexpected filesystem entry"
    assert kind != "file" or json_int(info["links"]) == 1, "output must not have hard links"
    return {"device": info["device"], "inode": info["inode"]}


def signature(path: str) -> Json:
    info: Json = path_stat(path, False)
    assert json_string(info["kind"]) == "file", "input must be a regular file"
    del info["atime_ns"]
    return info


def document(path: str) -> Json:
    signature(path)
    data: bytes = b""
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 65536, "control document exceeds 64 KiB"
        data = file_read(handle, 65537)
        assert len(data) <= 65536, "control document grew beyond 64 KiB"
    return json_loads(data.decode())


def configuration() -> Json:
    path: str = absolute(env_get("JSONL_CONFIG", "transform.json"), path_resolve("."))
    before: Json = signature(path)
    config: Json = document(path)
    assert json_keys(config) == sorted(
        ["input", "output", "select", "where", "chunk_bytes", "max_line_bytes", "batch_rows", "batch_bytes"]
    ), "invalid configuration fields"
    for field in ["chunk_bytes", "max_line_bytes", "batch_rows", "batch_bytes"]:
        maximum: int = 65536 if field == "chunk_bytes" else 1048576
        maximum = 1000 if field == "batch_rows" else maximum
        maximum = 16777216 if field == "batch_bytes" else maximum
        assert 1 <= json_int(config[field]) <= maximum, "invalid batch/line bound"
    selected: list[str] = []
    for item in json_array(config["select"]):
        name: str = json_string(item)
        assert name != "" and len(name.encode()) <= 256 and name not in selected, "invalid selected field"
        selected.append(name)
    assert 1 <= len(selected) <= 64 and len(json_keys(config["where"])) <= 64, "too many or missing fields"
    for field in ["input", "output"]:
        config[field] = absolute(json_string(config[field]), path_parent(path))
    root: str = json_string(config["output"])
    for source in [path, json_string(config["input"])]:
        assert source != root and not source.startswith(root + "/"), "inputs must be outside output directory"
    assert json_equal(before, signature(path)), "configuration changed while reading"
    config["_hash"] = digest(config)
    config["_path"] = path
    config["_stamp"] = before
    return config


def fault(label: str, step: int) -> None:
    token: str = label + ":" + str(step)
    assert env_get("JSONL_FAIL", "") != token, "injected failure: " + token
    if env_get("JSONL_PAUSE", "") == token:
        print("PAUSED " + token)
        signal: str = env_get("JSONL_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return


def save(root: str, state: Json) -> None:
    write_text_atomic(path_join(root, "checkpoint.json"), pretty({"checksum": digest(state), "state": state}))


def initialize(config: Json) -> Json:
    root: str = json_string(config["output"])
    staging: str = path_join(path_parent(root), ".jsonl-init-" + random_token())
    mkdir_new(staging)
    try:
        fault("stage", 0)
        outputs: Json = {}
        for name in names():
            path: str = path_join(staging, name)
            with file_open(path, "x+b") as handle:
                file_sync(handle)
            outputs[name] = {"size": 0, "sha256": sha256_digest(sha256_new()), "identity": identity(path, "file")}
        state: Json = {
            "version": 1,
            "config": config["_hash"],
            "root": identity(staging, "directory"),
            "input": signature(json_string(config["input"])),
            "phase": "running",
            "offset": 0,
            "lines": 0,
            "accepted": 0,
            "filtered": 0,
            "rejected": 0,
            "batches": 0,
            "source_sha256": sha256_digest(sha256_new()),
            "outputs": outputs,
        }
        save(staging, state)
        sync_directory(staging)
        fault("initialized", 0)
        rename_no_replace(staging, root)
        sync_directory(path_parent(root))
        fault("published", 0)
        return state
    except Exception:
        if present(staging):
            cleanup_names: list[str] = names()
            cleanup_names.append("checkpoint.json")
            for name in cleanup_names:
                if present(path_join(staging, name)):
                    remove_file(path_join(staging, name))
            remove_dir(staging)
        raise


def guard(config: Json, state: Json) -> None:
    assert json_equal(signature(json_string(config["_path"])), config["_stamp"]), "configuration changed"
    assert json_equal(signature(json_string(config["input"])), state["input"]), "source changed"
    root: str = json_string(config["output"])
    assert json_equal(identity(root, "directory"), state["root"]), "output directory changed"
    for name in names():
        assert json_equal(
            identity(path_join(root, name), "file"), state["outputs"][name]["identity"]
        ), "output file changed"


def load(config: Json) -> Json:
    root: str = json_string(config["output"])
    identity(root, "directory")
    envelope: Json = document(path_join(root, "checkpoint.json"))
    assert json_keys(envelope) == ["checksum", "state"], "invalid checkpoint fields"
    state: Json = envelope["state"]
    assert digest(state) == json_string(envelope["checksum"]), "checkpoint checksum mismatch"
    assert json_keys(state) == sorted(
        [
            "version",
            "config",
            "root",
            "input",
            "phase",
            "offset",
            "lines",
            "accepted",
            "filtered",
            "rejected",
            "batches",
            "source_sha256",
            "outputs",
        ]
    ), "invalid state fields"
    assert json_int(state["version"]) == 1 and json_equal(
        state["config"], config["_hash"]
    ), "configuration differs from checkpoint"
    assert json_string(state["phase"]) in ["running", "paused", "complete"], "invalid checkpoint phase"
    for key in ["offset", "lines", "accepted", "filtered", "rejected", "batches"]:
        assert json_int(state[key]) >= 0, "negative checkpoint counter"
    assert json_int(state["lines"]) == json_int(state["accepted"]) + json_int(state["filtered"]) + json_int(
        state["rejected"]
    ), "checkpoint counts differ"
    assert 0 <= json_int(state["offset"]) <= json_int(state["input"]["size"]), "invalid input offset"
    assert json_string(state["phase"]) != "complete" or json_equal(
        state["offset"], state["input"]["size"]
    ), "incomplete completion marker"
    assert json_keys(state["outputs"]) == names(), "invalid output names"
    guard(config, state)
    return state


def prefix(handle: FileHandle, size: int, expected: str) -> Sha256:
    assert 0 <= size <= file_size(handle), "committed file prefix is missing"
    file_seek(handle, 0, 0)
    left: int = size
    hashed: Sha256 = sha256_new()
    while left > 0:
        chunk: bytes = file_read(handle, min(left, 65536))
        assert len(chunk) > 0, "short committed prefix"
        hashed = sha256_update(hashed, chunk)
        left = left - len(chunk)
    assert sha256_digest(hashed) == expected, "committed file prefix changed"
    return hashed


def restore(config: Json, state: Json, outputs: list[FileHandle]) -> list[Sha256]:
    hashes: list[Sha256] = []
    with file_open(json_string(config["input"]), "rb") as source:
        hashes.append(prefix(source, json_int(state["offset"]), json_string(state["source_sha256"])))
    paths: list[str] = names()
    for index in range(3):
        entry: Json = state["outputs"][paths[index]]
        assert json_keys(entry) == ["identity", "sha256", "size"], "invalid output checkpoint"
        size: int = json_int(entry["size"])
        hashes.append(prefix(outputs[index], size, json_string(entry["sha256"])))
        assert (
            json_string(state["phase"]) != "complete" or file_size(outputs[index]) == size
        ), "completed output has an unexpected tail"
    guard(config, state)
    # Validate every prefix before changing any file; only uncommitted tails go.
    for index in range(3):
        size: int = json_int(state["outputs"][paths[index]]["size"])
        if file_size(outputs[index]) != size:
            file_truncate(outputs[index], size)
            file_sync(outputs[index])
        file_seek(outputs[index], size, 0)
    return hashes
