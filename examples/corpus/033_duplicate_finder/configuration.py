"""Bounded scan policy and output paths outside the tree being inspected."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
    file_read,
    file_size,
    json_array,
    json_get,
    json_int,
    json_keys,
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
)


def output_path(value: str, root: str) -> str:
    assert not path_is_symlink(value), "output cannot be a symlink"
    result: str = path_join(path_resolve(path_parent(value)), path_name(value))
    assert root != "/" and result != root and not result.startswith(root + "/"), "outputs must be outside root"
    if path_exists(result):
        assert json_string(path_stat(result, False)["kind"]) == "file", "output must be a regular file"
    return result


def load() -> Json:
    source: str = env_get("DUPLICATE_CONFIG", "duplicates.json")
    raw: Json = {}
    with file_open(source, "rb") as handle:
        assert file_size(handle) <= 65536, "configuration exceeds 64 KiB"
        data: bytes = file_read(handle, 65537)
        assert len(data) <= 65536, "configuration grew beyond 64 KiB"
        raw = json_loads(data.decode())
    root: str = path_resolve(json_string(raw["root"]))
    assert json_string(path_stat(root, False)["kind"]) == "directory", "root must be a directory"
    bounds: dict[str, tuple[int, int, int]] = {
        "max_depth": (64, 0, 256),
        "max_entries": (20000, 1, 200000),
        "max_children": (10000, 1, 100000),
        "min_size": (0, 0, 1099511627776),
        "max_size": (1073741824, 0, 1099511627776),
        "max_hash_bytes": (1073741824, 0, 1099511627776),
        "max_compare_bytes": (1073741824, 0, 2199023255552),
        "max_comparisons": (100000, 0, 1000000),
        "chunk_bytes": (65536, 1, 1048576),
        "digest_chars": (64, 1, 64),
        "max_report_bytes": (33554432, 1024, 134217728),
    }
    for key in json_keys(raw):
        assert key in bounds or key in ["root", "exclude"], "unknown configuration field"
    config: Json = {"root": root}
    for key in bounds:  # noqa: PLC0206 - typed dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid limit: " + key
        config[key] = value
    assert json_int(config["min_size"]) <= json_int(config["max_size"]), "min_size exceeds max_size"
    rules: list[Json] = json_array(json_get(raw, "exclude", []))
    assert len(rules) <= 128, "too many exclusions"
    for rule in rules:
        assert len(json_string(rule).encode()) <= 1024, "exclusion pattern exceeds 1024 bytes"
        regex_search(json_string(rule), "")
    config["exclude"] = rules
    report: str = output_path(env_get("DUPLICATE_REPORT", "duplicate-report.json"), root)
    plan: str = env_get("DUPLICATE_PLAN", "")
    paths: list[str] = [path_resolve(source), report]
    if plan != "":
        plan = output_path(plan, root)
        paths.append(plan)
    for left in range(len(paths)):
        for right in range(left + 1, len(paths)):
            assert paths[left] != paths[right], "configuration and outputs must be distinct"
            if path_exists(paths[left]) and path_exists(paths[right]):
                assert not path_same(paths[left], paths[right]), "configuration and outputs alias"
    config["report"] = report
    config["plan"] = plan
    return config


def excluded(name: str, config: Json) -> bool:
    for rule in json_array(config["exclude"]):
        if regex_search(json_string(rule), name):
            return True
    return False
