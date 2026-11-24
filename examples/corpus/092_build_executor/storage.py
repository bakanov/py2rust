"""Checksummed successful cache entries; invalidation is durable before a command starts."""

# ruff: noqa: I001, PLR1711 - compact imports and explicit subset returns
from configuration import exact, identifier
from files import atomic, hashed, present, read, regular
from py2rust.stdlib import (
    Json, directory_names, json_canonical, json_int, json_keys, json_loads_unique, json_string, mkdir_new,
    path_join, path_parent, path_stat, regex_fullmatch, sync_directory,
)


def digest(value: Json) -> None:
    assert regex_fullmatch("[0-9a-f]{64}", json_string(value)), "invalid digest"
    return


def fingerprint(value: Json) -> None:
    exact(value, ["bytes", "mode", "sha256"])
    assert 0 <= json_int(value["bytes"]) <= 4194304 and 0 <= json_int(value["mode"]) <= 4095, "invalid file fingerprint"
    digest(value["sha256"])
    return


def signature(entry: Json) -> str:
    return hashed(
        json_canonical(
            {"recipe": entry["recipe"], "inputs": entry["inputs"], "dependencies": entry["dependencies"]}
        ).encode()
    )


def load(config: Json) -> Json:
    root: str = json_string(config["state"])
    if not present(root):
        mkdir_new(root)
        sync_directory(path_parent(root))
    info: Json = path_stat(root, False)
    assert json_string(info["kind"]) == "directory", "state must be a directory"
    for name in directory_names(root, 5):
        assert name in ["cache.json", "report.json", "control.tmp", "artifact.tmp"], "unknown state file"
        regular(path_join(root, name))
    for name in json_keys(config["targets"]):
        parent: Json = path_stat(path_parent(json_string(config["targets"][name]["output_path"])), False)
        assert json_int(parent["device"]) == json_int(info["device"]), "output/state must share a filesystem"
    entries: Json = {}
    cache: str = path_join(root, "cache.json")
    if present(cache):
        envelope: Json = json_loads_unique(read(cache, 2097152).decode())
        exact(envelope, ["version", "entries", "sha256"])
        entries = envelope["entries"]
        assert json_int(envelope["version"]) == 1 and json_string(envelope["sha256"]) == hashed(
            json_canonical(entries).encode()
        ), "cache version/checksum mismatch"
        assert len(json_keys(entries)) <= 16, "too many cache entries"
        for name in json_keys(entries):
            identifier(name)
            entry: Json = entries[name]
            exact(entry, ["recipe", "inputs", "dependencies", "signature", "output"])
            digest(entry["recipe"])
            assert json_string(entry["signature"]) == signature(entry), "cache signature mismatch"
            fingerprint(entry["output"])
            assert len(json_keys(entry["inputs"])) <= 8 and len(json_keys(entry["dependencies"])) <= 16, "cache bounds"
            for key in json_keys(entry["inputs"]):
                identifier(key)
                fingerprint(entry["inputs"][key])
            for key in json_keys(entry["dependencies"]):
                identifier(key)
                value: Json = entry["dependencies"][key]
                exact(value, ["signature", "output"])
                digest(value["signature"])
                fingerprint(value["output"])
            if name not in json_keys(config["targets"]):
                del entries[name]
    return entries


def save(config: Json, entries: Json, label: str) -> None:
    data: bytes = (
        json_canonical({"version": 1, "entries": entries, "sha256": hashed(json_canonical(entries).encode())}) + "\n"
    ).encode()
    atomic(path_join(json_string(config["state"]), "cache.json"), data, config["guards"], label)
    return
