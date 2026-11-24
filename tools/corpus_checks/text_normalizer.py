"""Byte-level file oracles, idempotence, path safety and restoration conflicts."""

import json
from pathlib import Path

from .common import Application


def check(app: Application, directory: Path) -> dict:
    root = directory / "files"
    root.mkdir()
    originals = {
        "mixed.txt": "α  \r\nβ\t\rγ \nlast\t".encode(),
        "clean.txt": b"already clean\n",
        "blank.txt": b"",
        "spaces.txt": b" \t \r\n\t\r\n",
        "bom.txt": b"\xef\xbb\xbfhello \r\n",
    }
    expected = {
        "mixed.txt": "α\nβ\nγ\nlast\n".encode(),
        "clean.txt": b"already clean\n",
        "blank.txt": b"",
        "spaces.txt": b"\n\n",
        "bom.txt": b"\xef\xbb\xbfhello\n",
    }
    for name, content in originals.items():
        (root / name).write_bytes(content)
    config_path = directory / "normalize.json"
    report_path = directory / "report.json"
    settings = {"NORMALIZE_CONFIG": str(config_path), "NORMALIZE_REPORT": str(report_path)}
    config = {
        "root": str(root),
        "files": list(originals),
        "mode": "preview",
        "final_newline": "ensure",
        "max_bytes": 64,
    }

    def run(changes: dict, exit_code: int = 0) -> dict:
        config.update(changes)
        config_path.write_text(json.dumps(config))
        result = app.run(directory, settings)
        assert result.returncode == exit_code, result.stderr + result.stdout
        return json.loads(report_path.read_text())

    preview = run({})
    assert preview["changed"] == 3 and preview["errors"] == 0
    assert preview["files"][0]["preview"] == {"line": 1, "before": "α  \r", "after": "α"}
    assert not (root / ".normalizer-backups").exists()
    assert {name: (root / name).read_bytes() for name in originals} == originals
    applied = run({"mode": "apply"})
    assert applied["changed"] == 3 and applied["errors"] == 0
    assert {name: (root / name).read_bytes() for name in originals} == expected
    for index, name in enumerate(originals):
        backup = root / ".normalizer-backups" / f"{index}.original"
        if originals[name] != expected[name]:
            assert backup.read_bytes() == originals[name]
        else:
            assert not backup.exists()
    repeated = run({"mode": "preview"})
    assert repeated["changed"] == 0
    assert all(item["status"] == "unchanged" for item in repeated["files"])
    # Restoration preserves user edits instead of overwriting them.
    (root / "mixed.txt").write_bytes(b"user edits\n")
    conflict = run({"mode": "restore"}, 1)
    assert conflict["errors"] == 1 and conflict["restored"] == 2
    assert (root / "mixed.txt").read_bytes() == b"user edits\n"
    (root / "mixed.txt").write_bytes(expected["mixed.txt"])
    restored = run({"mode": "restore"})
    assert restored["restored"] == 3 and restored["errors"] == 0
    assert {name: (root / name).read_bytes() for name in originals} == originals
    assert run({"mode": "restore"})["errors"] == 0
    # Exercise CRLF output, removal of final newlines, and preserving horizontal whitespace.
    single = root / "single.txt"
    single.write_bytes(b"one \r\ntwo\t\n\n")
    run(
        {
            "mode": "apply",
            "files": ["single.txt"],
            "backups": ".other-backups",
            "newline": "crlf",
            "final_newline": "remove",
            "trim_trailing": False,
        }
    )
    assert single.read_bytes() == b"one \r\ntwo\t"
    assert run({"mode": "preview"})["changed"] == 0
    # Bad files do not prevent later files from being inspected.
    (root / "invalid.txt").write_bytes(b"\xff")
    (root / "nul.txt").write_bytes(b"a\x00b")
    (root / "huge.txt").write_bytes(b"x" * 65)
    outside = directory / "outside.txt"
    outside.write_bytes(b"outside \r\n")
    (root / "link.txt").symlink_to(outside)
    failures = run(
        {
            "files": ["invalid.txt", "nul.txt", "huge.txt", "missing.txt", "link.txt", "clean.txt"],
            "newline": "lf",
            "final_newline": "preserve",
        },
        1,
    )
    assert failures["errors"] == 5 and failures["files"][-1]["status"] == "unchanged"
    assert outside.read_bytes() == b"outside \r\n"
    for name in ["../outside.txt", "/absolute", "sub/../file", ".normalizer-backups/0.original"]:
        config.update(files=[name], backups=".normalizer-backups", mode="preview")
        config_path.write_text(json.dumps(config))
        before = report_path.read_bytes()
        assert app.run(directory, settings).returncode != 0
        assert report_path.read_bytes() == before
    return {
        "changed": applied["changed"],
        "idempotent": True,
        "exact_backups": True,
        "restored_original_bytes": True,
        "restore_conflicts": 1,
        "rejected_files": 5,
        "crlf_without_final_newline": True,
        "symlink_target_unchanged": True,
    }
