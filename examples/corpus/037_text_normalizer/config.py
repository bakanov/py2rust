"""Validate a bounded explicit manifest and reject unsafe relative paths."""

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_loads,
    json_string,
    path_join,
    path_resolve,
    read_text,
)


def load_config() -> Json:
    return json_loads(read_text(env_get("NORMALIZE_CONFIG", "normalize.json")))


def setting(config: Json, key: str, default: str) -> str:
    return json_string(json_get(config, key, default))


def safe_relative(name: str) -> bool:
    if len(name) == 0 or name.startswith("/") or "\\" in name or "\x00" in name:
        return False
    for component in name.split("/"):
        if component == "" or component == "." or component == "..":
            return False
    return True


def input_root(config: Json) -> str:
    return path_resolve(setting(config, "root", "."))


def source_path(root: str, name: str) -> str:
    assert safe_relative(name), "unsafe relative file name"
    path: str = path_join(root, name)
    # Prevent symlink traversal or replacing a symlink instead of its target.
    assert path_resolve(path) == path, "symlinked input paths are not supported"
    return path


def backup_directory(config: Json) -> str:
    return path_join(input_root(config), setting(config, "backups", ".normalizer-backups"))


def validate(config: Json) -> None:
    mode: str = setting(config, "mode", "preview")
    assert mode in ["preview", "apply", "restore"], "mode must be preview, apply or restore"
    assert setting(config, "newline", "lf") in ["lf", "crlf"], "newline must be lf or crlf"
    assert setting(config, "final_newline", "preserve") in [
        "preserve",
        "ensure",
        "remove",
    ], "invalid final newline policy"
    json_bool(json_get(config, "trim_trailing", True))
    limit: int = json_int(json_get(config, "max_bytes", 1048576))
    assert limit > 0 and limit <= 16777216, "max_bytes must be 1–16777216"
    backup: str = setting(config, "backups", ".normalizer-backups")
    assert safe_relative(backup) and "/" not in backup, "backup directory must be a basename"
    files: list[Json] = json_array(config["files"])
    assert len(files) > 0 and len(files) <= 1000, "expected 1–1000 input files"
    names: set[str] = set()
    for item in files:
        name: str = json_string(item)
        assert safe_relative(name), "unsafe relative file name"
        assert name != backup and not name.startswith(backup + "/"), "input cannot be a backup"
        assert name not in names, "duplicate input file"
        names.add(name)
    input_root(config)
    return  # noqa: PLR1711 - explicit return required by repository guidelines
