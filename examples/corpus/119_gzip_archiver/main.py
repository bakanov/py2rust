"""Archive, verify or recover rotated logs using a strict JSON request."""

# ruff: noqa: BLE001, PLR1711 - command reports recoverable request and filesystem errors
from archive import execute, preflight
from documents import absolute, load
from validation import integer, keys, limits, pathname

from py2rust.stdlib import (
    Json,
    env_get,
    json_canonical,
    json_string,
    log,
    path_parent,
    process_exit,
)


def main() -> None:
    try:
        config: str = absolute(env_get("GZIP_CONFIG", "gzip-job.json"), ".")
        request: Json = load(config, 65536)
        mode: str = json_string(request["mode"])
        assert mode in ["archive", "verify", "recover"], "unknown operation"
        expected: list[str] = ["version", "mode", "directory", "limits"]
        if mode == "archive":
            expected = expected + ["inputs", "level"]
        keys(request, expected)
        integer(request["version"], 1, 1)
        settings: Json = limits(request["limits"])
        base: str = path_parent(config)
        root: str = absolute(pathname(request["directory"]), base)
        assert path_parent(root) != root, "archive directory cannot be the filesystem root"
        assert config != root and not config.startswith(root + "/"), "request must be outside archive directory"
        inputs: list[Json] = []
        level: int = 6
        if mode == "archive":
            inputs = preflight(request["inputs"], base, root)
            level = integer(request["level"], 0, 9)
        print(json_canonical(execute(root, inputs, base, settings, level, mode)))
    except Exception as error:
        log(40, str(error))
        process_exit(2)
    return


if __name__ == "__main__":
    main()
