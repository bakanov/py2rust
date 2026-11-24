"""Validate complete local indexes and requests before any dependency search."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from dataclasses import dataclass
from documents import Document, absolute, present, read
from versions import requirement, version
from py2rust.stdlib import (
    Json, json_array, json_int, json_keys, json_loads_unique, json_string, path_parent, regex_fullmatch,
)


@dataclass
class Job:
    mode: str
    output: str
    config: Json
    index: Document
    packages: Json
    roots: Json
    root_text: Json
    choices: dict[str, str]
    lock_hash: str
    inputs: list[Document]


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def package_name(name: str) -> None:
    assert regex_fullmatch("[A-Za-z][A-Za-z0-9_-]{0,31}", name), "invalid package name"
    return


def requirements(value: Json, limit: int) -> Json:
    assert len(json_keys(value)) <= limit, "too many dependencies"
    parsed: Json = {}
    for name in sorted(json_keys(value)):
        package_name(name)
        parsed[name] = requirement(json_string(value[name]))
    return parsed


def load(document: Document) -> Job:
    config: Json = json_loads_unique(document.data.decode())
    mode: str = json_string(config["mode"])
    fields: list[str] = ["version", "mode", "index", "output", "lock"]
    if mode == "resolve":
        fields = ["version", "mode", "index", "output", "roots", "max_steps", "max_conflicts"]
        assert 1 <= json_int(config["max_steps"]) <= 10000, "invalid search budget"
        assert 1 <= json_int(config["max_conflicts"]) <= 128, "invalid conflict limit"
    assert mode in ["resolve", "verify"], "unknown mode"
    exact(config, fields)
    assert json_int(config["version"]) == 1, "unsupported version"
    base: str = path_parent(document.path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    index: Document = read(absolute(json_string(config["index"]), base), 524288)
    raw: Json = json_loads_unique(index.data.decode())
    exact(raw, ["version", "packages"])
    assert json_int(raw["version"]) == 1 and len(json_keys(raw["packages"])) <= 16, "invalid index"
    packages: Json = {}
    for name in sorted(json_keys(raw["packages"])):
        package_name(name)
        entries: list[Json] = json_array(raw["packages"][name])
        assert len(entries) <= 8, "at most eight versions per package"
        releases: Json = {}
        order: list[tuple[tuple[int, int, int], str]] = []
        for entry in entries:
            exact(entry, ["version", "dependencies"])
            text: str = json_string(entry["version"])
            number: tuple[int, int, int] = version(text)
            assert text not in json_keys(releases), "duplicate package version"
            releases[text] = requirements(entry["dependencies"], 8)
            order.append((number, text))
        versions: list[str] = []
        for item in sorted(order):
            versions.append(item[1])
        packages[name] = {"order": versions, "releases": releases}
    inputs: list[Document] = [document, index]
    choices: dict[str, str] = {}
    root_text: Json = config["roots"] if mode == "resolve" else None
    lock_hash: str = ""
    if mode == "verify":
        lock: Document = read(absolute(json_string(config["lock"]), base), 65536)
        value: Json = json_loads_unique(lock.data.decode())
        exact(value, ["version", "index_sha256", "roots", "packages"])
        assert json_int(value["version"]) == 1, "unsupported lock version"
        lock_hash = json_string(value["index_sha256"])
        assert regex_fullmatch("[0-9a-f]{64}", lock_hash), "invalid index digest"
        root_text = value["roots"]
        assert len(json_keys(value["packages"])) <= 16, "too many locked packages"
        for name in json_keys(value["packages"]):
            package_name(name)
            text: str = json_string(value["packages"][name])
            version(text)
            choices[name] = text
        inputs.append(lock)
    return Job(
        mode, output, config, index, packages, requirements(root_text, 16), root_text, choices, lock_hash, inputs
    )
