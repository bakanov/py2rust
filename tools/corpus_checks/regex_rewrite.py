"""Independent literal-regex oracle, exact backup checks and interrupted recovery."""

# ruff: noqa: PLR1711 - explicit repository returns
import copy
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .common import Application


@dataclass
class Fixture:
    directory: Path
    config: dict
    original: dict[str, bytes]
    metadata: dict[str, tuple[int, int]]

    @property
    def job(self) -> Path:
        return self.directory / "job.json"

    @property
    def backup(self) -> Path:
        return self.directory / self.config["backup"]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(directory: Path) -> Fixture:
    directory.mkdir(parents=True)
    original = {"a.txt": "é TODO\n".encode(), "b.txt": b"DONE\n", "c.txt": b"TODO\r\n", "empty": b"", "keep": b"stable"}
    metadata = {}
    for index, (name, data) in enumerate(original.items()):
        path = directory / name
        path.write_bytes(data)
        mode, mtime = (0o440 if index == 0 else 0o640), -1234567890 + index
        path.chmod(mode)
        os.utime(path, ns=(mtime, mtime))
        metadata[name] = mode, mtime
    rules = [
        {"name": "ending", "pattern": r"\bTODO$", "replacement": r"$1\1"},
        {"name": "strict", "pattern": r"DONE\n\Z", "replacement": "世界\n"},
        {"name": "crlf", "pattern": r"TODO\r$", "replacement": "CRLF\r"},
    ]
    config = {"version": 1, "backup": "backup", "files": list(original), "rules": rules}
    case = Fixture(directory, config, original, metadata)
    save(case)
    return case


def save(case: Fixture) -> None:
    case.job.write_text(json.dumps(case.config))
    return


def invoke(app: Application, case: Fixture, mode: str, success: bool = True, **settings: str) -> dict | str:
    result = app.run(
        case.directory,
        {"REWRITE_CONFIG": str(case.job), "REWRITE_MODE": mode, "REWRITE_BACKUP": str(case.backup), **settings},
        timeout=60,
    )
    assert result.returncode == (0 if success else 2), result
    if not success:
        assert not result.stdout and result.stderr, result
        return result.stderr
    assert not result.stderr, result
    value = json.loads(result.stdout)
    assert value["mode"] == mode
    return value["report"]


def oracle(case: Fixture) -> tuple[dict, dict[str, bytes]]:
    reports, rewritten = [], {}
    for index, (name, data) in enumerate(case.original.items()):
        text = data.decode()
        events = []
        for rule in case.config["rules"]:
            compiled = re.compile(rule["pattern"], re.ASCII)
            matches = list(compiled.finditer(text))
            assert all(match.start() != match.end() for match in matches)
            after = compiled.sub(lambda _match, replacement=rule["replacement"]: replacement, text)
            events.append(
                {
                    "rule": rule["name"],
                    "matches": len(matches),
                    "bytes_before": len(text.encode()),
                    "bytes_after": len(after.encode()),
                    "before_sha256": digest(text.encode()),
                    "after_sha256": digest(after.encode()),
                    "changed": after != text,
                }
            )
            text = after
        rewritten[name] = text.encode()
        mode, mtime = case.metadata[name]
        reports.append(
            {
                "path": str(case.directory / name),
                "index": index,
                "changed": text.encode() != data,
                "before_sha256": digest(data),
                "after_sha256": digest(text.encode()),
                "bytes_before": len(data),
                "bytes_after": len(text.encode()),
                "preview_before": data.decode()[:160],
                "preview_after": text[:160],
                "mode": mode,
                "mtime_ns": mtime,
                "rules": events,
            }
        )
    return {"version": 1, "files": reports, "changed": sum(row["changed"] for row in reports)}, rewritten


def files(case: Fixture) -> dict[str, bytes]:
    return {name: (case.directory / name).read_bytes() for name in case.original}


def snapshot(directory: Path) -> dict:
    result = {}
    for path in sorted(directory.rglob("*")):
        info = path.lstat()
        kind = stat.S_IFMT(info.st_mode)
        data = os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None
        result[str(path.relative_to(directory))] = (kind, stat.S_IMODE(info.st_mode), info.st_mtime_ns, data)
    return result


def verify_backup(case: Fixture, report: dict, rewritten: dict[str, bytes]) -> None:
    assert json.loads((case.backup / "report.json").read_bytes()) == report
    assert (case.backup / "job.json").read_bytes() == case.job.read_bytes()
    expected = {"report.json", "job.json", "state.json"}
    for index, (name, data) in enumerate(case.original.items()):
        assert (case.backup / f"{index}.before").read_bytes() == data
        assert (case.backup / f"{index}.after").read_bytes() == rewritten[name]
        expected.update([f"{index}.before", f"{index}.after"])
    assert {path.name for path in case.backup.iterdir()} == expected
    assert not list(case.directory.glob(".rewrite-*"))
    return


def verify_restored(case: Fixture) -> None:
    assert files(case) == case.original
    for name, (mode, mtime) in case.metadata.items():
        info = (case.directory / name).stat()
        assert (stat.S_IMODE(info.st_mode), info.st_mtime_ns) == (mode, mtime)
    assert json.loads((case.backup / "state.json").read_text()) == {
        "status": "restored",
        "completed": len(case.original),
    }
    return


