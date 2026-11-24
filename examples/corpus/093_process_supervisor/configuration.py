"""Validate every service and resource bound before creating the session or starting children."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from files import absolute, present, read, regular
from py2rust.stdlib import (
    Json, json_array, json_int, json_keys, json_loads_unique, json_string, path_parent,
    path_resolve, path_stat, regex_fullmatch,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def environment(value: Json) -> dict[str, str]:
    assert len(json_keys(value)) <= 32, "at most 32 environment variables"
    result: dict[str, str] = {}
    size: int = 0
    for key in json_keys(value):
        text: str = json_string(value[key])
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", key) and "\x00" not in text, "invalid environment"
        size = size + len(key.encode()) + len(text.encode()) + 2
        result[key] = text
    assert size <= 16384, "environment exceeds 16 KiB"
    return result


def load(path: str) -> Json:
    stamp: Json = regular(path)
    config: Json = json_loads_unique(read(path, 262144).decode())
    exact(config, ["version", "state", "stop", "run_ms", "grace_ms", "services"])
    assert json_int(config["version"]) == 1, "unsupported version"
    assert 1 <= json_int(config["run_ms"]) <= 60000, "run deadline bounds"
    assert 0 <= json_int(config["grace_ms"]) <= 2000, "shutdown grace bounds"
    base: str = path_parent(path)
    for key in ["state", "stop"]:
        name: str = json_string(config[key])
        assert regex_fullmatch("[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name), "state/stop must be sibling names"
        config[key] = absolute(name, base)
    state: str = json_string(config["state"])
    stop: str = json_string(config["stop"])
    assert path not in [state, state + ".lock", stop] and stop not in [state, state + ".lock"], "control collision"
    if present(stop):
        regular(stop)
    rows: list[Json] = json_array(config["services"])
    assert len(rows) <= 8, "at most eight services"
    names: set[str] = set()
    services: Json = {}
    for row in rows:
        exact(row, ["id", "argv", "cwd", "environment", "restarts", "backoff_ms", "max_backoff_ms", "log_bytes"])
        name: str = json_string(row["id"])
        assert (
            regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name) and name not in names
        ), "invalid/duplicate service ID"
        names.add(name)
        assert 0 <= json_int(row["restarts"]) <= 8 and 0 <= json_int(row["log_bytes"]) <= 65536, "service bounds"
        assert 1 <= json_int(row["backoff_ms"]) <= json_int(row["max_backoff_ms"]) <= 10000, "backoff bounds"
        environment(row["environment"])
        cwd: str = absolute(json_string(row["cwd"]), base)
        assert json_string(path_stat(cwd, True)["kind"]) == "directory", "working directory must exist"
        row["cwd"] = path_resolve(cwd)
        arguments: list[Json] = json_array(row["argv"])
        assert 1 <= len(arguments) <= 64, "argument count"
        argv: list[str] = []
        size: int = 0
        for argument in arguments:
            text: str = json_string(argument)
            assert len(text.encode()) <= 1024 and "\x00" not in text, "argument bounds"
            argv.append(text)
        argv[0] = absolute(argv[0], base)
        for argument in argv:
            size = size + len(argument.encode()) + 1
        assert size <= 65536, "resolved arguments exceed 64 KiB"
        row["argv"] = argv
        services[name] = row
    config["services"] = services
    config["path"] = path
    config["stamp"] = stamp
    return config
