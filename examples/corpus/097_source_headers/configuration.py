"""Strict requests and policies for a bounded text-only header checker."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from dataclasses import dataclass
from documents import Document, absolute, present, read
from py2rust.stdlib import (
    Json, json_array, json_int, json_keys, json_loads_unique, json_string, path_parent, regex_fullmatch,
)


@dataclass
class Job:
    mode: str
    output: str
    policy: Json
    entries: list[Json]
    inputs: list[Document]


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected fields"
    return


def relative(name: str, limit: int, depth: int) -> None:
    assert 1 <= len(name) <= limit and regex_fullmatch(r"[^\x00-\x1f\x7f\\]+", name), "invalid relative path"
    parts: list[str] = name.split("/")
    assert len(parts) <= depth, "path depth limit"
    for part in parts:
        assert part not in ["", ".", ".."] and len(part.encode()) <= 240, "invalid path component"
    return


def policy(value: Json) -> None:
    exact(value, ["year", "owners", "licenses"])
    assert 1900 <= json_int(value["year"]) <= 9999, "invalid current year"
    for key in ["owners", "licenses"]:
        entries: list[Json] = json_array(value[key])
        assert 1 <= len(entries) <= 8, "one to eight policy choices required"
        seen: set[str] = set()
        for item in entries:
            text: str = json_string(item)
            assert 1 <= len(text) <= 128 and text.strip() == text, "invalid policy choice"
            assert not regex_fullmatch(r"[\s\S]*[\x00-\x1f\x7f][\s\S]*", text), "control in policy choice"
            assert text not in seen, "duplicate policy choice"
            if key == "licenses":
                assert regex_fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]{0,63}", text), "invalid license label"
            seen.add(text)
    return


def load(document: Document) -> Job:
    config: Json = json_loads_unique(document.data.decode())
    mode: str = json_string(config["mode"])
    assert mode in ["check", "apply"], "unknown mode"
    fields: list[str] = ["version", "mode", "output", "patches"]
    if mode == "check":
        fields = ["version", "mode", "output", "policy", "files"]
    exact(config, fields)
    assert json_int(config["version"]) == 1, "unsupported request version"
    base: str = path_parent(document.path)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    inputs: list[Document] = [document]
    specification: Json = config
    if mode == "apply":
        patch_file: Document = read(absolute(json_string(config["patches"]), base), 4194304)
        specification = json_loads_unique(patch_file.data.decode())
        exact(specification, ["version", "policy", "files"])
        assert json_int(specification["version"]) == 1, "unsupported patch version"
        inputs.append(patch_file)
        base = path_parent(patch_file.path)
    policy(specification["policy"])
    entries: list[Json] = json_array(specification["files"])
    assert len(entries) <= 32, "at most 32 files"
    names: set[str] = set()
    paths: set[str] = set()
    total: int = 0
    for entry in entries:
        fields = ["name", "path", "style"]
        if mode == "apply":
            fields = ["name", "path", "style", "before_sha256", "after_sha256", "edit"]
        exact(entry, fields)
        name: str = json_string(entry["name"])
        relative(name, 240, 8)
        relative(json_string(entry["path"]), 256, 9)
        path: str = absolute(json_string(entry["path"]), base)
        assert name not in names and path not in paths, "duplicate name or source path"
        for previous in names:
            assert not name.startswith(previous + "/") and not previous.startswith(name + "/"), "name prefix collision"
        assert json_string(entry["style"]) in ["hash", "slash"], "unknown comment style"
        source: Document = read(path, 65536)
        total = total + len(source.data)
        assert total <= 1048576, "source byte budget exceeded"
        inputs.append(source)
        names.add(name)
        paths.add(path)
    return Job(mode, output, specification["policy"], entries, inputs)
