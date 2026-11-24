"""Exact backup, validation and every durable interruption boundary."""

import copy
import json
from pathlib import Path

from .common import Application


def check(app: Application, directory: Path) -> dict:
    old = {"version": 1, "host": "127.0.0.1", "port": 8080, "debug": True, "timeout": 30, "tags": ["api", "local"]}
    middle = {
        "version": 2,
        "listen": {"host": "127.0.0.1", "port": 8080},
        "logging": {"level": "DEBUG"},
        "timeout_ms": 30000,
        "tags": ["api", "local"],
    }
    expected = {
        "version": 3,
        "server": {"bind": "127.0.0.1", "port": 8080, "timeout_ms": 30000},
        "logging": {"level": "DEBUG"},
        "labels": {"api": True, "local": True},
    }
    for number, source in enumerate([old, middle, expected], 1):
        path = directory / f"v{number}.json"
        original = (json.dumps(source, indent=2).replace("\n", "\r\n") + "\r\n").encode()
        path.write_bytes(original)
        settings = {"MIGRATE_FILE": str(path), "MIGRATE_MODE": "preview"}
        preview = app.run(directory, settings)
        assert preview.returncode == 0, preview.stderr
        result = json.loads(preview.stdout)
        assert result["action"] == ("unchanged" if number == 3 else "preview")
        if number != 3:
            assert result["document"] == expected
            changes = {item["path"]: item for item in result["changes"]}
            assert changes["version"] == {"path": "version", "change": "replace", "before": number, "after": 3}
            assert changes["server"]["change"] == "add" and changes["server"]["after"] == expected["server"]
        assert path.read_bytes() == original and not Path(str(path) + ".backup").exists()
        applied = app.run(directory, dict(settings, MIGRATE_MODE="apply"))
        assert applied.returncode == 0, applied.stderr
        assert json.loads(path.read_bytes()) == expected
        if number != 3:
            assert Path(str(path) + ".backup").read_bytes() == original
        before = path.read_bytes()
        repeated = app.run(directory, dict(settings, MIGRATE_MODE="apply"))
        assert repeated.returncode == 0 and json.loads(repeated.stdout)["action"] == "unchanged"
        assert path.read_bytes() == before
        if number != 3:
            rolled_back = app.run(directory, dict(settings, MIGRATE_MODE="rollback"))
            assert rolled_back.returncode == 0, rolled_back.stderr
            assert json.loads(rolled_back.stdout) == {"action": "rolled_back", "from": 3, "to": number}
            assert path.read_bytes() == original
            assert app.run(directory, dict(settings, MIGRATE_MODE="rollback")).returncode == 0
            assert app.run(directory, dict(settings, MIGRATE_MODE="apply")).returncode == 0
            modified = copy.deepcopy(expected)
            modified["server"]["port"] = 9000
            path.write_text(json.dumps(modified))
            assert app.run(directory, dict(settings, MIGRATE_MODE="rollback")).returncode != 0
            assert json.loads(path.read_text()) == modified
    boundaries = ["after_backup", "after_journal", "after_replace", "after_cleanup"]
    for boundary in boundaries:
        path = directory / (boundary + ".json")
        original = json.dumps(old).encode()
        path.write_bytes(original)
        settings = {"MIGRATE_FILE": str(path), "MIGRATE_MODE": "apply"}
        interrupted = app.run(directory, dict(settings, MIGRATE_STOP=boundary))
        assert interrupted.returncode == 75, interrupted.stderr
        assert json.loads(path.read_bytes()) in [old, expected]
        resumed = app.run(directory, settings)
        assert resumed.returncode == 0, resumed.stderr
        assert json.loads(path.read_bytes()) == expected
        assert Path(str(path) + ".backup").read_bytes() == original
        assert not Path(str(path) + ".journal.json").exists()
    # External edits and malformed recovery state must not be overwritten.
    path = directory / "conflict.json"
    path.write_text(json.dumps(old))
    settings = {"MIGRATE_FILE": str(path), "MIGRATE_MODE": "apply"}
    assert app.run(directory, dict(settings, MIGRATE_STOP="after_journal")).returncode == 75
    edited = dict(old, port=9000)
    path.write_text(json.dumps(edited))
    before = path.read_bytes()
    assert app.run(directory, settings).returncode != 0
    assert path.read_bytes() == before
    path.write_text(json.dumps(old))
    journal_path = Path(str(path) + ".journal.json")
    journal = json.loads(journal_path.read_text())
    wrong = copy.deepcopy(expected)
    wrong["server"]["port"] = 9000
    journal["after"] = json.dumps(wrong)
    journal_path.write_text(json.dumps(journal))
    assert app.run(directory, settings).returncode != 0
    assert json.loads(path.read_text()) == old
    invalid = [
        dict(old, version=9),
        dict(old, port=0),
        dict(old, debug=1),
        dict(old, timeout=-1),
        dict(old, tags=["same", "same"]),
        dict(old, extra=True),
    ]
    for index, source in enumerate(invalid):
        path = directory / f"invalid-{index}.json"
        path.write_text(json.dumps(source))
        before = path.read_bytes()
        assert app.run(directory, {"MIGRATE_FILE": str(path), "MIGRATE_MODE": "apply"}).returncode != 0
        assert path.read_bytes() == before
        assert not Path(str(path) + ".backup").exists()
        assert not Path(str(path) + ".journal.json").exists()
    return {
        "current": expected,
        "old_versions": [1, 2],
        "idempotent": True,
        "interruption_boundaries": boundaries,
        "external_edits_preserved": True,
        "tampered_journal_rejected": True,
        "invalid_inputs": len(invalid),
    }
