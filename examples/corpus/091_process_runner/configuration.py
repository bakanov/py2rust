"""Validate the whole suite before launching commands, including aggregate resource budgets."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from documents import Document, absolute, present
from py2rust.stdlib import (
    Json,
    base64_decode,
    json_array,
    json_int,
    json_keys,
    json_loads_unique,
    json_string,
    path_parent,
    path_resolve,
    path_stat,
    regex_fullmatch,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def integer(value: Json, low: int, high: int) -> int:
    number: int = json_int(value)
    assert low <= number <= high, "integer outside permitted range"
    return number


def environment(value: Json) -> dict[str, str]:
    result: dict[str, str] = {}
    size: int = 0
    assert len(json_keys(value)) <= 256, "too many environment entries"
    for name in json_keys(value):
        text: str = json_string(value[name])
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", name) and "\x00" not in text, "invalid environment"
        size = size + len(name.encode()) + len(text.encode()) + 2
        result[name] = text
    assert size <= 65536, "environment byte limit exceeded"
    return result


def input_bytes(value: Json) -> bytes:
    exact(value, ["encoding", "data"])
    encoding: str = json_string(value["encoding"])
    text: str = json_string(value["data"])
    assert encoding in ["utf8", "base64"], "invalid stdin encoding"
    data: bytes = text.encode() if encoding == "utf8" else base64_decode(text)
    assert len(data) <= 1048576, "stdin exceeds 1 MiB"
    return data


def expectation(value: Json) -> None:
    exact(value, ["mode", "value"])
    mode: str = json_string(value["mode"])
    text: str = json_string(value["value"])
    assert mode in ["ignore", "utf8", "base64", "contains", "regex"], "invalid output expectation"
    assert len(text.encode()) <= 65536, "expectation byte limit exceeded"
    if mode == "ignore":
        assert text == "", "ignored output must have empty value"
    elif mode == "base64":
        base64_decode(text)
    elif mode == "regex":
        assert len(text.encode()) <= 4096, "regex byte limit exceeded"
        regex_fullmatch(text, "")
    return


def load(document: Document) -> Json:
    config: Json = json_loads_unique(document.data.decode())
    exact(config, ["version", "output", "environment", "tests"])
    assert json_int(config["version"]) == 1, "unsupported version"
    base: str = path_parent(document.path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    config["output"] = output
    defaults: dict[str, str] = environment(config["environment"])
    cases: list[Json] = json_array(config["tests"])
    assert len(cases) <= 32, "at most 32 tests"
    known: set[str] = set()
    time_budget: int = 0
    output_budget: int = 0
    input_budget: int = 0
    for index in range(len(cases)):
        case: Json = cases[index]
        exact(case, ["id", "argv", "cwd", "environment", "stdin", "timeout_ms", "max_output", "expect"])
        name: str = json_string(case["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name) and name not in known, "invalid/duplicate test ID"
        known.add(name)
        argv: list[Json] = json_array(case["argv"])
        assert 1 <= len(argv) <= 128, "argv count outside bounds"
        arguments: list[str] = []
        size: int = 0
        for argument in argv:
            text: str = json_string(argument)
            assert "\x00" not in text, "NUL in argv"
            arguments.append(text)
        arguments[0] = absolute(arguments[0], base)
        for text in arguments:
            size = size + len(text.encode()) + 1
        assert size <= 65536, "argv exceeds 64 KiB"
        directory: str = path_resolve(absolute(json_string(case["cwd"]), base))
        assert len(directory.encode()) <= 4096, "cwd exceeds 4096 bytes"
        assert json_string(path_stat(directory, False)["kind"]) == "directory", "cwd must be a directory"
        merged: dict[str, str] = defaults.copy()
        overrides: dict[str, str] = environment(case["environment"])
        for key in overrides:  # noqa: PLC0206 - typed subset dictionary iteration
            merged[key] = overrides[key]
        merged_json: Json = merged
        environment(merged_json)
        input_budget = input_budget + len(input_bytes(case["stdin"]))
        time_budget = time_budget + integer(case["timeout_ms"], 1, 60000)
        output_budget = output_budget + integer(case["max_output"], 0, 1048576)
        expected: Json = case["expect"]
        exact(expected, ["exit_code", "stdout", "stderr"])
        integer(expected["exit_code"], -64, 255)
        expectation(expected["stdout"])
        expectation(expected["stderr"])
        case["arguments"] = arguments
        case["directory"] = directory
        case["variables"] = merged
        cases[index] = case
    assert time_budget <= 120000 and output_budget <= 8388608 and input_budget <= 1048576, "suite budget exceeded"
    config["tests"] = cases
    return config
