"""Validate bounded rules and disjoint field paths without exporting configuration values."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from documents import Document, absolute, present
from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_kind,
    json_loads_unique,
    json_string,
    path_parent,
    regex_search,
)


def exact(value: Json, names: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(names), "unexpected configuration fields"
    return


def load(document: Document) -> Json:
    config: Json = json_loads_unique(document.data.decode())
    exact(config, ["version", "input", "output", "missing", "targets", "rules"])
    assert json_int(config["version"]) == 1, "unsupported version"
    assert json_string(config["missing"]) in ["skip", "error"], "invalid missing-field policy"
    source: str = absolute(json_string(config["input"]), path_parent(document.path))
    output: str = absolute(json_string(config["output"]), path_parent(document.path))
    assert source != document.path and not present(output), "input/output conflict"
    config["input"] = source
    config["output"] = output
    paths: list[Json] = json_array(config["targets"])
    assert 1 <= len(paths) <= 32, "expected 1..32 targets"
    for index in range(len(paths)):
        path: list[Json] = json_array(paths[index])
        assert 1 <= len(path) <= 16, "expected 1..16 path components"
        for component in path:
            if json_kind(component) == "string":
                assert len(json_string(component).encode()) <= 128, "path key too long"
            else:
                assert 0 <= json_int(component) <= 4095, "invalid array index"
        for previous in range(index):
            other: list[Json] = json_array(paths[previous])
            length: int = min(len(path), len(other))
            assert json_canonical(path[:length]) != json_canonical(other[:length]), "overlapping target paths"
    rules: list[Json] = json_array(config["rules"])
    assert 1 <= len(rules) <= 32, "expected 1..32 rules"
    for rule in rules:
        exact(rule, ["kind", "pattern", "replacement"])
        kind: str = json_string(rule["kind"])
        assert kind in ["literal", "regex"], "invalid rule kind"
        pattern: str = json_string(rule["pattern"])
        replacement: str = json_string(rule["replacement"])
        assert 1 <= len(pattern.encode()) <= 512 and len(replacement.encode()) <= 256, "rule text limit exceeded"
        if kind == "regex":
            assert not regex_search(pattern, ""), "regex matches empty input"
    return config
