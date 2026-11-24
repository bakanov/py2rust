"""Strict bounds keep simulation time, heap size and arithmetic predictable."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from documents import Document, absolute, present
from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    regex_fullmatch,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside permitted range"
    return result


def interval(value: Json, low: int, high: int) -> None:
    pair: list[Json] = json_array(value)
    assert len(pair) == 2, "expected lower and upper bound"
    lower: int = integer(pair[0], low, high)
    integer(pair[1], lower, high)
    return


def load(document: Document) -> Json:
    config: Json = json_loads(document.data.decode())
    exact(config, ["version", "workers", "queue_capacity", "workload", "output"])
    assert json_int(config["version"]) == 1, "unsupported version"
    integer(config["workers"], 1, 32)
    integer(config["queue_capacity"], 0, 512)
    output: str = absolute(json_string(config["output"]), path_parent(document.path))
    assert not present(output), "output already exists"
    config["output"] = output
    workload: Json = config["workload"]
    mode: str = json_string(workload["mode"])
    if mode == "explicit":
        exact(workload, ["mode", "jobs"])
        jobs: list[Json] = json_array(workload["jobs"])
        assert len(jobs) <= 512, "at most 512 jobs"
        known: set[str] = set()
        for job in jobs:
            exact(job, ["id", "arrival", "service", "deadline"])
            key: str = json_string(job["id"])
            assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", key) and key not in known, "invalid/duplicate ID"
            known.add(key)
            arrival: int = integer(job["arrival"], 0, 1000000000)
            integer(job["service"], 1, 1000000)
            integer(job["deadline"], arrival, 2000000000)
    else:
        assert mode == "generated", "unknown workload mode"
        exact(workload, ["mode", "seed", "count", "gap", "service", "slack"])
        integer(workload["seed"], 1, 2147483646)
        integer(workload["count"], 0, 512)
        interval(workload["gap"], 0, 1000000)
        interval(workload["service"], 1, 1000000)
        interval(workload["slack"], 0, 1000000)
    return config
