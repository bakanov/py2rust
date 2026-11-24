"""A before/after journal makes each interruption boundary recoverable."""

import sys

from diff import changes
from schema import exact_keys, upgrade, validate

from py2rust.stdlib import (
    Json,
    env_get,
    json_equal,
    json_int,
    json_loads,
    json_string,
    path_exists,
    path_resolve,
    pretty,
    read_text,
    remove_file,
    write_text_atomic,
)


def checkpoint(name: str) -> None:
    if env_get("MIGRATE_STOP", "") == name:
        print("INTERRUPTED", name)
        sys.exit(75)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def backup_path(path: str) -> str:
    return path + ".backup"


def journal_path(path: str) -> str:
    return path + ".journal.json"


def ensure_backup(path: str, original: str) -> None:
    destination: str = backup_path(path)
    if path_exists(destination):
        assert read_text(destination) == original, "existing backup belongs to different input"
    else:
        write_text_atomic(destination, original)
    return  # noqa: PLR1711 - explicit return required by repository guidelines


def versions(start: int) -> list[int]:
    result: list[int] = []
    for version in range(start + 1, 4):
        result.append(version)  # noqa: PERF402 - range iterators are not first-class values in this profile
    return result


def result(action: str, start: int) -> Json:
    return {"action": action, "from": start, "to": 3, "steps": versions(start)}


def recover(path: str) -> Json:
    journal: Json = json_loads(read_text(journal_path(path)))
    exact_keys(journal, ["format", "target", "before", "after", "from"])
    assert json_int(journal["format"]) == 1, "unsupported migration journal"
    assert json_string(journal["target"]) == path_resolve(path), "journal belongs to another target"
    before: str = json_string(journal["before"])
    after: str = json_string(journal["after"])
    original: Json = json_loads(before)
    target: Json = json_loads(after)
    start: int = validate(original)
    assert start < 3 and start == json_int(journal["from"]), "invalid journal source version"
    assert validate(target) == 3, "journal target is not current"
    assert json_equal(upgrade(original), target), "journal does not match the migration plan"
    assert path_exists(backup_path(path)), "migration backup is missing"
    assert read_text(backup_path(path)) == before, "migration backup was modified"
    current: str = read_text(path)
    assert current == before or current == after, "target changed during interrupted migration"
    if current == before:
        write_text_atomic(path, after)
    checkpoint("after_replace")
    remove_file(journal_path(path))
    checkpoint("after_cleanup")
    return result("recovered", start)


def execute(path: str, preview: bool) -> Json:
    original: str = read_text(path)
    document: Json = json_loads(original)
    start: int = validate(document)
    if path_exists(journal_path(path)):
        assert not preview, "recover the pending migration before previewing"
        return recover(path)
    upgraded: Json = upgrade(document)
    if start == 3:
        return result("unchanged", start)
    if preview:
        return {
            "action": "preview",
            "from": start,
            "to": 3,
            "steps": versions(start),
            "document": upgraded,
            "changes": changes(document, upgraded, ""),
        }
    ensure_backup(path, original)
    checkpoint("after_backup")
    after: str = pretty(upgraded)
    journal: Json = {"format": 1, "target": path_resolve(path), "before": original, "after": after, "from": start}
    write_text_atomic(journal_path(path), pretty(journal))
    checkpoint("after_journal")
    write_text_atomic(path, after)
    checkpoint("after_replace")
    remove_file(journal_path(path))
    checkpoint("after_cleanup")
    return result("migrated", start)


def rollback(path: str) -> Json:
    assert not path_exists(journal_path(path)), "recover the pending migration before rollback"
    original: str = read_text(backup_path(path))
    before: Json = json_loads(original)
    start: int = validate(before)
    assert start < 3, "backup is not an older schema"
    current_text: str = read_text(path)
    if current_text == original:
        return {"action": "unchanged", "from": start, "to": start}
    current: Json = json_loads(current_text)
    assert validate(current) == 3, "rollback requires the current schema"
    assert json_equal(current, upgrade(before)), "configuration changed after migration"
    write_text_atomic(path, original)
    return {"action": "rolled_back", "from": 3, "to": start}