def invalid_inputs(app: Application, directory: Path) -> int:
    case = fixture(directory)
    base = copy.deepcopy(case.config)
    patterns = [
        "",
        "[",
        "[a-z",
        "(",
        ")",
        "(?=a)",
        "(?i)a",
        r"(a)\1",
        r"\h$",
        r"\p{Latin}",
        r"\z",
        r"\x",
        r"\xG0",
        r"\q",
        "[a&&b]",
        "[a--b]",
        "[a~~b]",
        "[a||b]",
        "[[:alpha:]]",
        "[[]",
        "a++",
        "a*+",
        "a?+",
        "a{1,2}+",
        "a{,3}",
        "a{thing}",
        "a{10000}",
        "a{2,1}",
        "a{",
        "a}",
        "a**",
        "a**?",
        "(" * 33 + "a" + ")" * 33,
        "é",
        "a\0",
        "a" * 513,
        "a*",
        r"TODO|\b",
    ]
    cases = []
    for pattern in patterns:
        value = copy.deepcopy(base)
        value["rules"].append({"name": "bad", "pattern": pattern, "replacement": "bad"})
        cases.append(value)
    for changes in [
        {"version": 2},
        {"version": True},
        {"extra": 1},
        {"files": []},
        {"files": ["a.txt"] * 65},
        {"files": ["a.txt", "a.txt"]},
        {"rules": []},
        {"rules": base["rules"] * 11},
        {"backup": ""},
        {"backup": "a.txt"},
        {"backup": "job.json"},
    ]:
        cases.append(dict(base, **changes))
    for rule in [
        {"name": "", "pattern": "x", "replacement": ""},
        {"name": "é", "pattern": "x", "replacement": ""},
        {"name": "ok", "pattern": "x", "replacement": "\0"},
        {"name": "ok", "pattern": "x", "replacement": "a" * 4097},
        {"name": "ok", "pattern": "x", "replacement": "x", "extra": 1},
    ]:
        cases.append(dict(base, rules=[rule]))
    for value in cases:
        case.config = value
        save(case)
        before = snapshot(case.directory)
        invoke(app, case, "apply", False)
        assert snapshot(case.directory) == before
    for name, data in {"utf8": b"\xff", "nul": b"x\0", "large": b"x" * 65537}.items():
        case.config = dict(base, files=["a.txt", name])
        (directory / name).write_bytes(data)
        save(case)
        before = snapshot(directory)
        invoke(app, case, "apply", False)
        assert snapshot(directory) == before
    (directory / "link").symlink_to(directory / "a.txt")
    os.link(directory / "a.txt", directory / "hardlink")
    (directory / "folder").mkdir()
    for names in [["link"], ["a.txt", "hardlink"], ["folder"], ["job.json"], ["missing"]]:
        case.config = dict(base, files=names)
        save(case)
        before = snapshot(directory)
        invoke(app, case, "apply", False)
        assert snapshot(directory) == before
    return len(cases) + 8


def check(app: Application, directory: Path) -> dict:
    case = fixture(directory / "normal")
    expected, rewritten = oracle(case)
    before = snapshot(case.directory)
    assert invoke(app, case, "preview") == expected
    assert snapshot(case.directory) == before
    assert invoke(app, case, "apply") == expected
    assert files(case) == rewritten
    verify_backup(case, expected, rewritten)
    assert json.loads((case.backup / "state.json").read_text()) == {"status": "applied", "completed": 5}
    assert invoke(app, case, "preview")["changed"] == 0
    before = snapshot(case.directory)
    invoke(app, case, "apply", False)
    assert snapshot(case.directory) == before
    (case.directory / "b.txt").write_bytes(b"outside edit")
    before = snapshot(case.directory)
    assert "file changed since rewrite" in invoke(app, case, "restore", False)
    assert snapshot(case.directory) == before
    (case.directory / "b.txt").write_bytes(rewritten["b.txt"])
    backup_file = case.backup / "1.before"
    backup_file.write_bytes(b"corrupt")
    before = snapshot(case.directory)
    assert "corrupt backup" in invoke(app, case, "restore", False)
    assert snapshot(case.directory) == before
    backup_file.write_bytes(case.original["b.txt"])
    for _index in range(2):
        assert invoke(app, case, "restore") == expected
        verify_restored(case)
    for boundary in [0, 1, 4]:
        partial = fixture(directory / ("interrupted-" + str(boundary)))
        report, after = oracle(partial)
        invoke(app, partial, "apply", False, REWRITE_FAIL=str(boundary))
        assert json.loads((partial.backup / "state.json").read_text()) == {
            "status": "interrupted",
            "completed": boundary,
        }
        verify_backup(partial, report, after)
        for index, (name, data) in enumerate(partial.original.items()):
            assert (partial.directory / name).read_bytes() == (after[name] if index < boundary else data)
        assert invoke(app, partial, "restore") == report
        verify_restored(partial)
    invalid = invalid_inputs(app, directory / "invalid")
    return {
        "independent_cpython_literal_replacement_oracle": True,
        "files": len(case.original),
        "rules": len(case.config["rules"]),
        "changed": expected["changed"],
        "preview_has_no_writes": True,
        "backups_have_exact_before_and_after_bytes": True,
        "invalid_cases_rejected_without_writes": invalid,
        "interruption_boundaries_restored": 3,
        "existing_backups_preserved": True,
        "external_edits_and_corruption_prevent_all_restore_writes": True,
        "negative_timestamps_and_permissions_restored": True,
        "repeat_restore": True,
        "rewritten_sha256": digest(b"".join(rewritten.values())),
    }
