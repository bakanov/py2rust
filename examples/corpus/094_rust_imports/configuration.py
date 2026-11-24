"""Validate every case before calling native code or publishing any results."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from documents import Document, absolute, present
from py2rust.stdlib import (
    Json,
    base64_decode,
    base64_encode,
    json_array,
    json_bool,
    json_canonical,
    json_int,
    json_kind,
    json_is_null,
    json_keys,
    json_loads_unique,
    json_string,
    path_parent,
    regex_fullmatch,
)


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def bounded(value: Json) -> None:
    assert len(json_canonical(value).encode()) <= 4096, "JSON value exceeds 4096 bytes"
    pending: list[tuple[Json, int]] = [(value, 0)]
    nodes: int = 0
    while len(pending) > 0:
        entry: tuple[Json, int] = pending.pop()
        item: Json = entry[0]
        depth: int = entry[1]
        nodes = nodes + 1
        assert depth <= 8 and nodes <= 256, "JSON structural limit exceeded"
        if json_kind(item) == "array":
            for child in json_array(item):
                pending.append((child, depth + 1))
        elif json_kind(item) == "object":
            for name in json_keys(item):
                pending.append((item[name], depth + 1))
    return


def expectation(value: Json) -> None:
    if json_is_null(value):
        return
    kind: str = json_string(value["kind"])
    if kind == "value":
        exact(value, ["kind", "value"])
        bounded(value["value"])
    else:
        exact(value, ["kind", "code"])
        assert kind == "error", "invalid expectation kind"
        assert json_string(value["code"]) in [
            "integer_range",
            "overflow",
            "nonfinite",
            "json_range",
            "rejected",
        ], "error code"
    return


def arguments(operation: str, args: Json) -> None:
    if operation in ["narrow", "unsigned", "double"]:
        exact(args, ["value"])
        json_int(args["value"])
    elif operation == "add":
        exact(args, ["left", "right"])
        json_int(args["left"])
        json_int(args["right"])
    elif operation == "invert":
        exact(args, ["value"])
        json_bool(args["value"])
    elif operation in ["unicode", "accept", "unit"]:
        exact(args, ["text"])
        assert len(json_string(args["text"]).encode()) <= 1024, "text exceeds 1024 bytes"
    elif operation == "bytes":
        exact(args, ["data"])
        text: str = json_string(args["data"])
        data: bytes = base64_decode(text)
        assert len(data) <= 1024 and base64_encode(data) == text, "expected canonical base64 of at most 1024 bytes"
    elif operation in ["float", "nested", "json"]:
        exact(args, ["mode"])
        modes: list[str] = ["finite", "wide"] if operation == "json" else ["finite", "nan", "inf", "negative_inf"]
        assert json_string(args["mode"]) in modes, "invalid return mode"
    else:
        assert operation == "roundtrip", "unknown native operation"
        exact(args, ["value"])
        bounded(args["value"])
    return


def load(document: Document) -> Json:
    config: Json = json_loads_unique(document.data.decode())
    exact(config, ["version", "output", "cases"])
    assert json_int(config["version"]) == 1, "unsupported version"
    output: str = absolute(json_string(config["output"]), path_parent(document.path))
    assert not present(output), "output already exists"
    cases: list[Json] = json_array(config["cases"])
    assert len(cases) <= 64, "at most 64 cases"
    known: set[str] = set()
    argument_bytes: int = 0
    for case in cases:
        exact(case, ["id", "operation", "arguments", "expect"])
        name: str = json_string(case["id"])
        assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name) and name not in known, "invalid/duplicate case ID"
        known.add(name)
        arguments(json_string(case["operation"]), case["arguments"])
        expectation(case["expect"])
        argument_bytes = argument_bytes + len(json_canonical(case["arguments"]).encode())
    assert argument_bytes <= 98304, "aggregate arguments exceed 96 KiB replay budget"
    config["output"] = output
    return config
