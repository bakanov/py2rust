"""Preview, apply with byte-preserving backups, or safely restore a file batch."""

import sys

from config import (
    backup_directory,
    input_root,
    load_config,
    setting,
    source_path,
    validate,
)
from normalize import describe, normalized

from py2rust.stdlib import (
    Json,
    env_get,
    json_array,
    json_bool,
    json_get,
    json_int,
    json_loads,
    json_string,
    mkdir_all,
    path_exists,
    path_join,
    path_resolve,
    pretty,
    read_bytes,
    read_text,
    write_bytes,
    write_text_atomic,
)


def backup_name(index: int) -> str:
    return str(index) + ".original"


def changed_name(index: int) -> str:
    return str(index) + ".normalized"


def receipt_path(config: Json) -> str:
    return path_join(backup_directory(config), "receipt.json")


def prepare_backups(config: Json) -> None:
    directory: str = backup_directory(config)
    mkdir_all(directory)
    assert path_resolve(directory) == directory, "backup directory cannot be a symlink"
    assert not path_exists(receipt_path(config)), "existing receipt must be restored or archived before applying"
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def process_file(config: Json, name: str, index: int, applying: bool) -> Json:
    path: str = source_path(input_root(config), name)
    original: bytes = read_bytes(path)
    assert len(original) <= json_int(json_get(config, "max_bytes", 1048576)), "input exceeds size limit"
    text: str = original.decode()
    assert "\x00" not in text, "input contains NUL bytes"
    transformed: str = normalized(text, config)
    result: Json = describe(name, text, transformed)
    result["index"] = index
    result["status"] = "unchanged"
    if json_bool(result["changed"]):
        result["status"] = "would-change"
        if applying:
            directory: str = backup_directory(config)
            backup: str = path_join(directory, backup_name(index))
            expected: str = path_join(directory, changed_name(index))
            assert not path_exists(backup) and not path_exists(expected), "backup file already exists"
            write_bytes(backup, original)
            write_bytes(expected, transformed.encode())
            write_text_atomic(path, transformed)
            result["status"] = "applied"
    return result


def normalize_batch(config: Json) -> Json:
    applying: bool = setting(config, "mode", "preview") == "apply"
    if applying:
        prepare_backups(config)
    results: list[Json] = []
    index: int = 0
    errors: int = 0
    changed: int = 0
    for item in json_array(config["files"]):
        name: str = json_string(item)
        try:
            result: Json = process_file(config, name, index, applying)
            results.append(result)
            if json_bool(result["changed"]):
                changed = changed + 1
        except Exception as failure:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
            print("normalization failed for", name, str(failure))
            results.append({"file": name, "index": index, "status": "error"})
            errors = errors + 1
        index = index + 1
        if applying:
            # Save the receipt after each file, including failed entries.
            write_text_atomic(receipt_path(config), pretty({"version": 1, "entries": results}))
    return {"mode": setting(config, "mode", "preview"), "files": results, "changed": changed, "errors": errors}


def restore_batch(config: Json) -> Json:
    receipt: Json = json_loads(read_text(receipt_path(config)))
    assert json_int(receipt["version"]) == 1, "unsupported receipt version"
    results: list[Json] = []
    errors: int = 0
    restored: int = 0
    directory: str = backup_directory(config)
    assert path_resolve(directory) == directory, "backup directory cannot be a symlink"
    for entry in json_array(receipt["entries"]):
        name: str = json_string(entry["file"])
        if json_string(entry["status"]) == "applied":
            try:
                path: str = source_path(input_root(config), name)
                index: int = json_int(entry["index"])
                assert index >= 0, "invalid backup index"
                original: bytes = read_bytes(path_join(directory, backup_name(index)))
                expected: bytes = read_bytes(path_join(directory, changed_name(index)))
                current: bytes = read_bytes(path)
                assert current == expected or current == original, "file changed since normalization"
                # Originals were validated as UTF-8 before backup; atomic text
                # writing preserves their exact encoded bytes, including CRLF.
                write_text_atomic(path, original.decode())
                results.append({"file": name, "status": "restored"})
                restored = restored + 1
            except Exception as failure:  # noqa: BLE001 - the profile exposes recoverable failures through Exception
                print("restoration failed for", name, str(failure))
                results.append({"file": name, "status": "error"})
                errors = errors + 1
    return {"mode": "restore", "files": results, "restored": restored, "errors": errors}


def main() -> None:
    config: Json = load_config()
    validate(config)
    report: Json = {}
    if setting(config, "mode", "preview") == "restore":
        report = restore_batch(config)
    else:
        report = normalize_batch(config)
    write_text_atomic(env_get("NORMALIZE_REPORT", "normalization-report.json"), pretty(report))
    print(pretty(report))
    if json_int(report["errors"]) > 0:
        sys.exit(1)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


if __name__ == "__main__":
    main()
