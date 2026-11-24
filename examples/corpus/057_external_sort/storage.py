"""Configuration, protected paths, an owned workspace and conservative restart cleanup."""

# ruff: noqa: PLR1711 - explicit returns

from model import Job

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_sync,
    file_write,
    json_array,
    json_canonical,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    list_dir,
    mkdir_new,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    read_bytes,
    regex_fullmatch,
    remove_dir,
    remove_file,
    sleep,
    sync_directory,
)


def present(path: str) -> bool:
    return path_exists(path) or path_is_symlink(path)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid path"
    value: str = path_join(base, path)
    return path_join(path_resolve(path_parent(value)), path_name(value))


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file", "expected a regular file"
    del value["atime_ns"]
    return value


def number(value: Json, minimum: int, maximum: int) -> int:
    result: int = json_int(value)
    assert minimum <= result <= maximum, "integer outside configured bounds"
    return result


def configuration() -> Job:
    path: str = absolute(env_get("SORT_CONFIG", "sort-job.json"), path_resolve("."))
    before: Json = stamp(path)
    assert json_int(before["size"]) <= 65536, "configuration exceeds 64 KiB"
    raw: bytes = read_bytes(path)
    assert json_equal(before, stamp(path)), "configuration changed while reading"
    value: Json = json_loads(raw.decode())
    assert json_keys(value) == sorted(
        [
            "inputs",
            "field",
            "kind",
            "chunk_bytes",
            "record_bytes",
            "fan_in",
            "max_rows",
            "memory_mib",
            "output",
            "workspace",
        ]
    ), "unexpected configuration fields"
    inputs: list[str] = []
    base: str = path_parent(path)
    for item in json_array(value["inputs"]):
        inputs.append(absolute(json_string(item), base))
    assert 1 <= len(inputs) <= 16, "expected 1..16 input files"
    field: str = json_string(value["field"])
    assert 1 <= len(field) <= 128 and len(field.encode()) <= 512, "invalid sort field"
    kind: str = json_string(value["kind"])
    assert kind in ["integer", "string"], "invalid sort key kind"
    chunk: int = number(value["chunk_bytes"], 4096, 4194304)
    record: int = number(value["record_bytes"], 256, min(chunk, 65536))
    output: str = absolute(json_string(value["output"]), base)
    workspace: str = absolute(json_string(value["workspace"]), base)
    for protected in inputs + [path, output]:
        assert protected != workspace and not protected.startswith(
            workspace + "/"
        ), "workspace overlaps a protected path"
    return Job(
        inputs,
        field,
        kind,
        chunk,
        record,
        number(value["fan_in"], 2, 8),
        number(value["max_rows"], 1, 1000000),
        number(value["memory_mib"], 128, 1024) * 1048576,
        output,
        workspace,
        path,
        before,
    )


def initialize(job: Job) -> None:
    marker: str = path_join(job.workspace, "owner.json")
    expected: bytes = (
        json_canonical(
            {"format": "external-sort-v1", "workspace": job.workspace, "output": job.output, "config": job.config_path}
        )
        + "\n"
    ).encode()
    observed: bytes = b""
    if present(marker):
        metadata: Json = stamp(marker)
        assert json_int(metadata["size"]) <= 65536 and json_int(metadata["links"]) == 1, "invalid workspace owner"
        observed = read_bytes(marker)
        if observed == expected:
            return
    assert expected.startswith(observed), "workspace belongs to another job"
    for name in list_dir(job.workspace):
        assert name in ["owner.json", ".lock"], "unowned workspace is not empty"
    with file_open(marker, "w+b") as handle:
        file_write(handle, expected)
        file_sync(handle)
    sync_directory(job.workspace)
    return


def cleanup(job: Job) -> int:
    files: list[str] = []
    bundle: str = path_join(job.workspace, "bundle")
    for name in list_dir(job.workspace):
        path: str = path_join(job.workspace, name)
        if name == "bundle":
            assert json_string(path_stat(path, False)["kind"]) == "directory", "invalid bundle directory"
            for child in list_dir(path):
                assert child in ["sorted.jsonl", "report.json"], "unknown bundle file"
                stamp(path_join(path, child))
                files.append(path_join(path, child))
        else:
            stamp(path)
            assert name in [".lock", "owner.json"] or regex_fullmatch(
                "run-[0-9]+\\.jsonl", name
            ), "unknown workspace file"
            if name not in [".lock", "owner.json"]:
                files.append(path)
    for path in files:
        remove_file(path)
    if present(bundle):
        remove_dir(bundle)
    sync_directory(job.workspace)
    return len(files)


def prepare(job: Job) -> None:
    if not present(job.workspace):
        mkdir_new(job.workspace)
    assert json_string(path_stat(job.workspace, False)["kind"]) == "directory", "workspace must be a directory"
    if not present(path_join(job.workspace, "owner.json")):
        for name in list_dir(job.workspace):
            assert name == ".lock", "unowned workspace is not empty"
    return


def checkpoint(label: str) -> None:
    assert env_get("SORT_FAIL", "") != label, "injected failure: " + label
    if env_get("SORT_PAUSE", "") == label:
        print("PAUSED " + label)
        signal: str = env_get("SORT_CONTINUE", "")
        for attempt in range(3000):
            if signal != "" and present(signal):
                return
            sleep(0.01)
        assert False, "pause timed out"
    return
