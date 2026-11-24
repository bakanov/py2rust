"""Ordered layers and explicit permissions for otherwise conflicting type changes."""

from dataclasses import dataclass

from documents import Document, absolute, distinct, fields, read
from model import pointer

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_int,
    json_string,
    path_parent,
    path_resolve,
    regex_fullmatch,
)


@dataclass
class Settings:
    documents: list[Document]
    names: list[str]
    allowed: set[str]
    output: str
    max_nodes: int


def load() -> Settings:
    path: str = absolute(env_get("MERGE_CONFIG", "merge.json"), path_resolve("."))
    source: Document = read(path, True)
    config: Json = source.value
    fields(config, ["layers", "type_changes", "output", "max_nodes"])
    maximum: int = json_int(config["max_nodes"])
    assert 1 <= maximum <= 20000, "max_nodes must be 1..20000"
    documents: list[Document] = [source]
    names: list[str] = []
    paths: list[str] = [path]
    layers: list[Json] = json_array(config["layers"])
    assert 1 <= len(layers) <= 16, "expected 1..16 layers"
    total: int = 0
    available: int = 0
    for layer in layers:
        fields(layer, ["name", "path", "required"])
        name: str = json_string(layer["name"])
        assert regex_fullmatch("[A-Za-z0-9_-]{1,64}", name) and name not in names, "invalid or repeated layer name"
        names.append(name)
        filename: str = absolute(json_string(layer["path"]), path_parent(path))
        distinct(filename, paths)
        paths.append(filename)
        document: Document = read(filename, json_bool(layer["required"]))
        documents.append(document)
        total = total + document.nodes
        assert total <= maximum, "total input node budget exceeded"
        if document.present:
            available = available + 1
    assert available > 0, "all layers are missing"
    allowed: set[str] = set()
    permissions: list[Json] = json_array(config["type_changes"])
    assert len(permissions) <= 128, "too many type-change permissions"
    for permission in permissions:
        permitted: str = pointer(json_string(permission))
        assert permitted not in allowed, "repeated type-change permission"
        allowed.add(permitted)
    output: str = absolute(json_string(config["output"]), path_parent(path))
    distinct(output, paths)
    return Settings(documents, names, allowed, output, maximum)
