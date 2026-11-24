"""Validate ownership, polling settings and compatibility of resumed state."""

# ruff: noqa: I001 - compact grouped runtime imports within 120 columns
# ruff: noqa: PLR1711 - explicit subset returns
from files import absolute, identity, inside, read, stamp
from py2rust.stdlib import (
    Json, env_get, json_int, json_keys, json_loads, json_string, path_parent, path_resolve,
)


def exact(value: Json, keys: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(keys), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside bounds"
    return result


def relative(path: str) -> None:
    parts: list[str] = path.split("/")
    assert 1 <= len(path.encode()) <= 1024 and len(parts) <= 16 and "\x00" not in path, "invalid relative path"
    for part in parts:
        assert part not in ["", ".", ".."], "invalid relative path component"
    return


def configuration() -> Json:
    path: str = absolute(env_get("WATCH_CONFIG", "watch-job.json"), path_resolve("."))
    value: Json = json_loads(read(path, 65536).decode())
    exact(value, ["version", "root", "output", "debounce_ms", "retain"])
    assert json_int(value["version"]) == 1, "unsupported version"
    integer(value["debounce_ms"], 0, 60000)
    integer(value["retain"], 1, 256)
    root: str = path_resolve(absolute(json_string(value["root"]), path_parent(path)))
    info: Json = stamp(root)
    assert json_string(info["kind"]) == "directory", "root must be a directory"
    output: str = absolute(json_string(value["output"]), path_parent(path))
    for control in [output, output + ".lock"]:
        assert not inside(control, root) and not inside(root, control), "controls overlap observed tree"
        assert not inside(path, control), "controls overlap configuration"
    value["root"] = root
    value["output"] = output
    value["identity"] = identity(info)
    return value


def binding(config: Json) -> Json:
    return {
        "root": config["root"],
        "identity": config["identity"],
        "debounce_ms": config["debounce_ms"],
        "retain": config["retain"],
    }
