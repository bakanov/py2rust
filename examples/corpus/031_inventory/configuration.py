"""Validated traversal bounds and a report path outside the input tree."""

from py2rust.stdlib import (
    Json,
    env_get,
    file_open,
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
    read_text,
    regex_search,
)


def load() -> Json:
    source: str = env_get("INVENTORY_CONFIG", "inventory.json")
    with file_open(source, "rb") as handle:
        assert file_size(handle) <= 65536, "configuration exceeds 64 KiB"
    raw: Json = json_loads(read_text(source))
    allowed: list[str] = ["root", "exclude", "max_depth", "max_entries", "max_children", "max_report_bytes"]
    for key in json_keys(raw):
        assert key in allowed, "unknown configuration field"
    root: str = path_resolve(env_get("INVENTORY_ROOT", json_string(json_get(raw, "root", "tree"))))
    assert json_string(path_stat(root, False)["kind"]) == "directory", "root must be a directory"
    output: str = env_get("INVENTORY_REPORT", "inventory-report.json")
    assert not path_is_symlink(output), "report cannot be a symlink"
    output = path_join(path_resolve(path_parent(output)), path_name(output))
    assert root != "/" and output != root and not output.startswith(root + "/"), "report must be outside the input tree"
    if path_exists(output):
        assert not path_same(output, source), "report aliases configuration"
        assert json_string(path_stat(output, False)["kind"]) == "file", "existing report must be a regular file"
    rules: list[Json] = json_array(json_get(raw, "exclude", []))
    assert len(rules) <= 128, "too many exclusion rules"
    for value in rules:
        pattern: str = json_string(value)
        assert len(pattern.encode()) <= 1024, "exclusion pattern too large"
        regex_search(pattern, "")
    result: Json = {"root": root, "output": output, "exclude": rules}
    bounds: dict[str, tuple[int, int, int]] = {
        "max_depth": (64, 0, 256),
        "max_entries": (20000, 1, 200000),
        "max_children": (10000, 1, 100000),
        "max_report_bytes": (33554432, 1024, 134217728),
    }
    for key in bounds:  # noqa: PLC0206 - supported dictionary-key iteration
        limits: tuple[int, int, int] = bounds[key]
        value: int = json_int(json_get(raw, key, limits[0]))
        assert value >= limits[1] and value <= limits[2], "invalid limit: " + key
        result[key] = value
    return result


def excluded(relative: str, config: Json) -> bool:
    for rule in json_array(config["exclude"]):
        if regex_search(json_string(rule), relative):
            return True
    return False
