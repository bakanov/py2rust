"""Read a bounded collection of regular files without changing or executing source."""

from dataclasses import dataclass

from documents import Document, absolute, present, read
from lexing import Highlight, scan

from py2rust.stdlib import (
    Json,
    json_array,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_same,
)


@dataclass
class Source:
    label: str
    document: Document
    highlight: Highlight


@dataclass
class Project:
    output: str
    theme: str
    sources: list[Source]


def load(config: Document) -> Project:
    value: Json = json_loads(config.data.decode())
    assert sorted(json_keys(value)) == ["files", "output", "theme", "version"], "invalid project fields"
    assert json_int(value["version"]) == 1, "unsupported project version"
    output: str = absolute(json_string(value["output"]), path_parent(config.path))
    assert not present(output), "output already exists"
    theme: str = json_string(value["theme"])
    assert theme in ["light", "dark"], "theme must be light or dark"
    entries: list[Json] = json_array(value["files"])
    assert 1 <= len(entries) <= 16, "expected 1..16 source files"
    sources: list[Source] = []
    labels: set[str] = set()
    paths: list[str] = []
    size: int = 0
    count: int = 0
    for entry in entries:
        assert sorted(json_keys(entry)) == ["label", "source"], "invalid source fields"
        label: str = json_string(entry["label"])
        assert 1 <= len(label) <= 80 and label not in labels, "invalid or duplicate label"
        assert "\x00" not in label and "\n" not in label and "\r" not in label, "label must be one line"
        labels.add(label)
        path: str = absolute(json_string(entry["source"]), path_parent(config.path))
        for previous in paths:
            assert path != previous and not path_same(path, previous), "duplicate or aliased source"
        paths.append(path)
        document: Document = read(path, 65536)
        size = size + len(document.data)
        assert size <= 262144, "project source exceeds 256 KiB"
        highlighted: Highlight = scan(document.data.decode())
        count = count + len(highlighted.tokens)
        assert count <= 32768, "project exceeds 32768 tokens"
        sources.append(Source(label, document, highlighted))
    return Project(output, theme, sources)
