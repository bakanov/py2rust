"""Read stable snapshots of explicitly named files and build the entire plan first."""

from dataclasses import dataclass

from documents import Document, absolute, present, read
from rules import Rule, digest, load_rules, transform

from py2rust.stdlib import (
    Json,
    json_array,
    json_canonical,
    json_int,
    json_keys,
    json_loads,
    json_string,
    path_parent,
    path_same,
)


@dataclass
class Change:
    original: Document
    replacement: bytes
    report: Json


@dataclass
class Plan:
    config: Document
    backup: str
    changes: list[Change]
    report: Json


def prepare(config: Document, require_fresh_backup: bool) -> Plan:
    value: Json = json_loads(config.data.decode())
    assert sorted(json_keys(value)) == ["backup", "files", "rules", "version"], "invalid job fields"
    assert json_int(value["version"]) == 1, "unsupported job version"
    rules: list[Rule] = load_rules(value["rules"])
    backup: str = absolute(json_string(value["backup"]), path_parent(config.path))
    if require_fresh_backup:
        assert not present(backup), "backup already exists"
    assert backup + ".lock" != config.path, "lock collides with configuration"
    files: list[Json] = json_array(value["files"])
    assert 1 <= len(files) <= 64, "expected 1..64 files"
    paths: list[str] = [config.path]
    changes: list[Change] = []
    reports: list[Json] = []
    count: int = 0
    for item in files:
        path: str = absolute(json_string(item), path_parent(config.path))
        assert path != backup and path != backup + ".lock", "input collides with backup or lock"
        for other in paths:
            assert path != other and not path_same(path, other), "input files alias"
        if present(backup + ".lock"):
            assert not path_same(path, backup + ".lock"), "input aliases lock"
        paths.append(path)
        document: Document = read(path, 65536)
        assert 0 <= json_int(document.stamp["mode"]) <= 511, "special permission bits are unsupported"
        text: str = document.data.decode()
        assert "\x00" not in text, "input contains NUL"
        rewritten: tuple[str, list[Json]] = transform(text, rules)
        data: bytes = rewritten[0].encode()
        changed: bool = document.data != data
        if changed:
            count = count + 1
        row: Json = {
            "path": path,
            "index": len(changes),
            "changed": changed,
            "before_sha256": digest(document.data),
            "after_sha256": digest(data),
            "bytes_before": len(document.data),
            "bytes_after": len(data),
            "preview_before": text[:160],
            "preview_after": rewritten[0][:160],
            "mode": document.stamp["mode"],
            "mtime_ns": document.stamp["mtime_ns"],
            "rules": rewritten[1],
        }
        changes.append(Change(document, data, row))
        reports.append(row)
    report: Json = {"version": 1, "files": reports, "changed": count}
    assert len(json_canonical(report).encode()) <= 1048576, "audit exceeds 1 MiB"
    return Plan(config, backup, changes, report)
