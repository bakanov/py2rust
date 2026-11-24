"""Publication and collection happen only while the repository lock is held."""

from common import (
    checkpoint,
    checksum,
    encode,
    fields,
    identifier,
    name,
    outside,
    present,
    stamp,
    write_document,
)
from content import copy, digest
from graph import normalize, reachable
from repository import inventory, room

from py2rust.stdlib import (
    Json,
    json_array,
    json_equal,
    json_int,
    json_string,
    path_join,
    path_name,
    path_parent,
    remove_file,
    rename_no_replace,
    replace_file,
    sync_directory,
)


def publish(repo: str, temporary: str, target: str, replace: bool) -> None:
    if replace:
        replace_file(path_join(repo, temporary), path_join(repo, target))
    else:
        rename_no_replace(path_join(repo, temporary), path_join(repo, target))
    sync_directory(path_join(repo, path_parent(target)))
    sync_directory(path_join(repo, "staging"))
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def import_file(config: Json, state: dict[str, Json], request: Json) -> Json:
    fields(request, ["path"])
    repo: str = json_string(config["repository"])
    source: str = outside(json_string(request["path"]), repo)
    before: Json = stamp(source)
    size: int = json_int(before["size"])
    assert size <= json_int(config["max_blob_bytes"]), "blob exceeds limit"
    hashed: str = digest(source, size)
    checkpoint("import_hashed")
    key: str = "blobs/" + hashed
    created: bool = key not in state
    if created:
        room(config, state, 1, size)
        assert copy(source, path_join(repo, "staging/blob.part"), size) == hashed, "source changed during copy"
        assert json_equal(stamp(source), before), "source changed during import"
        checkpoint("blob_staged")
        publish(repo, "staging/blob.part", key, False)
        checkpoint("blob_published")
    else:
        assert digest(path_join(repo, key), size) == hashed, "existing blob is corrupt"
        assert json_equal(stamp(source), before), "source changed during import"
    return {"digest": hashed, "size": size, "created": created}


def pin(
    config: Json, state: dict[str, Json], roots: dict[str, str], reference: str, hashed: str, expected: str
) -> None:
    name(reference)
    identifier(hashed)
    assert roots.get(reference, "-") == expected, "reference changed; expected value does not match"
    repo: str = json_string(config["repository"])
    key: str = "refs/" + reference + ".json"
    value: Json = {"manifest": hashed}
    previous: int = json_int(state[key]["size"]) if key in state else 0
    room(config, state, 0 if key in state else 1, len(encode(value)) - previous)
    sync_directory(path_join(repo, "blobs"))
    sync_directory(path_join(repo, "manifests"))
    write_document(path_join(repo, "staging/ref.part"), value)
    checkpoint("ref_staged")
    publish(repo, "staging/ref.part", key, key in state)
    checkpoint("ref_published")
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def manifest(config: Json, state: dict[str, Json], roots: dict[str, str], request: Json) -> Json:
    fields(request, ["name", "expected", "files", "includes", "metadata"])
    reference: str = json_string(request["name"])
    expected: str = json_string(request["expected"])
    assert roots.get(reference, "-") == expected, "reference changed"
    if reference != "":
        name(reference)
    else:
        assert expected == "-", "unrooted manifest needs expected '-'"
    body: Json = normalize(
        {"version": 1, "files": request["files"], "includes": request["includes"], "metadata": request["metadata"]}
    )
    reachable(config, state, [], body)
    hashed: str = checksum(body)
    key: str = "manifests/" + hashed + ".json"
    repo: str = json_string(config["repository"])
    if key not in state:
        room(config, state, 1, len(encode(body)))
        write_document(path_join(repo, "staging/manifest.part"), body)
        checkpoint("manifest_staged")
        publish(repo, "staging/manifest.part", key, False)
        state = inventory(config)
    else:
        reachable(config, state, [hashed], None)
    checkpoint("manifest_published")
    if reference != "":
        pin(config, state, roots, reference, hashed, expected)
    return {"manifest": hashed, "name": reference}


def retrieve(config: Json, state: dict[str, Json], request: Json) -> Json:
    fields(request, ["digest", "destination"])
    repo: str = json_string(config["repository"])
    hashed: str = identifier(json_string(request["digest"]))
    key: str = "blobs/" + hashed
    assert key in state, "blob not found"
    target: str = outside(json_string(request["destination"]), repo)
    temporary: str = path_join(path_parent(target), "." + path_name(target) + ".artifact-incomplete")
    assert not present(target) and not present(temporary), "destination or incomplete retrieval already exists"
    size: int = json_int(state[key]["size"])
    assert copy(path_join(repo, key), temporary, size) == hashed, "blob digest mismatch"
    checkpoint("get_staged")
    rename_no_replace(temporary, target)
    sync_directory(path_parent(target))
    return {"digest": hashed, "size": size}


def collect(config: Json, state: dict[str, Json], roots: dict[str, str]) -> Json:
    identifiers: list[str] = []
    for key in roots:  # noqa: PLC0206 - typed key iteration
        identifiers.append(roots[key])
    live: Json = reachable(config, state, identifiers, None)
    sync_directory(path_join(json_string(config["repository"]), "refs"))
    kept: set[str] = set()
    for item in json_array(live["blobs"]):
        kept.add("blobs/" + json_string(item))
    for item in json_array(live["manifests"]):
        kept.add("manifests/" + json_string(item) + ".json")
    checkpoint("gc_marked")
    assert json_equal(inventory(config), state), "store changed during graph traversal"
    removed: list[str] = []
    for key in sorted(list(state)):  # noqa: C414 - typed key snapshot
        if "/" not in key or key.startswith("refs/") or key in kept:
            continue
        remove_file(path_join(json_string(config["repository"]), key))
        removed.append(key)
        checkpoint("gc_removed")
    for folder in ["blobs", "manifests"]:
        sync_directory(path_join(json_string(config["repository"]), folder))
    return {"removed": removed, "live": live}
