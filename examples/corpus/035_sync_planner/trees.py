"""Read both trees without following symlinks; signatures depend on actual bytes."""

from documents import relative

from py2rust.stdlib import (
    Json,
    Sha256,
    directory_names,
    file_open,
    file_read,
    json_array,
    json_equal,
    json_int,
    json_string,
    path_exists,
    path_is_symlink,
    path_join,
    path_stat,
    read_link,
    regex_search,
    sha256_digest,
    sha256_new,
    sha256_update,
)


def stamp(path: str) -> Json:
    value: Json = path_stat(path, False)
    del value["atime_ns"]
    return value


def unchanged(root: str, guards: dict[str, Json]) -> None:
    for name in guards:  # noqa: PLC0206 - typed key iteration
        assert json_equal(stamp(path_join(root, name)), guards[name]), "tree changed: " + name
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def output_guard(path: str, guards: dict[str, Json]) -> None:
    if path_exists(path) or path_is_symlink(path):
        info: Json = stamp(path)
        assert json_string(info["kind"]) == "file", "output is no longer regular"
        for name in guards:  # noqa: PLC0206 - typed key iteration
            before: Json = guards[name]
            assert info["device"] != before["device"] or info["inode"] != before["inode"], "output aliases an input"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def scan(root: str, config: Json) -> tuple[dict[str, Json], dict[str, Json], list[str]]:
    entries: dict[str, Json] = {}
    guards: dict[str, Json] = {}
    protected: list[str] = []
    pending: list[str] = [""]
    cursor: int = 0
    visited: int = 1
    hashed: int = 0
    while cursor < len(pending):
        name: str = pending[cursor]
        cursor = cursor + 1
        relative(name)
        path: str = path_join(root, name)
        before: Json = stamp(path)
        kind: str = json_string(before["kind"])
        entry: Json = {"kind": kind, "mode": json_int(before["mode"]) & 511}
        if kind == "directory":
            for child in directory_names(path, 10000):
                visited = visited + 1
                assert visited <= json_int(config["max_entries"]), "entry budget exceeded"
                child = child if name == "" else name + "/" + child
                excluded: bool = False
                for rule in json_array(config["exclude"]):
                    if regex_search(json_string(rule), child):
                        excluded = True
                if not excluded:
                    pending.append(child)
                else:
                    protected.append(child)
                    guards[child] = stamp(path_join(root, child))
        elif kind == "file":
            size: int = json_int(before["size"])
            hashed = hashed + size
            assert hashed <= json_int(config["max_bytes"]), "byte budget exceeded"
            digest: Sha256 = sha256_new()
            count: int = 0
            with file_open(path, "rb") as handle:
                while count < size:
                    data: bytes = file_read(handle, min(65536, size - count))
                    assert len(data) > 0, "unexpected EOF"
                    digest = sha256_update(digest, data)
                    count = count + len(data)
                assert file_read(handle, 1) == b"", "file grew"
            entry["size"] = size
            entry["sha256"] = sha256_digest(digest)
        else:
            assert kind == "symlink", "unsupported special file"
            entry = {"kind": kind, "target": read_link(path)}
        assert json_equal(stamp(path), before), "entry changed during scan"
        entries[name] = entry
        guards[name] = before
    unchanged(root, guards)
    return (entries, guards, protected)
