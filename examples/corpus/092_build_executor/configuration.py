"""A bounded build graph with literal argv and whole-argument input/dependency/output placeholders."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from files import absolute, hashed, inside, present, read, regular
from py2rust.stdlib import (
    Json, json_array, json_canonical, json_int, json_keys, json_loads_unique, json_string, path_parent,
    regex_fullmatch,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected fields"
    return


def identifier(name: str) -> None:
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid identifier"
    return


def relative(value: Json, base: str) -> str:
    path: str = json_string(value)
    parts: list[str] = path.split("/")
    assert 1 <= len(path.encode()) <= 1024 and len(parts) <= 16, "relative path bounds"
    for part in parts:
        assert part not in ["", ".", ".."] and "\x00" not in part, "invalid relative path"
    resolved: str = absolute(path, base)
    assert inside(resolved, base), "path escapes workspace"
    return resolved


def environment(value: Json) -> dict[str, str]:
    result: dict[str, str] = {}
    size: int = 0
    assert len(json_keys(value)) <= 32, "at most 32 environment variables"
    for name in json_keys(value):
        text: str = json_string(value[name])
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_]{0,127}", name) and "\x00" not in text, "invalid environment"
        size = size + len(name.encode()) + len(text.encode()) + 2
        result[name] = text
    assert size <= 16384, "environment exceeds 16 KiB"
    return result


def load(path: str) -> Json:
    before: Json = regular(path)
    config: Json = json_loads_unique(read(path, 262144).decode())
    exact(config, ["version", "state", "targets"])
    assert json_int(config["version"]) == 1, "unsupported version"
    base: str = path_parent(path)
    state: str = relative(config["state"], base)
    targets: Json = {}
    inputs: list[str] = [path]
    outputs: list[str] = []
    rows: list[Json] = json_array(config["targets"])
    assert len(rows) <= 16, "at most 16 targets"
    budget: int = 0
    for row in rows:
        exact(row, ["id", "inputs", "dependencies", "output", "argv", "environment", "timeout_ms", "max_output"])
        name: str = json_string(row["id"])
        identifier(name)
        assert name not in json_keys(targets), "duplicate target"
        row["recipe"] = hashed(json_canonical(row).encode())
        input_paths: Json = {}
        assert len(json_keys(row["inputs"])) <= 8, "at most eight direct inputs"
        for key in json_keys(row["inputs"]):
            identifier(key)
            source: str = relative(row["inputs"][key], base)
            regular(source)
            inputs.append(source)
            input_paths[key] = source
        output: str = relative(row["output"], base)
        assert output not in outputs, "duplicate output"
        if present(output):
            regular(output)
        outputs.append(output)
        environment(row["environment"])
        timeout: int = json_int(row["timeout_ms"])
        assert 1 <= timeout <= 60000 and 0 <= json_int(row["max_output"]) <= 65536, "command limits"
        budget = budget + timeout
        dependencies: set[str] = set()
        for dependency in json_array(row["dependencies"]):
            dep: str = json_string(dependency)
            identifier(dep)
            assert dep not in dependencies, "duplicate dependency"
            dependencies.add(dep)
        assert len(dependencies) <= 16 and 1 <= len(json_array(row["argv"])) <= 64, "dependency/argv limits"
        assert "{output}" in json_array(row["argv"]), "command must use output placeholder"
        for argument in json_array(row["argv"]):
            text: str = json_string(argument)
            assert len(text.encode()) <= 1024 and "\x00" not in text, "argument bounds"
            if text.startswith("{"):
                assert (
                    text == "{output}"
                    or (text.startswith("{input:") and text.endswith("}") and text[7:-1] in json_keys(input_paths))
                    or (text.startswith("{dependency:") and text.endswith("}") and text[12:-1] in dependencies)
                ), "unknown placeholder"
        row["input_paths"] = input_paths
        row["output_path"] = output
        targets[name] = row
    assert budget <= 120000, "suite timeout budget exceeded"
    for item in inputs + outputs:
        assert not inside(item, state) and item != state + ".lock", "state overlaps data"
    for output in outputs:
        for item in inputs:
            assert not inside(item, output) and not inside(output, item), "output overlaps input"
    order: list[str] = []
    while len(order) < len(json_keys(targets)):
        before_count: int = len(order)
        for name in sorted(json_keys(targets)):
            if name not in order:
                ready: bool = True
                for dependency in json_array(targets[name]["dependencies"]):
                    dep: str = json_string(dependency)
                    assert dep in json_keys(targets), "unknown dependency"
                    ready = ready and dep in order
                if ready:
                    order.append(name)
                    break
        assert len(order) > before_count, "dependency cycle"
    guards: Json = {}
    guards[path] = before
    return {"root": base, "state": state, "targets": targets, "order": order, "guards": guards}
