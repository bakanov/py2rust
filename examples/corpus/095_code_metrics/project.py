"""Discover a bounded import search root and parse snapshots without importing source code."""
# ruff: noqa: I001, PLR1711, BLE001 - compact imports and explicit subset returns
from dataclasses import dataclass
from documents import Document, absolute, discover, present, read
from py2rust.stdlib import (
    Json, json_array, json_int, json_keys, json_loads_unique, json_string, path_parent, python_statement_tree,
    regex_fullmatch, sha256_digest, sha256_new, sha256_update,
)


@dataclass
class Source:
    relative: str
    name: str
    package: bool
    document: Document
    text: str
    tree: Json


@dataclass
class Project:
    config: Document
    root: str
    output: str
    excluded: list[str]
    prefix: str
    thresholds: Json
    paths: list[str]
    sources: list[Source]


def exact(value: Json, fields: list[str]) -> None:
    assert sorted(json_keys(value)) == sorted(fields), "unexpected configuration fields"
    return


def digest(data: bytes) -> str:
    return sha256_digest(sha256_update(sha256_new(), data))


def load(document: Document) -> Project:
    config: Json = json_loads_unique(document.data.decode())
    exact(config, ["version", "root", "output", "package", "exclude", "thresholds"])
    assert json_int(config["version"]) == 1, "unsupported version"
    base: str = path_parent(document.path)
    root: str = absolute(json_string(config["root"]), base)
    output: str = absolute(json_string(config["output"]), base)
    assert not present(output), "output already exists"
    assert root != "/" and output != root and not output.startswith(root + "/"), "output must be outside source root"
    prefix: str = json_string(config["package"])
    pattern: str = r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*"
    assert len(prefix) <= 128 and (prefix == "" or regex_fullmatch(pattern, prefix)), "package name"
    if prefix != "":
        python_statement_tree("import " + prefix)
    excluded: list[str] = []
    assert len(json_array(config["exclude"])) <= 16, "too many exclusions"
    for entry in json_array(config["exclude"]):
        name: str = json_string(entry)
        assert regex_fullmatch("[A-Za-z_][A-Za-z0-9_-]{0,63}", name) and name not in excluded, "invalid exclusion"
        excluded.append(name)
    thresholds: Json = config["thresholds"]
    exact(thresholds, ["lines", "statements", "depth"])
    for name in json_keys(thresholds):
        limit: int = json_int(thresholds[name])
        assert 0 <= limit <= (64 if name == "depth" else 4096), "invalid threshold"
    paths: list[str] = discover(root, excluded)
    sources: list[Source] = []
    total: int = 0
    statements: int = 0
    for relative in paths:
        name: str = relative[:-3].replace("/", ".")
        package: bool = name == "__init__" or name.endswith(".__init__")
        if package:
            name = "" if name == "__init__" else name[:-9]
        assert name != "" or prefix != "", "root __init__.py requires a package name"
        if prefix != "":
            name = prefix if name == "" else prefix + "." + name
        assert len(name) <= 256 and regex_fullmatch(pattern, name), "invalid module path"
        python_statement_tree("import " + name)
        try:
            source: Document = read(absolute(relative, root), 131072)
            total = total + len(source.data)
            assert total <= 1048576, "source project exceeds 1 MiB"
            text: str = source.data.decode()
            if text.startswith("\ufeff"):  # noqa: FURB188 - supported subset
                text = text[1:]
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            assert len(text.split("\n")) - (1 if text.endswith("\n") else 0) <= 4096, "source module exceeds 4096 lines"
            tree: Json = python_statement_tree(text)
            statements = statements + len(json_array(tree["nodes"]))
            assert statements <= 32768, "source project exceeds 32768 statements"
            sources.append(Source(relative, name, package, source, text, tree))
        except Exception as error:
            assert False, relative + ": " + str(error)
    return Project(document, root, output, excluded, prefix, thresholds, paths, sources)
