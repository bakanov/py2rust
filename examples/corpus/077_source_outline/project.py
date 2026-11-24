"""Load a named collection of Python modules without importing or executing them."""

from dataclasses import dataclass

from documents import Document, absolute, present, read

from py2rust.stdlib import (
    Json,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_name,
    path_parent,
    python_statement_tree,
    regex_fullmatch,
)


@dataclass
class Source:
    name: str
    package: bool
    document: Document
    text: str
    tree: Json


@dataclass
class Project:
    output: str
    modules: list[Source]


def load(config: Document) -> Project:
    value: Json = json_loads(config.data.decode())
    assert sorted(json_keys(value)) == ["modules", "output", "version"], "invalid project fields"
    assert json_int(value["version"]) == 1, "unsupported project version"
    output: str = absolute(json_string(value["output"]), path_parent(config.path))
    assert not present(output), "output already exists"
    entries: list[Json] = json_array(value["modules"])
    assert 1 <= len(entries) <= 32, "expected 1..32 modules"
    modules: list[Source] = []
    names: set[str] = set()
    paths: set[str] = set()
    total: int = 0
    for entry in entries:
        assert sorted(json_keys(entry)) in [["name", "source"], ["name", "package", "source"]], "invalid module fields"
        name: str = json_string(entry["name"])
        assert len(name) <= 128 and regex_fullmatch(
            r"[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*", name
        ), "invalid module name"
        assert name not in names, "duplicate module name"
        names.add(name)
        path: str = absolute(json_string(entry["source"]), path_parent(config.path))
        assert path.endswith(".py") and path not in paths, "duplicate or non-Python source"
        paths.add(path)
        document: Document = read(path, 131072)
        total = total + len(document.data)
        assert total <= 1048576, "project exceeds 1 MiB"
        text: str = document.data.decode()
        if text.startswith("\ufeff"):  # noqa: FURB188 - supported subset
            text = text[1:]
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        assert len(text.split("\n")) <= 4096, "module exceeds 4096 lines"
        package: bool = json_bool(json_get(entry, "package", path_name(path) == "__init__.py"))
        modules.append(Source(name, package, document, text, python_statement_tree(text)))
    return Project(output, modules)
