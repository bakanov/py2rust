"""Create fixtures exclusively and remove only entries still matching their receipt."""

from documents import checkpoint, identity, observe, present, save
from manifest import Manifest
from receipt import removal_order, verify

from py2rust.stdlib import (
    Json,
    file_open,
    file_sync,
    file_write,
    json_bool,
    json_equal,
    json_int,
    json_keys,
    json_string,
    mkdir_new,
    path_join,
    path_parent,
    remove_dir,
    remove_file,
    sync_directory,
)


def guard_parents(body: Json, name: str) -> None:
    root: str = json_string(body["root"])
    assert json_equal(identity(path_parent(root)), body["parent"]), "root parent changed"
    if name != "":
        parent: str = path_parent(name)
        while True:
            parent = "" if parent == "." else parent
            expected: Json = body["entries"][parent]["stamp"]
            assert expected is not None and json_equal(
                identity(path_join(root, parent)), expected
            ), "fixture parent changed"
            if parent == "":
                break
            parent = path_parent(parent)


def create(manifest: Manifest, receipt_path: str) -> Json:
    body: Json = manifest.receipt
    root: str = json_string(body["root"])
    assert not present(receipt_path), "receipt already exists; retain it for verification or cleanup"
    verify(body)
    save(receipt_path, body)
    checkpoint("receipt", 0)
    entries: Json = body["entries"]
    index: int = 0
    for name in json_keys(entries):
        entry: Json = entries[name]
        path: str = path_join(root, name)
        if json_bool(entry["owned"]):
            checkpoint("before", index)
            guard_parents(body, name)
            if json_string(entry["kind"]) == "directory":
                mkdir_new(path)
            else:
                with file_open(path, "x+b") as handle:
                    file_write(handle, manifest.payloads[name])
                    file_sync(handle)
            checkpoint("written", index)
            sync_directory(path_parent(path))
            entry["stamp"] = observe(path, json_string(entry["kind"]))
            if json_string(entry["kind"]) == "file":
                assert json_equal(entry["stamp"]["size"], entry["size"]) and json_equal(
                    entry["stamp"]["sha256"], entry["sha256"]
                ), "written content differs"
            entries[name] = entry
            body["entries"] = entries
            save(receipt_path, body)
            checkpoint("recorded", index)
        index = index + 1
    body["phase"] = "ready"
    verify(body)
    save(receipt_path, body)
    return body


def cleanup(body: Json, receipt_path: str) -> Json:
    verify(body)
    if json_string(body["phase"]) == "cleaned":
        return body
    root: str = json_string(body["root"])
    body["phase"] = "cleaning"
    save(receipt_path, body)
    order: list[str] = removal_order(body)
    step: int = json_int(body["step"])
    checkpoint("cleaning", step)
    while step < len(order):
        name: str = order[step]
        path: str = path_join(root, name)
        entry: Json = body["entries"][name]
        checkpoint("removing", step)
        guard_parents(body, name)
        if present(path):
            assert json_equal(
                observe(path, json_string(entry["kind"])), entry["stamp"]
            ), "fixture changed before cleanup"
            if json_string(entry["kind"]) == "file":
                remove_file(path)
            else:
                remove_dir(path)
            checkpoint("removed", step)
        sync_directory(path_parent(path))
        step = step + 1
        body["step"] = step
        save(receipt_path, body)
        checkpoint("saved", step)
    body["phase"] = "cleaned"
    verify(body)
    save(receipt_path, body)
    return body
