"""Bounded JSON documents, canonical signatures and safe report locations."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_size,
    json_array,
    json_dumps,
    json_int,
    json_keys,
    json_kind,
    json_loads,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_name,
    path_parent,
    path_resolve,
    path_same,
    path_stat,
    regex_search,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def checksum(value: Json) -> str:
    return sha256_digest(sha256_update(sha256_new(), json_dumps(value).encode()))


def fields(value: Json, names: list[str]) -> None:
    assert json_kind(value) == "object" and sorted(json_keys(value)) == sorted(names), "invalid document fields"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def document(path: str) -> Json:
    assert json_string(path_stat(path, False)["kind"]) == "file", "document must be regular"
    with file_open(path, "rb") as handle:
        assert file_size(handle) <= 16777216, "document exceeds 16 MiB"
        data: bytes = b""
        while True:
            chunk: bytes = file_read(handle, 65536)
            if len(chunk) == 0:
                break
            data = data + chunk
            assert len(data) <= 16777216, "document exceeds 16 MiB"
        return json_loads(data.decode())


def relative(name: str) -> None:
    assert len(name.encode()) <= 2048 and "\x00" not in name, "invalid relative path"
    if name != "":
        parts: list[str] = name.split("/")
        assert len(parts) <= 64, "depth exceeds 64"
        for part in parts:
            assert part not in ["", ".", ".."], "unsafe path component"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def under(name: str, parent: str) -> bool:
    return parent == "" or name == parent or name.startswith(parent + "/")


def load() -> Json:
    source: str = env_get("SYNC_CONFIG", "sync.json")
    raw: Json = document(source)
    fields(raw, ["source", "destination", "exclude", "max_entries", "max_bytes"])
    roots: list[str] = []
    for key in ["source", "destination"]:
        root: str = path_resolve(json_string(raw[key]))
        assert root != "/" and json_string(path_stat(root, False)["kind"]) == "directory", "invalid root"
        roots.append(root)
        raw[key] = root
    assert not under(roots[0], roots[1]) and not under(roots[1], roots[0]), "trees overlap"
    for key in ["max_entries", "max_bytes"]:
        maximum: int = 10000 if key == "max_entries" else 1099511627776
        assert json_int(raw[key]) >= 1 and json_int(raw[key]) <= maximum, "invalid budget"
    rules: list[Json] = json_array(raw["exclude"])
    assert len(rules) <= 128, "too many exclusions"
    for rule in rules:
        assert len(json_string(rule).encode()) <= 1024, "exclusion is too long"
        regex_search(json_string(rule), "")
    paths: list[str] = [path_resolve(source)]
    for key in ["plan", "baseline"]:
        value: str = env_get("SYNC_" + key.upper(), "sync-" + key + ".json")
        assert not path_is_symlink(value), "output cannot be a symlink"
        path: str = path_join(path_resolve(path_parent(value)), path_name(value))
        for root in roots:
            assert not under(path, root), "documents must be outside both trees"
        if path_exists(path):
            assert json_string(path_stat(path, False)["kind"]) == "file", "output must be regular"
        for other in paths:
            assert other != path, "document paths collide"
            if path_exists(path) and path_exists(other):
                assert not path_same(path, other), "document files alias"
        raw[key] = path
        paths.append(path)
    return raw
