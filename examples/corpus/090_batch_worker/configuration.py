"""Validate complete input before creating state; bind resumable work to input bytes."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from files import Document, absolute, hashed, inside
from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_loads_unique,
    json_string,
    path_parent,
    regex_fullmatch,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    number: int = json_int(value)
    assert low <= number <= high, "integer outside permitted range"
    return number


def load(document: Document) -> Json:
    config: Json = json_loads_unique(document.data.decode())
    exact(config, ["version", "input", "output", "batch_size"])
    assert json_int(config["version"]) == 1, "unsupported version"
    integer(config["batch_size"], 1, 64)
    for name in ["input", "output"]:
        config[name] = absolute(json_string(config[name]), path_parent(document.path))
    source: str = json_string(config["input"])
    output: str = json_string(config["output"])
    assert source != document.path, "configuration and input overlap"
    for path in [source, document.path]:
        assert not inside(path, output) and path != output + ".lock", "controls overlap input"
    return config


def jobs(document: Document) -> list[Json]:
    lines: list[str] = document.data.decode().split("\n")
    if lines[-1] == "":
        lines.pop()
    assert len(lines) <= 256, "at most 256 jobs"
    result: list[Json] = []
    known: set[str] = set()
    for line in lines:
        assert len(line.encode()) <= 16384, "job line byte limit exceeded"
        job: Json = json_loads_unique(line)
        exact(job, ["id", "text", "values"])
        name: str = json_string(job["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name) and name not in known, "invalid/duplicate job ID"
        known.add(name)
        assert len(json_string(job["text"]).encode()) <= 2048, "text byte limit exceeded"
        values: list[Json] = json_array(job["values"])
        assert len(values) <= 128, "at most 128 samples per job"
        for value in values:
            integer(value, -1000000000, 1000000000)
        result.append(job)
    return result


def binding(document: Document, count: int) -> Json:
    return {"sha256": hashed(document.data), "input_bytes": len(document.data), "jobs": count, "transform": 1}
