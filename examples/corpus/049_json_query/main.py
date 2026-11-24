"""Query one saved JSON array, preview its pretty result, or atomically publish a new result file."""

import logging

from engine import execute
from parsing import parse

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_sync,
    file_write,
    json_array,
    json_equal,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_stat,
    pretty,
    process_exit,
    random_token,
    remove_file,
    rename_no_replace,
    sync_directory,
)


def absolute(path: str, base: str) -> str:
    assert path != "" and "\x00" not in path, "invalid document path"
    joined: str = path_join(base, path)
    return path_join(path_resolve(path_parent(joined)), path_name(joined))


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    assert json_string(value["kind"]) == "file", "input must be a regular file"
    del value["atime_ns"]
    return value


def read(path: str, limit: int) -> tuple[Json, str]:
    before: Json = stamp(path)
    size: int = json_int(before["size"])
    assert size <= limit, "input byte limit exceeded"
    data: bytes = b""
    with file_open(path, "rb") as handle:
        while len(data) < size:
            chunk: bytes = file_read(handle, size - len(data))
            assert len(chunk) > 0, "input shrank while reading"
            data = data + chunk
    assert json_equal(before, stamp(path)), "input changed while reading"
    return (before, data.decode())


def publish(path: str, content: str) -> None:
    assert not path_exists(path) and not path_is_symlink(path), "output already exists"
    parent: str = path_parent(path)
    temporary: str = path_join(parent, ".json-query-" + random_token())
    with file_open(temporary, "x+b") as handle:
        try:
            file_write(handle, content.encode())
            file_sync(handle)
            assert env_get("QUERY_FAIL", "") != "ready", "injected failure: ready"
            rename_no_replace(temporary, path)
            sync_directory(parent)
        except Exception:
            if path_exists(temporary):
                remove_file(temporary)
            raise
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def run() -> None:
    mode: str = env_get("QUERY_MODE", "preview")
    assert mode in ["preview", "write"], "invalid query mode"
    path: str = absolute(env_get("QUERY_CONFIG", "query-job.json"), path_resolve("."))
    configuration: tuple[Json, str] = read(path, 65536)
    config: Json = json_loads(configuration[1])
    assert json_keys(config) == ["input", "output", "query"], "expected input, output and query configuration"
    source: str = absolute(json_string(config["input"]), path_parent(path))
    output: str = absolute(json_string(config["output"]), path_parent(path))
    query: str = env_get("QUERY_TEXT", json_string(config["query"]))
    stages: list[Json] = parse(query)
    document: tuple[Json, str] = read(source, 4194304)
    rows: list[Json] = json_array(json_loads(document[1]))
    assert len(rows) <= 2000, "dataset exceeds 2000 rows"
    result: str = pretty(execute(rows, stages)) + "\n"
    assert len(result.encode()) <= 16777216, "result exceeds 16 MiB"
    assert json_equal(configuration[0], stamp(path)) and json_equal(document[0], stamp(source)), "input changed"
    if mode == "write":
        publish(output, result)
    print(result[:-1])
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


def main() -> None:
    try:
        run()
    except Exception as error:  # noqa: BLE001 - CLI failures have exit status 2
        logging.error(str(error))  # noqa: LOG015 - supported logging facade
        process_exit(2)
    return  # noqa: PLR1711 - explicit returns follow repository guidelines


if __name__ == "__main__":
    main()
