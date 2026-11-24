"""Validate immutable manifests and mark the complete graph of reachable blobs."""

from common import checksum, document, fields, identifier
from content import digest

from py2rust.stdlib import (
    Json,
    json_array,
    json_equal,
    json_int,
    json_keys,
    json_kind,
    json_string,
    path_join,
)


def normalize(value: Json) -> Json:
    fields(value, ["version", "files", "includes", "metadata"])
    assert (
        json_int(value["version"]) == 1 and json_kind(value["metadata"]) == "object"
    ), "invalid manifest version/metadata"
    files: list[str] = json_keys(value["files"])
    assert len(files) <= 1000, "too many artifact names"
    for name in files:
        assert name != "" and len(name.encode()) <= 1024 and "\x00" not in name, "invalid artifact name"
        for part in name.split("/"):
            assert part not in ["", ".", ".."], "unsafe artifact name"
        row: Json = value["files"][name]
        fields(row, ["digest", "size"])
        identifier(json_string(row["digest"]))
        assert json_int(row["size"]) >= 0 and json_int(row["size"]) <= 1099511627776, "invalid blob size"
    includes: list[str] = []
    seen: set[str] = set()
    for item in json_array(value["includes"]):
        hashed: str = identifier(json_string(item))
        assert hashed not in seen and len(includes) < 128, "duplicate or excessive manifest dependencies"
        seen.add(hashed)
        includes.append(hashed)
    includes.sort()
    return {"version": 1, "files": value["files"], "includes": includes, "metadata": value["metadata"]}


def read(repo: str, hashed: str) -> Json:
    value: Json = document(path_join(repo, "manifests/" + identifier(hashed) + ".json"))
    assert checksum(value) == hashed, "manifest digest mismatch"
    assert json_equal(normalize(value), value), "manifest is not canonical"
    return value


def reachable(config: Json, state: dict[str, Json], roots: list[str], seed: Json) -> Json:
    repo: str = json_string(config["repository"])
    pending: list[str] = []
    manifests: set[str] = set()
    blobs: set[str] = set()
    for hashed in roots:
        if hashed not in manifests:
            manifests.add(identifier(hashed))
            pending.append(hashed)
    cursor: int = -1
    while cursor < len(pending):
        body: Json = seed
        if cursor >= 0:
            body = read(repo, pending[cursor])
        cursor = cursor + 1
        if body is None:
            continue
        body = normalize(body)
        for alias in json_keys(body["files"]):
            row: Json = body["files"][alias]
            hashed: str = json_string(row["digest"])
            key: str = "blobs/" + hashed
            assert key in state and json_int(state[key]["size"]) == json_int(row["size"]), "missing or wrong-sized blob"
            if hashed not in blobs:
                assert digest(path_join(repo, key), json_int(row["size"])) == hashed, "corrupt blob"
                blobs.add(hashed)
        for item in json_array(body["includes"]):
            hashed: str = json_string(item)
            if hashed not in manifests:
                assert len(pending) < json_int(config["max_nodes"]), "manifest graph exceeds node budget"
                manifests.add(hashed)
                pending.append(hashed)
    return {"manifests": sorted(list(manifests)), "blobs": sorted(list(blobs))}  # noqa: C414 - explicit typed lists
