"""A small protected namespace; only known temporary files are recovered."""

from common import document, fields, identifier, name, present, stamp, write_document

from py2rust.stdlib import (
    Json,
    directory_names,
    json_equal,
    json_int,
    json_string,
    mkdir_new,
    path_join,
    remove_file,
    sync_directory,
)


def open_store(config: Json, initialize: bool) -> None:
    repo: str = json_string(config["repository"])
    for entry in directory_names(repo, 8):
        assert entry in [".store.lock", "format.json", "blobs", "manifests", "refs", "staging"], "unknown store entry"
    if initialize:
        assert not present(path_join(repo, "format.json")), "already initialized"
        for entry in ["blobs", "manifests", "refs", "staging"]:
            path: str = path_join(repo, entry)
            if not present(path):
                mkdir_new(path)
            assert len(directory_names(path, 1)) == 0, "initialization requires empty directories"
        write_document(path_join(repo, "format.json"), {"format": "py2rust-artifacts", "version": 1})
        sync_directory(repo)
    assert json_equal(
        document(path_join(repo, "format.json")), {"format": "py2rust-artifacts", "version": 1}
    ), "unknown format"
    for entry in ["blobs", "manifests", "refs", "staging"]:
        assert json_string(stamp(path_join(repo, entry))["kind"]) == "directory", "invalid store directory"
    for entry in directory_names(path_join(repo, "staging"), 3):
        assert entry in ["blob.part", "manifest.part", "ref.part"], "unknown staging entry"
        path: str = path_join(repo, "staging/" + entry)
        assert json_string(stamp(path)["kind"]) == "file", "invalid temporary file"
        remove_file(path)
    sync_directory(path_join(repo, "staging"))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def room(config: Json, state: dict[str, Json], extra_nodes: int, extra_bytes: int) -> None:
    assert len(state) - 3 + extra_nodes <= json_int(config["max_nodes"]), "node budget exceeded"
    total: int = extra_bytes
    for key in state:
        if json_string(state[key]["kind"]) == "file":
            total = total + json_int(state[key]["size"])
    assert total <= json_int(config["max_bytes"]), "store byte budget exceeded"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def inventory(config: Json) -> dict[str, Json]:
    repo: str = json_string(config["repository"])
    state: dict[str, Json] = {}
    for folder in ["blobs", "manifests", "refs"]:
        state[folder] = stamp(path_join(repo, folder))
        for entry in directory_names(path_join(repo, folder), json_int(config["max_nodes"])):
            if folder == "blobs":
                identifier(entry)
            else:
                assert entry.endswith(".json"), "unknown namespace entry"
                if folder == "refs":
                    name(entry[:-5])
                else:
                    identifier(entry[:-5])
            key: str = folder + "/" + entry
            info: Json = stamp(path_join(repo, key))
            assert json_string(info["kind"]) == "file", "store entries must be regular files"
            limit: int = json_int(config["max_blob_bytes"]) if folder == "blobs" else 1048576
            assert json_int(info["size"]) <= limit, "store entry exceeds limit"
            state[key] = info
    room(config, state, 0, 0)
    return state


def references(repo: str, state: dict[str, Json]) -> dict[str, str]:
    roots: dict[str, str] = {}
    for key in state:
        if key.startswith("refs/"):
            row: Json = document(path_join(repo, key))
            fields(row, ["manifest"])
            roots[key[5:-5]] = identifier(json_string(row["manifest"]))
    return roots
