"""Receipts distinguish created entries from reused directories and unrelated content."""

from documents import (
    absolute,
    digest,
    document,
    fields,
    identity,
    observe,
    present,
    relative,
)

from py2rust.stdlib import (
    Json,
    directory_names,
    json_bool,
    json_equal,
    json_int,
    json_keys,
    json_string,
    path_join,
    path_parent,
    regex_fullmatch,
)


def load(path: str) -> Json:
    envelope: Json = document(path)
    fields(envelope, ["checksum", "receipt"])
    body: Json = envelope["receipt"]
    assert json_string(envelope["checksum"]) == digest(body), "receipt checksum mismatch"
    fields(body, ["version", "root", "parent", "phase", "step", "entries", "bytes"])
    root: str = json_string(body["root"])
    assert root != "/" and root == absolute(root) and json_int(body["version"]) == 1, "invalid receipt root/version"
    assert json_string(body["phase"]) in ["building", "ready", "cleaning", "cleaned"], "invalid receipt phase"
    entries: Json = body["entries"]
    names: list[str] = json_keys(entries)
    assert "" in names and len(names) <= 1000, "invalid receipt entry count"
    total: int = 0
    for name in names:
        if name != "":
            relative(name)
            parent: str = path_parent(name)
            parent = "" if parent == "." else parent
            assert parent in entries and json_string(entries[parent]["kind"]) == "directory", "missing parent"
        entry: Json = entries[name]
        fields(entry, ["kind", "owned", "stamp", "size", "sha256"])
        kind: str = json_string(entry["kind"])
        assert kind in ["file", "directory"] and (name != "" or kind == "directory"), "invalid entry kind"
        owned: bool = json_bool(entry["owned"])
        assert owned or (kind == "directory" and entry["stamp"] is not None), "invalid reused entry"
        size: int = json_int(entry["size"])
        assert 0 <= size <= 1048576, "invalid fixture size"
        if kind == "file":
            assert regex_fullmatch("[0-9a-f]{64}", json_string(entry["sha256"])), "invalid content hash"
            total = total + size
        else:
            assert size == 0 and json_string(entry["sha256"]) == "", "invalid directory payload"
    assert total == json_int(body["bytes"]) and total <= 4194304, "invalid total size"
    return body


def removal_order(body: Json) -> list[str]:
    result: list[str] = []
    for name in json_keys(body["entries"]):
        entry: Json = body["entries"][name]
        if json_bool(entry["owned"]) and entry["stamp"] is not None:
            result.append(name)
    result.reverse()
    return result


def verify(body: Json) -> bool:
    root: str = json_string(body["root"])
    assert json_equal(identity(path_parent(root)), body["parent"]), "root parent identity changed"
    phase: str = json_string(body["phase"])
    order: list[str] = removal_order(body)
    step: int = json_int(body["step"])
    assert 0 <= step <= len(order), "invalid cleanup step"
    assert phase in ["cleaning", "cleaned"] or step == 0, "unexpected cleanup progress"
    assert phase != "cleaned" or step == len(order), "incomplete cleaned receipt"
    removed: set[str] = set()
    for index in range(step):
        removed.add(order[index])
    pending: bool = False
    entries: Json = body["entries"]
    for name in json_keys(entries):
        path: str = path_join(root, name)
        entry: Json = entries[name]
        if name in removed or entry["stamp"] is None:
            assert not present(path), "removed or unrecorded fixture path is occupied: " + name
            assert phase != "ready", "ready receipt contains an uncreated entry"
        elif not present(path) and phase == "cleaning" and step < len(order) and name == order[step]:
            pending = True
        else:
            assert json_equal(observe(path, json_string(entry["kind"])), entry["stamp"]), "fixture changed: " + name
            if json_string(entry["kind"]) == "directory" and json_bool(entry["owned"]):
                for child in directory_names(path, 1001):
                    relative_name: str = child if name == "" else name + "/" + child
                    assert relative_name in entries, "unrecorded child in created directory: " + relative_name
    return pending
