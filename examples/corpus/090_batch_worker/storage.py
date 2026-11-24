"""Commit progress and results together, then derive an independently replayable final report."""

# ruff: noqa: I001, PLR1711 - compact runtime imports and explicit subset returns
from configuration import exact
from files import Document, checkpoint, hashed, present, read, regular, unchanged
from state import empty, report, validate
from py2rust.stdlib import (
    Json,
    directory_names,
    file_open,
    file_sync,
    file_write,
    json_canonical,
    json_int,
    json_loads_unique,
    json_string,
    mkdir_new,
    path_join,
    path_parent,
    path_stat,
    remove_file,
    replace_file,
    sync_directory,
)


def load(root: str, binding: Json, jobs: list[Json]) -> Json:
    if not present(root):
        mkdir_new(root)
        sync_directory(path_parent(root))
    assert json_string(path_stat(root, False)["kind"]) == "directory", "output must be a directory"
    for name in directory_names(root, 4):
        assert name in ["state.json", "report.json", "control.tmp"], "unknown output file"
        regular(path_join(root, name))
    state: Json = empty(binding)
    if present(path_join(root, "state.json")):
        document: Document = read(path_join(root, "state.json"), 8388608)
        envelope: Json = json_loads_unique(document.data.decode())
        exact(envelope, ["value", "sha256"])
        state = envelope["value"]
        assert json_string(envelope["sha256"]) == hashed(json_canonical(state).encode()), "checkpoint checksum mismatch"
    validate(state, binding, jobs)
    if present(path_join(root, "report.json")):
        assert present(path_join(root, "state.json")), "report without checkpoint"
        assert json_int(state["completed"]) == len(jobs), "report before completion"
        saved: Document = read(path_join(root, "report.json"), 8388608)
        assert saved.data == report(state), "final report mismatch"
    return state


def commit(root: str, name: str, data: bytes, completed: int, inputs: list[Document]) -> None:
    assert len(data) <= 8388608, "checkpoint/report byte limit exceeded"
    temporary: str = path_join(root, "control.tmp")
    destination: str = path_join(root, name)
    if present(temporary):
        regular(temporary)
    with file_open(temporary, "w+b") as handle:
        file_write(handle, data)
        file_sync(handle)
    checkpoint("staged" if name == "state.json" else "report-staged", completed)
    unchanged(inputs)
    regular(temporary)
    if present(destination):
        regular(destination)
    replace_file(temporary, destination)
    sync_directory(root)
    checkpoint("committed" if name == "state.json" else "report-published", completed)
    return


def save(root: str, state: Json, inputs: list[Document]) -> None:
    data: bytes = (json_canonical({"value": state, "sha256": hashed(json_canonical(state).encode())}) + "\n").encode()
    commit(root, "state.json", data, json_int(state["completed"]), inputs)
    return


def finish(root: str, state: Json, inputs: list[Document]) -> None:
    unchanged(inputs)
    if not present(path_join(root, "report.json")):
        commit(root, "report.json", report(state), json_int(state["completed"]), inputs)
    temporary: str = path_join(root, "control.tmp")
    if present(temporary):
        regular(temporary)
        remove_file(temporary)
        sync_directory(root)
    return
