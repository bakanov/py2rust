"""Validate the complete job before starting processes; resolve each executable explicitly."""

# ruff: noqa: PLC0206 - explicit returns and supported subset operations
from dataclasses import dataclass

from documents import Document, absolute, present, read
from quoting import parse

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_int,
    json_keys,
    json_string,
    path_exists,
    path_join,
    path_parent,
    path_resolve,
    path_stat,
    regex_fullmatch,
)


@dataclass
class Job:
    name: str
    command: str
    arguments: list[list[str]]
    environment: dict[str, str]
    data: bytes


@dataclass
class Plan:
    cwd: str
    output: str
    timeout: int
    max_output: int
    pipefail: bool
    jobs: list[Job]


def environment(value: Json, base: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = base.copy()
    for key in json_keys(value):
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", key), "invalid environment name"
        item: str = json_string(value[key])
        assert "\x00" not in item, "invalid environment value"
        result[key] = item
    total: int = 0
    for key in result:
        total = total + len(key.encode()) + len(result[key].encode()) + 2
    assert len(result) <= 256 and total <= 65536, "environment limit exceeded"
    return result


def load(config: Document, value: Json) -> Plan:
    assert json_keys(value) == [
        "cwd",
        "environment",
        "jobs",
        "max_output",
        "output",
        "pipefail",
        "timeout_ms",
        "version",
    ], "invalid shell job fields"
    assert json_int(value["version"]) == 1, "unsupported shell version"
    cwd: str = path_resolve(absolute(json_string(value["cwd"]), path_parent(config.path)))
    assert json_string(path_stat(cwd, True)["kind"]) == "directory", "cwd must be a directory"
    output: str = absolute(json_string(value["output"]), path_parent(config.path))
    assert not present(output), "output already exists"
    timeout: int = json_int(value["timeout_ms"])
    max_output: int = json_int(value["max_output"])
    assert 1 <= timeout <= 60000 and 0 <= max_output <= 16777216, "invalid process limits"
    pipefail: bool = json_bool(value["pipefail"])
    base: dict[str, str] = environment(value["environment"], {})
    rows: list[Json] = json_array(value["jobs"])
    assert 1 <= len(rows) <= 64, "expected 1..64 jobs"
    jobs: list[Job] = []
    names: list[str] = []
    input_total: int = 0
    for row in rows:
        assert json_keys(row) == ["command", "environment", "input", "name"], "invalid pipeline fields"
        name: str = json_string(row["name"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,63}", name), "invalid job name"
        assert name not in names, "duplicate job name"
        names.append(name)
        command: str = json_string(row["command"])
        arguments: list[list[str]] = parse(command)
        variables: dict[str, str] = environment(row["environment"], base)
        data: bytes = b""
        source: str = json_string(row["input"])
        if source != "":
            document: Document = read(absolute(source, path_parent(config.path)), 16777216)
            data = document.data
        input_total = input_total + len(data)
        assert input_total <= 33554432, "total input exceeds 32 MiB"
        jobs.append(Job(name, command, arguments, variables, data))
    return Plan(cwd, output, timeout, max_output, pipefail, jobs)


def executable(name: str, variables: dict[str, str], cwd: str) -> str:
    assert name != "", "empty executable name"
    candidates: list[str] = []
    if "/" in name:
        candidates.append(path_join(cwd, name))
    else:
        assert "PATH" in variables, "PATH must be explicitly configured"
        for directory in variables["PATH"].split(":"):
            assert directory.startswith("/"), "PATH entries must be absolute and nonempty"
            candidates.append(path_join(directory, name))
        assert len(candidates) <= 32, "too many PATH entries"
    for path in candidates:
        if path_exists(path):
            info: Json = path_stat(path, True)
            if json_string(info["kind"]) == "file" and json_int(info["mode"]) & 73 != 0:
                return path_resolve(path)
    assert False, "executable not found: " + name
    return ""


def resolve(job: Job, cwd: str) -> list[list[str]]:
    commands: list[list[str]] = []
    for stage in job.arguments:
        arguments: list[str] = stage.copy()
        arguments[0] = executable(arguments[0], job.environment, cwd)
        commands.append(arguments)
    return commands
