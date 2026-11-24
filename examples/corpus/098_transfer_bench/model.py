"""Bounded workloads, reproducible fixture bytes and direct worker commands."""
# ruff: noqa: I001, PLR1711 - compact imports and explicit returns
from documents import absolute
from py2rust.stdlib import (
    Json, json_array, json_int, json_keys, json_string, path_resolve, path_stat, regex_fullmatch,
    sha256_digest, sha256_new, sha256_update,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    result: int = json_int(value)
    assert low <= result <= high, "integer outside permitted range"
    return result


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def payload(size: int, seed: int) -> bytes:
    block: bytearray = bytearray()
    for index in range(256):
        block.append((index * 31 + seed) % 256)
    data: bytes = bytes(block)
    while len(data) < size:
        data = data + data
    return data[:size]


def workload(value: Json) -> None:
    exact(value, ["id", "size", "seed", "send_chunk", "receive_chunk", "timeout_ms"])
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", json_string(value["id"])), "invalid case ID"
    integer(value["size"], 0, 1048576)
    integer(value["seed"], 0, 255)
    integer(value["send_chunk"], 1, 65536)
    integer(value["receive_chunk"], 1, 65536)
    integer(value["timeout_ms"], 1, 15000)
    return


def suite(cases: list[Json], repetitions: int) -> None:
    assert 1 <= len(cases) <= 16 and 1 <= repetitions <= 4, "invalid suite size"
    names: set[str] = set()
    budget: int = 0
    for case in cases:
        workload(case)
        name: str = json_string(case["id"])
        assert name not in names, "duplicate case ID"
        names.add(name)
        budget = budget + json_int(case["timeout_ms"]) * repetitions
    assert budget <= 120000, "suite deadline budget exceeded"
    return


def command(value: Json, base: str) -> Json:
    exact(value, ["argv", "environment", "cwd"])
    argv: list[Json] = json_array(value["argv"])
    assert 1 <= len(argv) <= 32, "expected one to 32 arguments"
    arguments: list[str] = []
    total: int = 0
    for item in argv:
        text: str = json_string(item)
        assert "\x00" not in text, "NUL in argument"
        text = absolute(text, base) if len(arguments) == 0 else text
        total = total + len(text.encode()) + 1
        arguments.append(text)
    assert total <= 8192, "argument byte budget exceeded"
    directory: str = path_resolve(absolute(json_string(value["cwd"]), base))
    assert json_string(path_stat(directory, False)["kind"]) == "directory", "invalid worker directory"
    variables: Json = value["environment"]
    assert len(json_keys(variables)) <= 32, "environment entry limit"
    total = 0
    for name in json_keys(variables):
        text: str = json_string(variables[name])
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_]{0,63}", name), "invalid environment name"
        assert not name.startswith("TRANSFER_") and name != "PYTHONUNBUFFERED", "reserved worker environment name"
        assert "\x00" not in text, "NUL in environment"
        total = total + len(name.encode()) + len(text.encode()) + 2
    assert total <= 8192, "environment byte budget exceeded"
    return {"argv": arguments, "environment": variables, "cwd": directory}
